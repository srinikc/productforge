// Stage 3c (BI-PF-0413): the worker agent.
//
// A wg-agent process owns one execution slot. Its loop:
//
//	recover -> claim -> write-back "scheduled" -> isolated git worktree
//	-> execute the runtime command -> heartbeat/renew lease -> write-back
//	"executing" -> success|blocked -> release lease
//
// It talks to two HTTP surfaces only: the WorkerGrid coordinator (claim/lease
// lifecycle) and the producer API (status write-back). No producer or PF code
// is imported - WorkerGrid stays producer-agnostic (ADR-0002).
//
// It owns ALL producer write-back, including reopening leases it recovers, so a
// worker that dies mid-run cannot wedge an item in a non-eligible status.
package agent

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"time"

	"workergrid/internal/config"
	"workergrid/internal/producer"
)

// Options are the wg-agent CLI inputs.
type Options struct {
	WorkerID string
	Runtime  string
	Scope    string
	Project  string
	Service  string // coordinator base URL ("" -> config ServiceBase())
	Once     bool   // claim+run at most one item, then exit (tests/one-shots)
}

// Agent executes claimed work. One process = one execution slot.
type Agent struct {
	cfg      config.Config
	opt      Options
	wid      string
	base     string // coordinator base URL
	producer string // producer API base URL
	token    string
	client   *http.Client
	journal  *os.File
}

var nonNameChars = regexp.MustCompile(`[^A-Za-z0-9._-]+`)

// Run validates config, registers the worker, then serves the claim/execute
// loop until interrupted (or one item when opt.Once). Returns a fatal error
// only for an unrecoverable agent problem; per-item failures are written back
// as `blocked` and do not stop the loop.
func Run(opt Options) error {
	cfg := config.Load()
	a := &Agent{
		cfg:      cfg,
		opt:      opt,
		producer: cfg.ProducerBase(),
		token:    cfg.Token(),
		client:   &http.Client{Timeout: 30 * time.Second},
	}
	a.base = strings.TrimRight(opt.Service, "/")
	if a.base == "" {
		a.base = cfg.ServiceBase()
	}
	if a.opt.Runtime == "" {
		a.opt.Runtime = "command"
	}
	if a.opt.Scope == "" {
		a.opt.Scope = "product_forge"
	}
	if err := a.validate(); err != nil {
		return err
	}

	jp := filepath.Join(cfg.StateDir(), "agent-journal.jsonl")
	f, err := os.OpenFile(jp, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return fmt.Errorf("journal %s: %w", jp, err)
	}
	a.journal = f
	defer f.Close()
	a.journalEvent("agent_start", map[string]any{
		"worker_id": opt.WorkerID, "runtime": a.opt.Runtime, "coordinator": a.base,
		"producer": a.producer, "once": opt.Once, "journal": jp,
	})
	fmt.Printf("[wg-agent] worker=%q runtime=%s coordinator=%s producer=%s\n",
		a.opt.WorkerID, a.opt.Runtime, a.base, a.producer)

	if err := a.register(); err != nil {
		return err
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()
	return a.loop(ctx)
}

func (a *Agent) validate() error {
	root := a.cfg.AgentRepoRoot()
	if root == "" {
		return errors.New("agent.repo_root not set in config.json (the git repo to execute work in)")
	}
	if st, err := os.Stat(root); err != nil || !st.IsDir() {
		return fmt.Errorf("agent.repo_root not a directory: %s", root)
	}
	if a.cfg.AgentRuntimeCommand(a.opt.Runtime) == "" {
		return fmt.Errorf("no command for runtime %q (set agent.runtimes.%s.command in config.json)",
			a.opt.Runtime, a.opt.Runtime)
	}
	if _, err := exec.LookPath("git"); err != nil {
		return errors.New("git not found on PATH")
	}
	return nil
}

// ── coordinator client (claim/lease lifecycle) ───────────────────────────────

func (a *Agent) svc(method, path string, body map[string]any) (map[string]any, error) {
	var rdr io.Reader
	if body != nil {
		raw, _ := json.Marshal(body)
		rdr = bytes.NewReader(raw)
	}
	req, err := http.NewRequest(method, a.base+path, rdr)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	if a.token != "" {
		req.Header.Set("Authorization", "Bearer "+a.token)
	}
	resp, err := a.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(io.LimitReader(resp.Body, 4<<20))
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, fmt.Errorf("%s %s -> %d %s", method, path, resp.StatusCode, strings.TrimSpace(string(raw)))
	}
	var out map[string]any
	if err := json.Unmarshal(raw, &out); err != nil {
		return nil, fmt.Errorf("%s %s: bad json: %w", method, path, err)
	}
	return out, nil
}

func (a *Agent) register() error {
	wid := a.opt.WorkerID
	if wid == "" {
		wid = fmt.Sprintf("WRK-%s-%d", nonNameChars.ReplaceAllString(a.opt.Runtime, ""), time.Now().Unix()%100000000)
	}
	deadline := time.Now().Add(60 * time.Second)
	for attempt := 1; ; attempt++ {
		wkr, err := a.svc("POST", "/workers/register", map[string]any{
			"worker_id": wid, "runtime": a.opt.Runtime, "role": "agent"})
		if err == nil {
			a.wid = wid
			a.journalEvent("register", map[string]any{"worker_id": wid, "status": wkr["status"]})
			fmt.Printf("[wg-agent] registered %s\n", wid)
			return nil
		}
		if time.Now().After(deadline) {
			return fmt.Errorf("coordinator unreachable at %s: %w", a.base, err)
		}
		fmt.Printf("[wg-agent] register retry (%d): %v\n", attempt, err)
		time.Sleep(2 * time.Second)
	}
}

// ── the loop ─────────────────────────────────────────────────────────────────

func (a *Agent) loop(ctx context.Context) error {
	poll := time.Duration(a.cfg.AgentPoll()) * time.Second
	for {
		if ctx.Err() != nil {
			a.journalEvent("agent_stop", map[string]any{"reason": "signal"})
			return nil
		}

		a.recoverExpired()

		claim, err := a.svc("POST", "/work", map[string]any{
			"worker_id": a.wid, "runtime": a.opt.Runtime,
			"scope": a.opt.Scope, "project": a.opt.Project})
		if err != nil {
			fmt.Printf("[wg-agent] claim error: %v\n", err)
			if a.opt.Once {
				return fmt.Errorf("claim: %w", err)
			}
			if !sleepCtx(ctx, poll) {
				return nil
			}
			continue
		}
		if assigned, _ := claim["assigned"].(bool); !assigned {
			reason, _ := claim["reason"].(string)
			fmt.Printf("[wg-agent] no work: %s\n", reason)
			if a.opt.Once {
				a.journalEvent("agent_stop", map[string]any{"reason": "no_work", "detail": reason})
				return nil
			}
			if !sleepCtx(ctx, poll) {
				return nil
			}
			continue
		}
		a.execute(ctx, claim)
		if a.opt.Once {
			a.journalEvent("agent_stop", map[string]any{"reason": "once_done"})
			return nil
		}
	}
}

func sleepCtx(ctx context.Context, d time.Duration) bool {
	t := time.NewTimer(d)
	defer t.Stop()
	select {
	case <-ctx.Done():
		return false
	case <-t.C:
		return true
	}
}

// recoverExpired frees dead workers' leases and reopens their items so they are
// claimable again (the agent owns producer write-back; the coordinator keeps
// only lease truth). Best-effort: failures are journaled, never fatal.
func (a *Agent) recoverExpired() {
	res, err := a.svc("POST", "/leases/recover", map[string]any{})
	if err != nil {
		a.journalEvent("recover_error", map[string]any{"error": err.Error()})
		return
	}
	ids, _ := res["recovered"].([]any)
	for _, id := range ids {
		item, _ := id.(string)
		if item == "" {
			continue
		}
		ok, detail := producer.SetStatus(a.producer, a.token, a.opt.Scope, a.opt.Project, item,
			"queued", "lease expired (worker died mid-run); reopened for re-claim by agent "+a.wid)
		a.journalEvent("reopen", map[string]any{"item_id": item, "ok": ok, "detail": detail})
		fmt.Printf("[wg-agent] recovered+reopened %s (ok=%v)\n", item, ok)
	}
}

// execute runs one claimed assignment end to end.
func (a *Agent) execute(ctx context.Context, claim map[string]any) {
	item, _ := claim["item_id"].(string)
	title, _ := claim["title"].(string)
	asg, _ := claim["assignment_id"].(string)
	a.journalEvent("claim", map[string]any{"item_id": item, "title": title, "assignment_id": asg,
		"expires_at": claim["expires_at"]})

	// PIDL approval gate: never execute work that requires approval (fail-closed).
	if policy, ok := claim["execution_policy"].(map[string]any); ok && truthy(policy["approval_required"]) {
		a.setStatus(item, "blocked", "execution_policy.approval_required=true - agent fail-closed, not executed")
		a.release(item)
		a.journalEvent("rejected", map[string]any{"item_id": item, "reason": "approval_required"})
		return
	}

	// Lease is held now: mirror `scheduled` into the backlog so the item is
	// visibly assigned. If the producer is unreachable we must not run untracked.
	if ok, detail := producer.SetStatus(a.producer, a.token, a.opt.Scope, a.opt.Project, item,
		"scheduled", fmt.Sprintf("leased to %s (%s) assignment %s", a.wid, a.opt.Runtime, asg)); !ok {
		a.release(item)
		a.journalEvent("writeback_failed", map[string]any{"item_id": item, "status": "scheduled", "detail": detail})
		fmt.Printf("[wg-agent] write-back scheduled failed for %s: %s\n", item, detail)
		return
	}

	wt, branch, err := a.worktree(item)
	if err != nil {
		a.setStatus(item, "blocked", "worktree setup failed: "+err.Error())
		a.release(item)
		a.journalEvent("worktree_failed", map[string]any{"item_id": item, "error": err.Error()})
		fmt.Printf("[wg-agent] worktree failed for %s: %v\n", item, err)
		return
	}
	a.journalEvent("worktree", map[string]any{"item_id": item, "worktree": wt, "branch": branch})
	a.setStatus(item, "executing", fmt.Sprintf("agent run: worktree %s branch %s", wt, branch))

	exit, out, killed, leaseLost := a.runCommand(ctx, claim, wt, branch)
	switch {
	case leaseLost:
		a.setStatus(item, "queued", "lease lost mid-run (recovered); work kept at branch "+branch)
		a.journalEvent("lease_lost", map[string]any{"item_id": item, "branch": branch})
	case killed:
		a.setStatus(item, "queued", "agent interrupted; work kept at branch "+branch)
		a.journalEvent("interrupted", map[string]any{"item_id": item, "branch": branch})
	case exit == 0:
		a.setStatus(item, a.cfg.AgentSuccessStatus(),
			fmt.Sprintf("agent run ok exit=0 branch=%s worktree=%s", branch, wt))
	default:
		a.setStatus(item, "blocked", fmt.Sprintf("agent run failed exit=%d branch=%s tail=%s",
			exit, branch, lastLine(out)))
	}
	a.journalEvent("exec_end", map[string]any{"item_id": item, "exit": exit,
		"killed": killed, "lease_lost": leaseLost, "branch": branch})
	a.release(item)
}

// runCommand executes the runtime command template in the worktree, renewing the
// lease on a ticker until it finishes. leaseLost=true means the lease was gone
// at a renew tick (recovered by someone else) - the process is then killed.
func (a *Agent) runCommand(ctx context.Context, claim map[string]any, wt, branch string) (exit int, out string, killed bool, leaseLost bool) {
	item, _ := claim["item_id"].(string)
	tmpl := a.cfg.AgentRuntimeCommand(a.opt.Runtime)
	line := expand(tmpl, map[string]string{
		"item_id": item, "title": asText(claim["title"]), "worktree": wt,
		"branch": branch, "base_ref": a.cfg.AgentBaseRef(),
	})
	a.journalEvent("exec_start", map[string]any{"item_id": item, "command": line, "worktree": wt})

	// Windows: cmd /c mangles a command line whose first token is quoted (the
	// exe path); run it from a .cmd file instead (shell semantics preserved).
	var shell string
	var shellArgs []string
	if runtime.GOOS == "windows" {
		script := filepath.Join(a.cfg.StateDir(), "run-"+nonNameChars.ReplaceAllString(item, "_")+".cmd")
		if err := os.WriteFile(script, []byte("@echo off\r\n"+line+"\r\n"), 0o644); err != nil {
			a.journalEvent("exec_start_failed", map[string]any{"item_id": item, "error": err.Error()})
			return -1, err.Error(), false, false
		}
		shell, shellArgs = "cmd", []string{"/c", script}
	} else {
		shell, shellArgs = "/bin/sh", []string{"-c", line}
	}
	runCtx, cancel := withTimeout(ctx, a.cfg.Agent.TimeoutSeconds)
	defer cancel()
	cmd := exec.CommandContext(runCtx, shell, shellArgs...)
	cmd.Dir = wt
	cmd.Env = append(os.Environ(),
		"WG_ITEM_ID="+item, "WG_TITLE="+asText(claim["title"]), "WG_WORKTREE="+wt,
		"WG_BRANCH="+branch, "WG_BASE_REF="+a.cfg.AgentBaseRef(),
		"WG_WORKER_ID="+a.wid, "WG_RUNTIME="+a.opt.Runtime)
	var buf capWriter
	buf.limit = 64 << 10
	cmd.Stdout, cmd.Stderr = &buf, &buf

	done := make(chan error, 1)
	if err := cmd.Start(); err != nil {
		a.journalEvent("exec_start_failed", map[string]any{"item_id": item, "error": err.Error()})
		return -1, err.Error(), false, false
	}
	go func() { done <- cmd.Wait() }()

	beat := time.Duration(imax(2, a.cfg.LeaseTTL()/3)) * time.Second
	tick := time.NewTicker(beat)
	defer tick.Stop()
	for {
		select {
		case err := <-done:
			return exitCode(err), buf.String(), false, false
		case <-ctx.Done():
			killProc(cmd)
			<-done
			return -1, buf.String(), true, false
		case <-tick.C:
			_, _ = a.svc("POST", "/workers/"+a.wid+"/heartbeat", map[string]any{
				"status": "BUSY", "current_assignment": item})
			res, err := a.svc("POST", "/leases/"+item+"/renew", map[string]any{})
			if err == nil {
				if renewed, _ := res["renewed"].(bool); !renewed {
					killProc(cmd)
					<-done
					return -1, buf.String(), false, true
				}
			}
		}
	}
}

// worktree creates an isolated git worktree + branch off base_ref (IS-PF-0036:
// one working tree per execution session; the agent never touches the main
// checkout).
func (a *Agent) worktree(item string) (string, string, error) {
	repo := a.cfg.AgentRepoRoot()
	slug := nonNameChars.ReplaceAllString(strings.ToLower(item), "-")
	stamp := time.Now().UTC().Format("20060102-150405")
	branch := "wg/" + slug + "-" + stamp
	dir := filepath.Join(a.cfg.AgentWorktreesDir(), slug+"-"+stamp)
	if err := os.MkdirAll(filepath.Dir(dir), 0o755); err != nil {
		return "", "", err
	}
	cmd := exec.Command("git", "-C", repo, "worktree", "add", "-b", branch, dir, a.cfg.AgentBaseRef())
	if out, err := cmd.CombinedOutput(); err != nil {
		return "", "", fmt.Errorf("%v: %s", err, strings.TrimSpace(string(out)))
	}
	return dir, branch, nil
}

func (a *Agent) setStatus(item, status, note string) {
	ok, detail := producer.SetStatus(a.producer, a.token, a.opt.Scope, a.opt.Project, item, status, note)
	a.journalEvent("writeback", map[string]any{"item_id": item, "status": status, "ok": ok, "detail": detail})
	if !ok {
		fmt.Printf("[wg-agent] write-back %s failed for %s: %s\n", status, item, detail)
	}
}

func (a *Agent) release(item string) {
	_, err := a.svc("POST", "/leases/"+item+"/release", map[string]any{})
	a.journalEvent("release", map[string]any{"item_id": item, "ok": err == nil})
}

// ── helpers ──────────────────────────────────────────────────────────────────

func (a *Agent) journalEvent(event string, fields map[string]any) {
	if a.journal == nil {
		return
	}
	rec := map[string]any{"ts": time.Now().UTC().Format(time.RFC3339Nano), "event": event,
		"worker_id": a.wid}
	for k, v := range fields {
		rec[k] = v
	}
	raw, err := json.Marshal(rec)
	if err != nil {
		return
	}
	_, _ = a.journal.Write(append(raw, '\n'))
}

// expand substitutes {placeholders} with shell-quoted values.
func expand(tmpl string, vars map[string]string) string {
	out := tmpl
	for k, v := range vars {
		out = strings.ReplaceAll(out, "{"+k+"}", shellQuote(v))
	}
	return out
}

func shellQuote(v string) string {
	if runtime.GOOS == "windows" {
		return `"` + strings.ReplaceAll(v, `"`, `'`) + `"`
	}
	return "'" + strings.ReplaceAll(v, "'", `'\''`) + "'"
}

func asText(v any) string {
	if s, ok := v.(string); ok {
		return s
	}
	if v == nil {
		return ""
	}
	return fmt.Sprintf("%v", v)
}

func truthy(v any) bool {
	switch t := v.(type) {
	case nil:
		return false
	case bool:
		return t
	case string:
		return t != ""
	case float64:
		return t != 0
	case []any:
		return len(t) > 0
	case map[string]any:
		return len(t) > 0
	default:
		return true
	}
}

func withTimeout(parent context.Context, secs int) (context.Context, context.CancelFunc) {
	if secs > 0 {
		return context.WithTimeout(parent, time.Duration(secs)*time.Second)
	}
	return context.WithCancel(parent)
}

func exitCode(err error) int {
	if err == nil {
		return 0
	}
	var ee *exec.ExitError
	if errors.As(err, &ee) {
		return ee.ExitCode()
	}
	return -1
}

func lastLine(s string) string {
	lines := strings.Split(strings.TrimRight(s, "\r\n"), "\n")
	if len(lines) == 0 {
		return ""
	}
	return strings.TrimSpace(lines[len(lines)-1])
}

func imax(a, b int) int {
	if a > b {
		return a
	}
	return b
}

// capWriter retains the LAST `limit` bytes of execution output (error tails).
type capWriter struct {
	buf   []byte
	limit int
}

func (w *capWriter) Write(p []byte) (int, error) {
	w.buf = append(w.buf, p...)
	if w.limit > 0 && len(w.buf) > w.limit {
		w.buf = w.buf[len(w.buf)-w.limit:]
	}
	return len(p), nil
}

func (w *capWriter) String() string { return string(w.buf) }

// killProc kills the shell process. On Windows taskkill also reaps the tree.
func killProc(cmd *exec.Cmd) {
	if cmd == nil || cmd.Process == nil {
		return
	}
	if runtime.GOOS == "windows" {
		_ = exec.Command("taskkill", "/F", "/T", "/PID", fmt.Sprintf("%d", cmd.Process.Pid)).Run()
		return
	}
	_ = cmd.Process.Kill()
}
