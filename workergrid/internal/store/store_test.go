package store

import (
	"strings"
	"testing"
)

func openTest(t *testing.T, ttl func() int) *Store {
	t.Helper()
	s, err := Open(t.TempDir(), ttl)
	if err != nil {
		t.Fatalf("open: %v", err)
	}
	t.Cleanup(func() { _ = s.Close() })
	return s
}

func TestRegisterUpsertKeepsRegisteredAt(t *testing.T) {
	s := openTest(t, func() int { return 3600 })
	w, err := s.Register("WRK-t1", "opencode", []string{"python", "go"}, "dev")
	if err != nil {
		t.Fatalf("register: %v", err)
	}
	if w.Status != "ONLINE" || w.Capabilities != "python,go" {
		t.Fatalf("unexpected worker: %+v", w)
	}
	first := w.RegisteredAt
	if _, err := s.Heartbeat("WRK-t1", "BUSY", "BI-X"); err != nil {
		t.Fatalf("heartbeat: %v", err)
	}
	w2, err := s.Register("WRK-t1", "opencode", []string{"go"}, "dev")
	if err != nil {
		t.Fatalf("re-register: %v", err)
	}
	if w2.RegisteredAt != first {
		t.Fatalf("registered_at changed on upsert: %v -> %v", first, w2.RegisteredAt)
	}
	if w2.Status != "ONLINE" || w2.Capabilities != "go" {
		t.Fatalf("upsert did not refresh: %+v", w2)
	}
}

func TestClaimConflictRelease(t *testing.T) {
	s := openTest(t, func() int { return 3600 })
	if _, err := s.Register("WRK-a", "opencode", nil, ""); err != nil {
		t.Fatal(err)
	}
	if _, err := s.Register("WRK-b", "opencode", nil, ""); err != nil {
		t.Fatal(err)
	}
	c1, err := s.Claim("BI-T", "WRK-a", "opencode")
	if err != nil || c1["claimed"] != true {
		t.Fatalf("first claim: %v %v", c1, err)
	}
	c2, err := s.Claim("BI-T", "WRK-b", "opencode")
	if err != nil {
		t.Fatal(err)
	}
	if c2["claimed"] != false {
		t.Fatalf("second claim must be denied: %v", c2)
	}
	if reason, _ := c2["reason"].(string); !strings.Contains(reason, "already leased by WRK-a") {
		t.Fatalf("reason = %q", reason)
	}
	if _, err := s.Release("BI-T"); err != nil {
		t.Fatal(err)
	}
	if w, _ := s.Get("WRK-a"); w == nil || w.Status != "IDLE" || w.CurrentAssignment != "" {
		t.Fatalf("release must free the worker: %+v", w)
	}
	c3, err := s.Claim("BI-T", "WRK-b", "opencode")
	if err != nil || c3["claimed"] != true {
		t.Fatalf("claim after release: %v %v", c3, err)
	}
	if w, _ := s.Get("WRK-b"); w == nil || w.Status != "BUSY" || w.CurrentAssignment != "BI-T" {
		t.Fatalf("claiming worker must be BUSY: %+v", w)
	}
}

func TestRecoverExpired(t *testing.T) {
	s := openTest(t, func() int { return -1 }) // lease expires immediately
	if _, err := s.Register("WRK-e", "opencode", nil, ""); err != nil {
		t.Fatal(err)
	}
	if c, err := s.Claim("BI-E", "WRK-e", "opencode"); err != nil || c["claimed"] != true {
		t.Fatalf("claim: %v %v", c, err)
	}
	res, err := s.RecoverExpired()
	if err != nil {
		t.Fatal(err)
	}
	if res["count"] != 1 {
		t.Fatalf("recover = %v", res)
	}
	if got := res["recovered"].([]string); len(got) != 1 || got[0] != "BI-E" {
		t.Fatalf("recovered = %v", got)
	}
	if leases, _ := s.ListLeases(); len(leases) != 0 {
		t.Fatalf("lease must be gone: %v", leases)
	}
	if w, _ := s.Get("WRK-e"); w == nil || w.Status != "IDLE" {
		t.Fatalf("worker must be IDLE after recover: %+v", w)
	}
}

func TestHeartbeatAndUnregisterShapes(t *testing.T) {
	s := openTest(t, func() int { return 3600 })
	h, err := s.Heartbeat("nope", "", "")
	if err != nil || h["ok"] != false || h["reason"] != "unknown worker" {
		t.Fatalf("unknown heartbeat: %v %v", h, err)
	}
	if _, err := s.Register("WRK-h", "opencode", nil, ""); err != nil {
		t.Fatal(err)
	}
	if h, err := s.Heartbeat("WRK-h", "", ""); err != nil || h["ok"] != true || h["worker_id"] != "WRK-h" {
		t.Fatalf("heartbeat: %v %v", h, err)
	}
	if u, err := s.Unregister("WRK-h"); err != nil || u["removed"] != true {
		t.Fatalf("unregister: %v %v", u, err)
	}
	if u, err := s.Unregister("WRK-h"); err != nil || u["removed"] != false {
		t.Fatalf("double unregister: %v %v", u, err)
	}
}
