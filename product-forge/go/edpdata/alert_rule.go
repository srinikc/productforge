package edpdata

import (
	"crypto/sha256"
	"encoding/hex"
	"strings"
	"time"
)

// AlertSeverity levels.
const (
	SeverityLow      = "low"
	SeverityMedium   = "medium"
	SeverityHigh     = "high"
	SeverityCritical = "critical"
)

var severityRanks = map[string]int{
	SeverityLow:      1,
	SeverityMedium:   2,
	SeverityHigh:     3,
	SeverityCritical: 4,
}

// SeverityRank returns the numeric rank (1..4) of a severity string.
func SeverityRank(sev string) int {
	if r, ok := severityRanks[strings.ToLower(strings.TrimSpace(sev))]; ok {
		return r
	}
	return severityRanks[SeverityLow]
}

// SeverityAtLeast checks whether eventSev meets or exceeds minSev threshold.
func SeverityAtLeast(eventSev, minSev string) bool {
	return SeverityRank(eventSev) >= SeverityRank(minSev)
}

// ExtractSeverity attempts to derive severity from event type or payload hint.
func ExtractSeverity(eventType string) string {
	et := strings.ToLower(eventType)
	switch {
	case strings.Contains(et, "critical"), strings.Contains(et, "fatal"), strings.Contains(et, "panic"):
		return SeverityCritical
	case strings.Contains(et, "high"), strings.Contains(et, "error"), strings.Contains(et, "fail"),
		strings.Contains(et, "exhaust"), strings.Contains(et, "conflict"), strings.Contains(et, "escalat"):
		return SeverityHigh
	case strings.Contains(et, "low"), strings.Contains(et, "debug"), strings.Contains(et, "info"):
		return SeverityLow
	default:
		return SeverityMedium
	}
}

// AlertRule defines persisted routing, filtering, throttle, and escalation criteria.
type AlertRule struct {
	ID                    string    `json:"id"`
	TenantID              string    `json:"tenant_id"`
	Name                  string    `json:"name"`
	EventTypes            []string  `json:"event_types"`
	MinSeverity           string    `json:"min_severity"`
	Channels              []string  `json:"channels"`
	ThrottleWindowSeconds int       `json:"throttle_window_seconds"`
	Escalate              bool      `json:"escalate"`
	EscalateChannel       string    `json:"escalate_channel"`
	Enabled               bool      `json:"enabled"`
	CreatedAt             time.Time `json:"created_at"`
	UpdatedAt             time.Time `json:"updated_at"`
}

// AlertDecision is the result of evaluating an event against alert policies.
type AlertDecision struct {
	RuleID          string   `json:"rule_id"`
	Matched         bool     `json:"matched"`
	Suppressed      bool     `json:"suppressed"`
	SuppressedCount int64    `json:"suppressed_count"`
	Channels        []string `json:"channels"`
	Escalated       bool     `json:"escalated"`
	EscalateChannel string   `json:"escalate_channel,omitempty"`
	Fingerprint     string   `json:"fingerprint"`
	Reason          string   `json:"reason"`
}

// ThrottleState captures sliding-window deduplication status.
type ThrottleState struct {
	TenantID        string    `json:"tenant_id"`
	RuleID          string    `json:"rule_id"`
	Fingerprint     string    `json:"fingerprint"`
	FirstSeenAt     time.Time `json:"first_seen_at"`
	LastSeenAt      time.Time `json:"last_seen_at"`
	SuppressedCount int64     `json:"suppressed_count"`
	WindowExpiresAt time.Time `json:"window_expires_at"`
}

// ComputeFingerprint generates a deterministic SHA256 hex string for deduplicating alerts.
func ComputeFingerprint(tenantID, ruleID, eventType, subject string) string {
	raw := strings.TrimSpace(tenantID) + "|" +
		strings.TrimSpace(ruleID) + "|" +
		strings.TrimSpace(eventType) + "|" +
		strings.TrimSpace(subject)
	h := sha256.Sum256([]byte(raw))
	return hex.EncodeToString(h[:])
}
