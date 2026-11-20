package edpdata

import (
	"context"
	"log"
	"strings"
	"time"
)

// DefaultFallbackRules provides baseline alert routing matching orchestration_context._POLICY
// when no custom rules are configured or when database lookup fails.
func DefaultFallbackRules(tenant string) []AlertRule {
	now := time.Now().UTC()
	return []AlertRule{
		{
			ID: "default-compliance-exhausted", TenantID: tenant, Name: "Compliance Exhausted Fallback",
			EventTypes: []string{"compliance_exhausted", "*.compliance_exhausted"}, MinSeverity: SeverityHigh,
			Channels: []string{"hil"}, Escalate: true, EscalateChannel: "hil", Enabled: true, CreatedAt: now, UpdatedAt: now,
		},
		{
			ID: "default-agent-conflict", TenantID: tenant, Name: "Agent Conflict Fallback",
			EventTypes: []string{"agent_conflict", "*.agent_conflict"}, MinSeverity: SeverityHigh,
			Channels: []string{"hil"}, Escalate: true, EscalateChannel: "hil", Enabled: true, CreatedAt: now, UpdatedAt: now,
		},
		{
			ID: "default-scope-change", TenantID: tenant, Name: "Scope Change Fallback",
			EventTypes: []string{"scope_change", "*.scope_change"}, MinSeverity: SeverityMedium,
			Channels: []string{"hil"}, Escalate: true, EscalateChannel: "hil", Enabled: true, CreatedAt: now, UpdatedAt: now,
		},
		{
			ID: "default-escalation", TenantID: tenant, Name: "Escalation Fallback",
			EventTypes: []string{"escalation", "*.escalation"}, MinSeverity: SeverityHigh,
			Channels: []string{"hil"}, Escalate: true, EscalateChannel: "hil", Enabled: true, CreatedAt: now, UpdatedAt: now,
		},
		{
			ID: "default-follow-up", TenantID: tenant, Name: "Follow Up Due Fallback",
			EventTypes: []string{"follow_up_due", "*.follow_up_due"}, MinSeverity: SeverityLow,
			Channels: []string{"backlog"}, Escalate: false, Enabled: true, CreatedAt: now, UpdatedAt: now,
		},
		{
			ID: "default-stuck", TenantID: tenant, Name: "Stuck Fallback",
			EventTypes: []string{"stuck", "*.stuck"}, MinSeverity: SeverityMedium,
			Channels: []string{"notify"}, Escalate: false, Enabled: true, CreatedAt: now, UpdatedAt: now,
		},
		{
			ID: "default-anomaly", TenantID: tenant, Name: "Anomaly Fallback",
			EventTypes: []string{"anomaly", "*.anomaly"}, MinSeverity: SeverityMedium,
			Channels: []string{"notify"}, Escalate: false, Enabled: true, CreatedAt: now, UpdatedAt: now,
		},
		{
			ID: "default-coverage-gap", TenantID: tenant, Name: "Coverage Gap Fallback",
			EventTypes: []string{"coverage_gap", "*.coverage_gap"}, MinSeverity: SeverityLow,
			Channels: []string{"notify"}, Escalate: false, Enabled: true, CreatedAt: now, UpdatedAt: now,
		},
		{
			ID: "default-worker-failed", TenantID: tenant, Name: "Worker Failed Fallback",
			EventTypes: []string{"worker.failed", "task.failed", "job.failed"}, MinSeverity: SeverityHigh,
			Channels: []string{"notify", "hil"}, Escalate: true, EscalateChannel: "hil", Enabled: true, CreatedAt: now, UpdatedAt: now,
		},
		{
			ID: "default-build-error", TenantID: tenant, Name: "Build Error Fallback",
			EventTypes: []string{"build.error", "ci.failed"}, MinSeverity: SeverityHigh,
			Channels: []string{"notify"}, Escalate: false, Enabled: true, CreatedAt: now, UpdatedAt: now,
		},
	}
}

// AlertPolicyEngine evaluates events against persisted rules or fallbacks and applies sliding throttle windows.
type AlertPolicyEngine struct {
	store AlertStore
}

// NewAlertPolicyEngine creates an engine over the given store.
func NewAlertPolicyEngine(store AlertStore) *AlertPolicyEngine {
	if store == nil {
		store = NewMemoryAlertStore()
	}
	return &AlertPolicyEngine{store: store}
}

// matchEventType checks whether eventType satisfies any rule pattern (exact, prefix.*, or *).
func matchEventType(eventType, pattern string) bool {
	p := strings.TrimSpace(strings.ToLower(pattern))
	et := strings.TrimSpace(strings.ToLower(eventType))
	if p == "*" || p == et {
		return true
	}
	if strings.HasSuffix(p, ".*") {
		prefix := strings.TrimSuffix(p, ".*")
		return strings.HasPrefix(et, prefix+".")
	}
	if strings.HasPrefix(p, "*.") {
		suffix := strings.TrimPrefix(p, "*.")
		return strings.HasSuffix(et, "."+suffix) || et == suffix
	}
	return false
}

func ruleMatchesEvent(rule AlertRule, eventType, severity string) bool {
	if !rule.Enabled {
		return false
	}
	// Severity check
	if !SeverityAtLeast(severity, rule.MinSeverity) {
		return false
	}
	// Event type check
	for _, p := range rule.EventTypes {
		if matchEventType(eventType, p) {
			return true
		}
	}
	return false
}

// Evaluate checks an event against active alert rules for a tenant, returning the alert decision.
func (e *AlertPolicyEngine) Evaluate(ctx context.Context, tenant string, ev Event, subject, overrideSeverity string) (AlertDecision, error) {
	sev := overrideSeverity
	if sev == "" {
		sev = ExtractSeverity(ev.Type)
	}
	now := ev.OccurredAt
	if now.IsZero() {
		now = time.Now().UTC()
	}

	rules, err := e.store.ListAlertRules(ctx, tenant)
	if err != nil {
		// Finding 2: structured warning on database rule load failure
		log.Printf("[WARN] alert_policy_db_fallback_engaged: tenant=%s err=%v; using fallback rules", tenant, err)
		rules = DefaultFallbackRules(tenant)
	} else if len(rules) == 0 {
		// No custom rules, use defaults
		rules = DefaultFallbackRules(tenant)
	}

	for _, rule := range rules {
		if !ruleMatchesEvent(rule, ev.Type, sev) {
			continue
		}

		// Rule matched
		fp := ComputeFingerprint(tenant, rule.ID, ev.Type, subject)
		suppressed, count, err := e.store.CheckAndRecordThrottle(ctx, tenant, rule.ID, fp, rule.ThrottleWindowSeconds, now)
		if err != nil {
			return AlertDecision{}, err
		}

		if suppressed {
			return AlertDecision{
				RuleID:          rule.ID,
				Matched:         true,
				Suppressed:      true,
				SuppressedCount: count,
				Channels:        nil,
				Escalated:       false,
				Fingerprint:     fp,
				Reason:          "suppressed by sliding throttle window",
			}, nil
		}

		// Alert emitted
		return AlertDecision{
			RuleID:          rule.ID,
			Matched:         true,
			Suppressed:      false,
			SuppressedCount: 0,
			Channels:        rule.Channels,
			Escalated:       rule.Escalate,
			EscalateChannel: rule.EscalateChannel,
			Fingerprint:     fp,
			Reason:          "matched rule " + rule.Name,
		}, nil
	}

	// No matching rule
	return AlertDecision{
		RuleID:     "",
		Matched:    false,
		Suppressed: false,
		Reason:     "no matching alert rule",
	}, nil
}

// EvaluateBatch evaluates multiple events sequentially (Finding 3).
func (e *AlertPolicyEngine) EvaluateBatch(ctx context.Context, tenant string, events []Event) ([]AlertDecision, error) {
	out := make([]AlertDecision, len(events))
	for i, ev := range events {
		dec, err := e.Evaluate(ctx, tenant, ev, ev.EventID, "")
		if err != nil {
			return nil, err
		}
		out[i] = dec
	}
	return out, nil
}
