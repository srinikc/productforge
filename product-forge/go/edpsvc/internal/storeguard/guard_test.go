package storeguard

import (
	"errors"
	"strings"
	"testing"
	"time"

	"productforge/edpsvc/internal/degrade"
	"productforge/edpsvc/internal/limits"
	"productforge/edpsvc/internal/observe"
)

func TestGuardRecordsAllowedStoreCalls(t *testing.T) {
	m := limits.NewMetrics()
	cfg := limits.DefaultConfig()
	cfg.TenantRPM = 10
	q := limits.NewQuota(cfg, nil, m)
	g := &Guard{Quota: q, Degrade: degrade.Config{Version: 1, MaxDurationSeconds: 900}, Metrics: observe.Recorder{M: m}, Meter: m}
	for _, store := range []string{"db", "object", "cache", "queue"} {
		if err := g.Do(store, "t1", func() error { return nil }); err != nil {
			t.Fatal(err)
		}
	}
	var b strings.Builder
	m.Write(&b)
	if !strings.Contains(b.String(), `store="queue"`) {
		t.Fatalf("store metrics missing: %s", b.String())
	}
}

func TestGuardFailsClosedOnDegradationAndQuota(t *testing.T) {
	m := limits.NewMetrics()
	cfg := limits.DefaultConfig()
	cfg.TenantRPM = 1
	q := limits.NewQuota(cfg, func() time.Time { return time.Unix(100, 0) }, m)
	g := &Guard{Quota: q, Degrade: degrade.Config{Version: 1, MaxDurationSeconds: 900, Stores: map[string]degrade.Rule{
		"db": {Enabled: true, Reason: "maintenance", Owner: "ops", ExpiresAt: time.Unix(200, 0)},
	}}, Metrics: observe.Recorder{M: m}, Now: func() time.Time { return time.Unix(100, 0) }}
	if err := g.Do("db", "t1", func() error { return nil }); !errors.Is(err, degrade.ErrDegraded) {
		t.Fatalf("want degraded, got %v", err)
	}
	if err := g.Do("cache", "t1", func() error { return nil }); err != nil {
		t.Fatal(err)
	}
	if err := g.Do("cache", "t1", func() error { return nil }); !errors.Is(err, ErrQuota) {
		t.Fatalf("want quota denial, got %v", err)
	}
}
