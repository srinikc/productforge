// Package config loads WorkerGrid's config.json with the same env overrides
// and precedence as the Python spike (_cfg.py / client.py): live reads on every
// call so operators can edit config while the service runs.
package config

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strconv"
)

// Config mirrors workergrid/config.json (only the keys the coordinator uses).
type Config struct {
	PfApiURL     string `json:"pf_api_url"`
	TokenEnv     string `json:"token_env"`
	LeaseSeconds int    `json:"lease_seconds"`
	ServiceHost  string `json:"service_host"`
	ServicePort  int    `json:"service_port"`
	StateDirName string `json:"state_dir"`
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
