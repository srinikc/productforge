// Package config loads WorkerGrid's config.json with the same env overrides
// and precedence as the Python spike (_cfg.py / client.py): live reads on every
// call so operators can edit config while the service runs.
package config

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

// Config mirrors workergrid/config.json (only the keys the coordinator/agent use).
type Config struct {
	PfApiURL     string `json:"pf_api_url"`
	TokenEnv     string `json:"token_env"`
	LeaseSeconds int    `json:"lease_seconds"`
	ServiceHost  string `json:"service_host"`
	ServicePort  int    `json:"service_port"`
	ServiceURL   string `json:"service_url"`
	StateDirName string `json:"state_dir"`
	PollSeconds  int    `json:"poll_seconds"`
	Store        Store  `json:"store"`
	Agent        Agent  `json:"agent"`
}

// Store selects the coordination-store backend (BI-PF-0414): SQLite (default,
// single-node) or PostgreSQL (multi-node). Driver "" = sqlite; DSN "" =
// <state_dir>/workergrid.db for sqlite, and is REQUIRED for postgres.
type Store struct {
	Driver string `json:"driver"`
	DSN    string `json:"dsn"`
}

// Agent is the `agent` block of config.json (Stage 3c, BI-PF-0413): the worker
// agent's execution settings. Commands are per-runtime templates; placeholders
// {item_id} {title} {worktree} {branch} {base_ref} are substituted with
// shell-quoted values (the command runs through cmd /c on Windows, sh -c else)
// and exported as env vars (WG_ITEM_ID, WG_TITLE, WG_WORKTREE, WG_BRANCH,
// WG_BASE_REF, WG_WORKER_ID, WG_RUNTIME).
type Agent struct {
	RepoRoot       string                `json:"repo_root"`
	BaseRef        string                `json:"base_ref"`
	WorktreesDir   string                `json:"worktrees_dir"`
	TimeoutSeconds int                   `json:"timeout_seconds"`
	SuccessStatus  string                `json:"success_status"`
	PollSeconds    int                   `json:"poll_seconds"`
	Runtimes       map[string]RuntimeCmd `json:"runtimes"`
}

// RuntimeCmd is one runtime's command template under agent.runtimes.
type RuntimeCmd struct {
	Command string `json:"command"`
}

// Home resolves the WorkerGrid directory (where config.json lives):
// $WORKERGRID_HOME > nearest config.json above the executable > above cwd.
func Home() string {
	if h := os.Getenv("WORKERGRID_HOME"); h != "" {
		return h
	}
	if exe, err := os.Executable(); err == nil {
		if dir := walkForConfig(filepath.Dir(exe)); dir != "" {
			return dir
		}
	}
	if cwd, err := os.Getwd(); err == nil {
		if dir := walkForConfig(cwd); dir != "" {
			return dir
		}
	}
	return "."
}

func walkForConfig(start string) string {
	dir := start
	for i := 0; i < 8; i++ {
		if _, err := os.Stat(filepath.Join(dir, "config.json")); err == nil {
			return dir
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	return ""
}

// Load reads config.json from Home() (every call, like Python's _cfg.load()).
func Load() Config {
	c := Config{}
	raw, err := os.ReadFile(filepath.Join(Home(), "config.json"))
	if err != nil {
		return c
	}
	_ = json.Unmarshal(raw, &c)
	return c
}

// StateDir: $WORKERGRID_STATE_DIR > config state_dir (relative to Home) > Home/state.
// The directory is created on demand, mirroring _cfg.state_dir().
func (c Config) StateDir() string {
	d := os.Getenv("WORKERGRID_STATE_DIR")
	if d == "" {
		d = c.StateDirName
		if d == "" {
			d = "state"
		}
		if !filepath.IsAbs(d) {
			d = filepath.Join(Home(), d)
		}
	}
	_ = os.MkdirAll(d, 0o755)
	return d
}

// ProducerBase: $WORKERGRID_PF_API_URL > config pf_api_url > http://127.0.0.1:8000
// (trailing "/" trimmed, like client._base()).
func (c Config) ProducerBase() string {
	b := os.Getenv("WORKERGRID_PF_API_URL")
	if b == "" {
		b = c.PfApiURL
	}
	if b == "" {
		b = "http://127.0.0.1:8000"
	}
	for len(b) > 0 && b[len(b)-1] == '/' {
		b = b[:len(b)-1]
	}
	return b
}

// Token: $<config token_env> (default API_TOKEN) > $WORKERGRID_TOKEN, else "".
func (c Config) Token() string {
	env := c.TokenEnv
	if env == "" {
		env = "API_TOKEN"
	}
	if t := os.Getenv(env); t != "" {
		return t
	}
	return os.Getenv("WORKERGRID_TOKEN")
}

// LeaseSeconds: $WORKERGRID_LEASE_SECONDS > config lease_seconds > 3600.
func (c Config) LeaseTTL() int {
	if v := os.Getenv("WORKERGRID_LEASE_SECONDS"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	if c.LeaseSeconds > 0 {
		return c.LeaseSeconds
	}
	return 3600
}

// StoreDriver: $WORKERGRID_STORE_DRIVER > config store.driver > "sqlite".
func (c Config) StoreDriver() string {
	if v := strings.TrimSpace(os.Getenv("WORKERGRID_STORE_DRIVER")); v != "" {
		return v
	}
	return strings.TrimSpace(c.Store.Driver)
}

// StoreDSN: $WORKERGRID_STORE_DSN > config store.dsn > <state_dir>/workergrid.db
// (the SQLite default). Empty for postgres without an explicit DSN - the
// coordinator reports that fail-closed.
func (c Config) StoreDSN() string {
	if v := strings.TrimSpace(os.Getenv("WORKERGRID_STORE_DSN")); v != "" {
		return v
	}
	if v := strings.TrimSpace(c.Store.DSN); v != "" {
		return v
	}
	d := strings.ToLower(c.StoreDriver())
	if d == "" || d == "sqlite" || d == "sqlite3" {
		return filepath.Join(c.StateDir(), "workergrid.db")
	}
	return ""
}

// ServiceBase: config service_url > http://service_host:service_port (same
// precedence as client.service_url(); trailing "/" trimmed).
func (c Config) ServiceBase() string {
	if u := strings.TrimSpace(c.ServiceURL); u != "" {
		return strings.TrimRight(u, "/")
	}
	host := c.ServiceHost
	if host == "" {
		host = "127.0.0.1"
	}
	port := c.ServicePort
	if port == 0 {
		port = 8790
	}
	return fmt.Sprintf("http://%s:%d", host, port)
}

// AgentRuntimeCommand: agent.runtimes[name].command ("" when unset).
func (c Config) AgentRuntimeCommand(name string) string {
	return strings.TrimSpace(c.Agent.Runtimes[name].Command)
}

// AgentPoll: agent.poll_seconds > config poll_seconds > 5 (seconds).
func (c Config) AgentPoll() int {
	if c.Agent.PollSeconds > 0 {
		return c.Agent.PollSeconds
	}
	if c.PollSeconds > 0 {
		return c.PollSeconds
	}
	return 5
}

// AgentWorktreesDir: agent.worktrees_dir (default "worktrees") relative to
// Home unless absolute; created on demand.
func (c Config) AgentWorktreesDir() string {
	d := strings.TrimSpace(c.Agent.WorktreesDir)
	if d == "" {
		d = "worktrees"
	}
	if !filepath.IsAbs(d) {
		d = filepath.Join(Home(), d)
	}
	_ = os.MkdirAll(d, 0o755)
	return d
}

// AgentBaseRef: agent.base_ref > "develop" (worktree branch base).
func (c Config) AgentBaseRef() string {
	if r := strings.TrimSpace(c.Agent.BaseRef); r != "" {
		return r
	}
	return "develop"
}

// AgentSuccessStatus: agent.success_status > "verifying" (the PF status an
// exit-0 run writes back - default keeps DoD/gates in the human path).
func (c Config) AgentSuccessStatus() string {
	if s := strings.TrimSpace(c.Agent.SuccessStatus); s != "" {
		return s
	}
	return "verifying"
}

// AgentRepoRoot: agent.repo_root (absolute or relative to Home); "" when unset.
func (c Config) AgentRepoRoot() string {
	r := strings.TrimSpace(c.Agent.RepoRoot)
	if r == "" {
		return ""
	}
	if !filepath.IsAbs(r) {
		r = filepath.Join(Home(), r)
	}
	return r
}
