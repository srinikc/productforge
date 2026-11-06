package degrade

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"productforge/edpsvc/internal/limits"
	"sync"
	"time"
)

var (
	ErrDegraded        = errors.New("store degraded")
	ErrDegradedExpired = errors.New("store degradation expired")
	ErrRenewalExceeded = errors.New("store degradation renewal exceeded")
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
	Version              int             `json:"version"`
	MaxDurationSeconds   int             `json:"max_duration_seconds"`
	RenewalLimit         int             `json:"renewal_limit"`
	RenewalWindowSeconds int             `json:"renewal_window_seconds"`
	Stores               map[string]Rule `json:"stores"`
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
	if c.Version < 1 || c.MaxDurationSeconds <= 0 || c.MaxDurationSeconds > 900 ||
		c.RenewalLimit < 1 || c.RenewalWindowSeconds < 60 {
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
	renewals map[string][]time.Time
	Metrics  *limits.Metrics
}

func NewPolicy(path string) (*Policy, error) {
	c, err := Load(path)
	if err != nil {
		return nil, err
	}
	st, _ := os.Stat(path)
	p := &Policy{path: path, cfg: c, renewals: map[string][]time.Time{}}
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
	now := time.Now()
	for store, old := range p.cfg.Stores {
		nr, ok := c.Stores[store]
		if !ok || !nr.Enabled {
			continue
		}
		if old.Enabled && nr.Enabled && nr.ExpiresAt.After(old.ExpiresAt) {
			cutoff := now.Add(-time.Duration(c.RenewalWindowSeconds) * time.Second)
			kept := p.renewals[store][:0]
			for _, at := range p.renewals[store] {
				if at.After(cutoff) {
					kept = append(kept, at)
				}
			}
			p.renewals[store] = append(kept, now)
			if p.Metrics != nil {
				p.Metrics.Inc("edp_store_degradation_renewals_total", "store", store)
			}
		}
	}
	p.cfg = c
	p.mod = st.ModTime()
}

func (p *Policy) Check(store string, now time.Time) error {
	p.mu.Lock()
	defer p.mu.Unlock()
	p.reload()
	cutoff := now.Add(-time.Duration(p.cfg.RenewalWindowSeconds) * time.Second)
	kept := make([]time.Time, 0, len(p.renewals[store]))
	for _, at := range p.renewals[store] {
		if at.After(cutoff) {
			kept = append(kept, at)
		}
	}
	p.renewals[store] = kept
	if len(kept) > p.cfg.RenewalLimit {
		return ErrRenewalExceeded
	}
	return p.cfg.Check(store, now)
}

func (p *Policy) RenewalCount(store string) int {
	p.mu.Lock()
	defer p.mu.Unlock()
	return len(p.renewals[store])
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
