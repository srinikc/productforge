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
