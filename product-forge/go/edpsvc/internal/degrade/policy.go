package degrade

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"sync"
	"time"
)

var (
	ErrDegraded        = errors.New("store degraded")
	ErrDegradedExpired = errors.New("store degradation expired")
)

// Rule is one bounded per-store degradation switch.
type Rule struct {
	Enabled   bool      `json:"enabled"`
	Reason    string    `json:"reason"`
	Owner     string    `json:"owner"`
	ExpiresAt time.Time `json:"expires_at"`
}

// Config is the operator-owned degradation document.
type Config struct {
	Version            int             `json:"version"`
	MaxDurationSeconds int             `json:"max_duration_seconds"`
	Stores             map[string]Rule `json:"stores"`
}

// Load reads and validates degradation configuration.
func Load(path string) (Config, error) {
	var c Config
	raw, err := os.ReadFile(path)
	if err != nil {
		return c, err
	}
	if err := json.Unmarshal(raw, &c); err != nil {
		return c, err
	}
	if c.Version < 1 || c.MaxDurationSeconds <= 0 || c.MaxDurationSeconds > 900 {
		return c, fmt.Errorf("degrade: invalid config")
	}
	for store, r := range c.Stores {
		if r.Enabled {
			if store == "" || r.Reason == "" || r.Owner == "" || r.ExpiresAt.IsZero() {
				return c, fmt.Errorf("degrade: %s requires reason, owner, expires_at", store)
			}
			if r.ExpiresAt.After(time.Now().Add(time.Duration(c.MaxDurationSeconds) * time.Second)) {
				return c, fmt.Errorf("degrade: %s expiry exceeds max_duration_seconds", store)
			}
		}
	}
	return c, nil
}

// Checker is the shared degradation check contract.
type Checker interface {
	Check(store string, now time.Time) error
}

// Policy reloads the config when the file changes and counts renewals per store.
type Policy struct {
	mu       sync.Mutex
	path     string
	cfg      Config
	mod      time.Time
	renewals map[string]int
}

func NewPolicy(path string) (*Policy, error) {
	c, err := Load(path)
	if err != nil {
		return nil, err
	}
	st, _ := os.Stat(path)
	p := &Policy{path: path, cfg: c, renewals: map[string]int{}}
	if st != nil {
		p.mod = st.ModTime()
	}
	return p, nil
}

func (p *Policy) reload() {
	st, err := os.Stat(p.path)
	if err != nil || !st.ModTime().After(p.mod) {
		return
	}
	c, err := Load(p.path)
	if err != nil {
		return
	}
	for store, old := range p.cfg.Stores {
		if nr, ok := c.Stores[store]; ok && old.Enabled && nr.Enabled && nr.ExpiresAt.After(old.ExpiresAt) {
			p.renewals[store]++
		}
	}
	p.cfg = c
	p.mod = st.ModTime()
}

func (p *Policy) Check(store string, now time.Time) error {
	p.mu.Lock()
	defer p.mu.Unlock()
	p.reload()
	if p.renewals[store] > 3 {
		return ErrDegradedExpired
	}
	return p.cfg.Check(store, now)
}

func (p *Policy) RenewalCount(store string) int {
	p.mu.Lock()
	defer p.mu.Unlock()
	return p.renewals[store]
}

// Check returns ErrDegraded while a valid switch is active, or ErrDegradedExpired for a stale switch.
func (c Config) Check(store string, now time.Time) error {
	r, ok := c.Stores[store]
	if !ok || !r.Enabled {
		return nil
	}
	if r.ExpiresAt.IsZero() || !now.Before(r.ExpiresAt) {
		return ErrDegradedExpired
	}
	return fmt.Errorf("%w: %s", ErrDegraded, r.Reason)
}
