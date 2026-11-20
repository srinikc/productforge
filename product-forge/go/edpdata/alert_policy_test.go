package edpdata

import (
	"context"
	"testing"
	"time"
)

func TestAlertRuleSeverity(t *testing.T) {
	if !SeverityAtLeast(SeverityCritical, SeverityHigh) {
		t.Fatalf("expected critical >= high")
	}
	if SeverityAtLeast(SeverityLow, SeverityHigh) {
		t.Fatalf("expected low < high")
	}
	if !SeverityAtLeast(SeverityMedium, SeverityMedium) {
		t.Fatalf("expected medium >= medium")
	}
	if ExtractSeverity("worker.panic") != SeverityCritical {
		t.Fatalf("expected panic to be critical")
	}
	if ExtractSeverity("build.error") != SeverityHigh {
		t.Fatalf("expected error to be high")
	}
}

func TestAlertPolicyEngine_RuleMatchingAndEscalation(t *testing.T) {
	ctx := context.Background()
	store := NewMemoryAlertStore()
	engine := NewAlertPolicyEngine(store)
	tenant := "test-tenant"

	rule := AlertRule{
		ID:                    "rule-1",
		TenantID:              tenant,
		Name:                  "Worker Critical Rule",
		EventTypes:            []string{"worker.*"},
		MinSeverity:           SeverityHigh,
		Channels:              []string{"notify", "hil"},
		ThrottleWindowSeconds: 60,
		Escalate:              true,
		EscalateChannel:       "hil",
		Enabled:               true,
	}
	if err := store.UpsertAlertRule(ctx, rule); err != nil {
		t.Fatalf("upsert rule failed: %v", err)
	}

	// 1. Matched with High severity
	ev1 := Event{
		TenantID:   tenant,
		EventID:    "ev-1",
		Type:       "worker.failed",
		OccurredAt: time.Now().UTC(),
	}
	dec1, err := engine.Evaluate(ctx, tenant, ev1, "job-123", SeverityHigh)
	if err != nil {
		t.Fatalf("unexpected eval error: %v", err)
	}
	if !dec1.Matched {
		t.Fatalf("expected rule to match")
	}
	if dec1.Suppressed {
		t.Fatalf("first event should not be suppressed")
	}
	if !dec1.Escalated || dec1.EscalateChannel != "hil" {
		t.Fatalf("expected escalation to hil")
	}
	if len(dec1.Channels) != 2 {
		t.Fatalf("expected 2 channels, got %v", dec1.Channels)
	}

	// 2. Suppressed within throttle window (same subject / fingerprint)
	ev2 := Event{
		TenantID:   tenant,
		EventID:    "ev-2",
		Type:       "worker.failed",
		OccurredAt: ev1.OccurredAt.Add(10 * time.Second),
	}
	dec2, err := engine.Evaluate(ctx, tenant, ev2, "job-123", SeverityHigh)
	if err != nil {
		t.Fatalf("unexpected eval error: %v", err)
	}
	if !dec2.Suppressed {
		t.Fatalf("expected event 2 to be suppressed by sliding throttle")
	}
	if dec2.SuppressedCount != 1 {
		t.Fatalf("expected suppressed count 1, got %d", dec2.SuppressedCount)
	}

	// 3. Different subject -> not suppressed
	ev3 := Event{
		TenantID:   tenant,
		EventID:    "ev-3",
		Type:       "worker.failed",
		OccurredAt: ev1.OccurredAt.Add(15 * time.Second),
	}
	dec3, err := engine.Evaluate(ctx, tenant, ev3, "job-999", SeverityHigh)
	if err != nil {
		t.Fatalf("unexpected eval error: %v", err)
	}
	if dec3.Suppressed {
		t.Fatalf("expected event 3 with different subject not to be suppressed")
	}

	// 4. Same subject after throttle window expiry -> emitted again
	ev4 := Event{
		TenantID:   tenant,
		EventID:    "ev-4",
		Type:       "worker.failed",
		OccurredAt: ev1.OccurredAt.Add(70 * time.Second),
	}
	dec4, err := engine.Evaluate(ctx, tenant, ev4, "job-123", SeverityHigh)
	if err != nil {
		t.Fatalf("unexpected eval error: %v", err)
	}
	if dec4.Suppressed {
		t.Fatalf("expected event 4 after 70s to reset throttle window")
	}
}

func TestAlertPolicyEngine_SeverityFilter(t *testing.T) {
	ctx := context.Background()
	store := NewMemoryAlertStore()
	engine := NewAlertPolicyEngine(store)
	tenant := "test-tenant"

	rule := AlertRule{
		ID:          "rule-high-only",
		TenantID:    tenant,
		Name:        "High Only",
		EventTypes:  []string{"deploy.*"},
		MinSeverity: SeverityHigh,
		Channels:    []string{"email"},
		Enabled:     true,
	}
	if err := store.UpsertAlertRule(ctx, rule); err != nil {
		t.Fatalf("upsert rule: %v", err)
	}

	// Low severity should not match
	evLow := Event{TenantID: tenant, Type: "deploy.progress", OccurredAt: time.Now()}
	decLow, err := engine.Evaluate(ctx, tenant, evLow, "", SeverityLow)
	if err != nil {
		t.Fatalf("eval error: %v", err)
	}
	if decLow.Matched {
		t.Fatalf("low severity event should not match high min_severity rule")
	}

	// High severity matches
	evHigh := Event{TenantID: tenant, Type: "deploy.failed", OccurredAt: time.Now()}
	decHigh, err := engine.Evaluate(ctx, tenant, evHigh, "", SeverityHigh)
	if err != nil {
		t.Fatalf("eval error: %v", err)
	}
	if !decHigh.Matched || len(decHigh.Channels) != 1 || decHigh.Channels[0] != "email" {
		t.Fatalf("expected high severity to match email rule, got %v", decHigh)
	}
}

func TestAlertPolicyEngine_FallbackPolicy(t *testing.T) {
	ctx := context.Background()
	// Empty store uses default fallback rules
	store := NewMemoryAlertStore()
	engine := NewAlertPolicyEngine(store)
	tenant := "default-tenant"

	// stuck -> notify
	evStuck := Event{TenantID: tenant, Type: "stuck", OccurredAt: time.Now()}
	decStuck, err := engine.Evaluate(ctx, tenant, evStuck, "task-1", SeverityMedium)
	if err != nil {
		t.Fatalf("eval error: %v", err)
	}
	if !decStuck.Matched || len(decStuck.Channels) != 1 || decStuck.Channels[0] != "notify" {
		t.Fatalf("expected stuck to route to notify fallback: %v", decStuck)
	}

	// compliance_exhausted -> hil, escalate=true
	evComp := Event{TenantID: tenant, Type: "compliance_exhausted", OccurredAt: time.Now()}
	decComp, err := engine.Evaluate(ctx, tenant, evComp, "task-1", SeverityHigh)
	if err != nil {
		t.Fatalf("eval error: %v", err)
	}
	if !decComp.Matched || !decComp.Escalated || decComp.EscalateChannel != "hil" {
		t.Fatalf("expected compliance_exhausted to escalate to hil: %v", decComp)
	}
}

func TestAlertPolicyEngine_EvaluateBatch(t *testing.T) {
	ctx := context.Background()
	engine := NewAlertPolicyEngine(nil) // in-memory with fallback
	tenant := "batch-tenant"

	events := []Event{
		{TenantID: tenant, EventID: "e1", Type: "stuck", OccurredAt: time.Now()},
		{TenantID: tenant, EventID: "e2", Type: "compliance_exhausted", OccurredAt: time.Now()},
	}

	decisions, err := engine.EvaluateBatch(ctx, tenant, events)
	if err != nil {
		t.Fatalf("batch eval failed: %v", err)
	}
	if len(decisions) != 2 {
		t.Fatalf("expected 2 decisions, got %d", len(decisions))
	}
	if !decisions[0].Matched || decisions[0].Channels[0] != "notify" {
		t.Fatalf("decision 0 mismatch: %v", decisions[0])
	}
	if !decisions[1].Matched || !decisions[1].Escalated {
		t.Fatalf("decision 1 mismatch: %v", decisions[1])
	}
}

func TestMemoryAlertStore_TTLCleanup(t *testing.T) {
	ctx := context.Background()
	store := NewMemoryAlertStore()
	tenant := "tenant-ttl"
	ruleID := "r-ttl"
	fp := "fp-test"
	now := time.Now()

	// Add throttle state with 10s window
	suppressed, _, err := store.CheckAndRecordThrottle(ctx, tenant, ruleID, fp, 10, now)
	if err != nil || suppressed {
		t.Fatalf("unexpected throttle: %v", err)
	}

	// Clean before expiry -> 0 pruned
	pruned := store.CleanupExpired(now.Add(5 * time.Second))
	if pruned != 0 {
		t.Fatalf("expected 0 pruned, got %d", pruned)
	}

	// Clean after expiry -> 1 pruned
	pruned = store.CleanupExpired(now.Add(15 * time.Second))
	if pruned != 1 {
		t.Fatalf("expected 1 pruned, got %d", pruned)
	}
}

func TestAlertStore_CRUD(t *testing.T) {
	ctx := context.Background()
	store := NewMemoryAlertStore()
	tenant := "t-crud"

	rule := AlertRule{
		ID:          "crud-1",
		TenantID:    tenant,
		Name:        "Test Rule",
		EventTypes:  []string{"*"},
		MinSeverity: SeverityLow,
		Channels:    []string{"notify"},
		Enabled:     true,
	}
	if err := store.UpsertAlertRule(ctx, rule); err != nil {
		t.Fatalf("upsert: %v", err)
	}

	rules, err := store.ListAlertRules(ctx, tenant)
	if err != nil || len(rules) != 1 {
		t.Fatalf("list rules failed: %v, count: %d", err, len(rules))
	}

	if err := store.DeleteAlertRule(ctx, tenant, "crud-1"); err != nil {
		t.Fatalf("delete: %v", err)
	}

	rulesAfter, err := store.ListAlertRules(ctx, tenant)
	if err != nil || len(rulesAfter) != 0 {
		t.Fatalf("expected empty rules after delete, got %d", len(rulesAfter))
	}
}
