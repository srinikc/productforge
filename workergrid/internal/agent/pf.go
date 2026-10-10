// BI-PF-0423: the PF-assignment contract - WorkerGrid as a THIN client of Product Forge.
//
// When the contract is "pf-assignments" the agent does NOT run a coordinator, create a worktree, hold a lease,
// or write status back itself. It calls PF's assignment lifecycle:
//
//	POST /engineering/assignments/claim        -> package {item_id, worktree, branch, base_ref, pidl_context,
//	                                                    execution_policy, acceptance_criteria, ...}
//	  write  <worktree>/.wg/assignment.json    (the package, for the runtime to read)
//	  run the runtime command in <worktree>    (cwd = the PF-made worktree)
//	POST /engineering/assignments/{id}/heartbeat
//	POST /engineering/assignments/{id}/complete | /fail
//
// PF owns the lease/worktree/delivery (BI-PF-0419/0421); the coordinator contract remains the fallback.
package agent

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"time"
)

const pfAssignmentsView = "/api/v1/engineering/assignments"

// pfAssignmentsAvailable probes the PF assignment view (BI-PF-0422) for contract auto-selection.
func (a *Agent) pfAssignmentsAvailable() bool {
	st, _, err := a.pf("GET", pfAssignmentsView+"?scope=product_forge", nil)
	return err == nil && st >= 200 && st < 300
}

// pf calls the producer API and returns (status, parsed-envelope, err). X-Roles worker+operator covers both the
// worker- and operator-guarded endpoints. A 4xx is an error (returned with the status).
func (a *Agent) pf(method, path string, body map[string]any) (int, map[string]any, error) {
	var rdr io.Reader
	if body != nil {
		raw, _ := json.Marshal(body)
		rdr = bytes.NewReader(raw)
	}
	req, err := http.NewRequest(method, a.pfBase+path, rdr)
	if err != nil {
		return 0, nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Roles", "worker,operator")
	if a.token != "" {
		req.Header.Set("Authorization", "Bearer "+a.token)
	}
	resp, err := a.client.Do(req)
	if err != nil {
		return 0, nil, err
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(io.LimitReader(resp.Body, 4<<20))
	var out map[string]any
	_ = json.Unmarshal(raw, &out)
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return resp.StatusCode, out, fmt.Errorf("%s %s -> %d", method, path, resp.StatusCode)
	}
	return resp.StatusCode, out, nil
}

// pfData unwraps the PF envelope {request_id,status,data:{...}} one level.
func pfData(body map[string]any) map[string]any {
	if body == nil {
		return map[string]any{}
	}
	if d, ok := body["data"].(map[string]any); ok {
		return d
	}
	return body
}

func (a *Agent) runPF(ctx context.Context) error {
	wid := a.opt.WorkerID
	if wid == "" {
		wid = fmt.Sprintf("WG-%s-%d", nonNameChars.ReplaceAllString(a.opt.Runtime, ""), time.Now().Unix()%100000000)
	}
	poll := time.Duration(a.cfg.AgentPoll()) * time.Second
	for {
		if ctx.Err() != nil {
			a.journalEvent("agent_stop", map[string]any{"reason": "signal"})
			return nil
		}
		// best-effort: free expired leases so a dead worker's item becomes claimable again
		_, _, _ = a.pf("POST", pfAssignmentsView+"/recover",
			map[string]any{"scope": a.opt.Scope, "project": a.opt.Project})

		_, raw, err := a.pf("POST", pfAssignmentsView+"/claim",
			map[string]any{"scope": a.opt.Scope, "project": a.opt.Project, "worker_id": wid,
				"epic": a.opt.Epic})
		if err != nil {
			fmt.Printf("[wg-agent] claim error: %v\n", err)
			if a.opt.Once {
				return err
			}
			if !sleepCtx(ctx, poll) {
				return nil
			}
			continue
		}
		pkg := pfData(raw)
		if assigned, _ := pkg["assigned"].(bool); !assigned {
			reason, _ := pkg["reason"].(string)
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
		a.executePF(ctx, wid, pkg)
		if a.opt.Once {
			a.journalEvent("agent_stop", map[string]any{"reason": "once_done"})
			return nil
		}
	}
}

func (a *Agent) executePF(ctx context.Context, wid string, pkg map[string]any) {
	item := asText(pkg["item_id"])
	title := asText(pkg["title"])
	wt := asText(pkg["worktree"])
	branch := asText(pkg["branch"])
	baseRef := asText(pkg["base_ref"])
	a.journalEvent("claim", map[string]any{"item_id": item, "title": title, "worktree": wt, "branch": branch})

	// PIDL approval gate: never execute work that requires approval (fail-closed).
	if pol, ok := pkg["execution_policy"].(map[string]any); ok && truthy(pol["approval_required"]) {
		a.pfOutcome(item, "fail", "execution_policy.approval_required - not executed")
		a.journalEvent("rejected", map[string]any{"item_id": item})
		return
	}
	if wt == "" {
		a.pfOutcome(item, "fail", "no worktree in the assignment package")
		return
	}
	a.writeManifest(wt, pkg)

	exit, out, killed, leaseLost := a.runRuntimePF(ctx, wid, item, title, wt, branch, baseRef)
	switch {
	case leaseLost:
		a.journalEvent("lease_lost", map[string]any{"item_id": item}) // PF recovers the lease
	case killed:
		a.pfOutcome(item, "fail", "agent interrupted")
	case exit == 0:
		a.pfOutcome(item, "complete", "")
	default:
		a.pfOutcome(item, "fail", fmt.Sprintf("exit=%d %s", exit, lastLine(out)))
	}
	a.journalEvent("exec_end", map[string]any{"item_id": item, "exit": exit, "killed": killed, "lease_lost": leaseLost})
}

// pfOutcome posts complete/fail for the item (best-effort; the journal already records the local result).
func (a *Agent) pfOutcome(item, kind, reason string) {
	body := map[string]any{"scope": a.opt.Scope, "project": a.opt.Project}
	if kind == "fail" {
		body["reason"] = reason
	}
	_, _, err := a.pf("POST", pfAssignmentsView+"/"+item+"/"+kind, body)
	a.journalEvent("pf_"+kind, map[string]any{"item_id": item, "ok": err == nil})
}

func (a *Agent) writeManifest(wt string, pkg map[string]any) {
	dir := filepath.Join(wt, ".wg")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return
	}
	if raw, err := json.MarshalIndent(pkg, "", "  "); err == nil {
		_ = os.WriteFile(filepath.Join(dir, "assignment.json"), raw, 0o644)
	}
}

// runRuntimePF runs the runtime command in the PF-made worktree, heart-beating the item via PF until it ends.
func (a *Agent) runRuntimePF(ctx context.Context, wid, item, title, wt, branch, baseRef string) (exit int, out string, killed, leaseLost bool) {
	tmpl := a.cfg.AgentRuntimeCommand(a.opt.Runtime)
	line := expand(tmpl, map[string]string{
		"item_id": item, "title": title, "worktree": wt, "branch": branch, "base_ref": baseRef,
	})
	a.journalEvent("exec_start", map[string]any{"item_id": item, "command": line, "worktree": wt})

	shell, shellArgs := shellFor(line)
	runCtx, cancel := withTimeout(ctx, a.cfg.Agent.TimeoutSeconds)
	defer cancel()
	cmd := exec.CommandContext(runCtx, shell, shellArgs...)
	cmd.Dir = wt
	cmd.Env = append(os.Environ(),
		"WG_ITEM_ID="+item, "WG_TITLE="+title, "WG_WORKTREE="+wt,
		"WG_BRANCH="+branch, "WG_BASE_REF="+baseRef, "WG_WORKER_ID="+wid, "WG_RUNTIME="+a.opt.Runtime,
		"WG_ASSIGNMENT="+filepath.Join(wt, ".wg", "assignment.json"))
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
			st, _, err := a.pf("POST", pfAssignmentsView+"/"+item+"/heartbeat",
				map[string]any{"scope": a.opt.Scope, "project": a.opt.Project})
			if err != nil && st == http.StatusNotFound { // lease gone / item reclaimed
				killProc(cmd)
				<-done
				return -1, buf.String(), false, true
			}
		}
	}
}

// shellFor builds the shell invocation for a command line (Windows: a .cmd file to avoid cmd /c quoting).
func shellFor(line string) (string, []string) {
	if runtime.GOOS == "windows" {
		f := filepath.Join(os.TempDir(), fmt.Sprintf("wg-pf-%d.cmd", time.Now().UnixNano()))
		_ = os.WriteFile(f, []byte("@echo off\r\n"+line+"\r\n"), 0o644)
		return "cmd", []string{"/c", f}
	}
	return "/bin/sh", []string{"-c", line}
}
