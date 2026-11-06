package degrade

import (
	"errors"
	"testing"
	"time"
)

func TestCheckActiveAndExpired(t *testing.T) {
	now := time.Now()
	c := Config{Version: 1, MaxDurationSeconds: 900, Stores: map[string]Rule{
		"db":    {Enabled: true, Reason: "schema lock", Owner: "ops", ExpiresAt: now.Add(time.Minute)},
		"cache": {Enabled: true, Reason: "eviction", Owner: "ops", ExpiresAt: now.Add(-time.Minute)},
	}}
	if err := c.Check("db", now); !errors.Is(err, ErrDegraded) {
		t.Fatalf("want degraded, got %v", err)
	}
	if err := c.Check("cache", now); !errors.Is(err, ErrDegradedExpired) {
		t.Fatalf("want expired, got %v", err)
	}
	if err := c.Check("queue", now); err != nil {
		t.Fatalf("unexpected: %v", err)
	}
}

func TestPolicyRenewalLimitFailsClosed(t *testing.T) {
	p := &Policy{cfg: Config{Version: 1, MaxDurationSeconds: 900, RenewalLimit: 1, RenewalWindowSeconds: 60,
		Stores: map[string]Rule{"db": {Enabled: true, Reason: "x", Owner: "ops", ExpiresAt: time.Now().Add(time.Minute)}}},
		renewals: map[string][]time.Time{"db": {time.Now(), time.Now()}}}
	if err := p.Check("db", time.Now()); !errors.Is(err, ErrRenewalExceeded) {
		t.Fatalf("want renewal exceeded, got %v", err)
	}
}

func TestPolicyWindowPrunesWithoutConfigReload(t *testing.T) {
	now := time.Now()
	p := &Policy{cfg: Config{Version: 1, MaxDurationSeconds: 900, RenewalLimit: 1, RenewalWindowSeconds: 60,
		Stores: map[string]Rule{"db": {Enabled: true, Reason: "x", Owner: "ops", ExpiresAt: now.Add(time.Minute)}}},
		renewals: map[string][]time.Time{"db": {now.Add(-30 * time.Second), now}}}
	if err := p.Check("db", now); !errors.Is(err, ErrRenewalExceeded) {
		t.Fatalf("want renewal exceeded, got %v", err)
	}
	p.renewals["db"] = []time.Time{now.Add(-2 * time.Minute)}
	if err := p.Check("db", now); !errors.Is(err, ErrDegraded) {
		t.Fatalf("stale renewal should prune to active-degraded, got %v", err)
	}
}
