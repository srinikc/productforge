package edpdata

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"productforge/datastore"
)

// AlertStore is the interface for persisting and querying alert rules and throttle states.
type AlertStore interface {
	UpsertAlertRule(ctx context.Context, rule AlertRule) error
	ListAlertRules(ctx context.Context, tenant string) ([]AlertRule, error)
	DeleteAlertRule(ctx context.Context, tenant, ruleID string) error
	CheckAndRecordThrottle(ctx context.Context, tenant, ruleID, fingerprint string, windowSeconds int, now time.Time) (bool, int64, error)
	CleanupExpiredThrottles(ctx context.Context, tenant string, before time.Time) (int64, error)
}

// -------------------------------------------------------------------------
// MemoryAlertStore: thread-safe in-memory store for policy evaluation & tests
// -------------------------------------------------------------------------

// MemoryAlertStore holds alert rules and throttle states in memory.
type MemoryAlertStore struct {
	mu        sync.RWMutex
	rules     map[string]map[string]AlertRule // tenantID -> ruleID -> AlertRule
	throttles map[string]*ThrottleState       // tenant|ruleID|fingerprint -> ThrottleState
}

// NewMemoryAlertStore creates a new in-memory alert store.
func NewMemoryAlertStore() *MemoryAlertStore {
	return &MemoryAlertStore{
		rules:     make(map[string]map[string]AlertRule),
		throttles: make(map[string]*ThrottleState),
	}
}

func throttleKey(tenant, ruleID, fingerprint string) string {
	return tenant + "|" + ruleID + "|" + fingerprint
}

// UpsertAlertRule stores an alert rule in memory.
func (m *MemoryAlertStore) UpsertAlertRule(_ context.Context, rule AlertRule) error {
	if rule.ID == "" || rule.TenantID == "" {
		return fmt.Errorf("%w: rule id and tenant_id are required", ErrEventInvalid)
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	tr, ok := m.rules[rule.TenantID]
	if !ok {
		tr = make(map[string]AlertRule)
		m.rules[rule.TenantID] = tr
	}
	now := time.Now().UTC()
	if rule.CreatedAt.IsZero() {
		rule.CreatedAt = now
	}
	rule.UpdatedAt = now
	tr[rule.ID] = rule
	return nil
}

// ListAlertRules lists all enabled alert rules for a tenant.
func (m *MemoryAlertStore) ListAlertRules(_ context.Context, tenant string) ([]AlertRule, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	tr, ok := m.rules[tenant]
	if !ok {
		return nil, nil
	}
	var out []AlertRule
	for _, r := range tr {
		if r.Enabled {
			out = append(out, r)
		}
	}
	return out, nil
}

// DeleteAlertRule removes a rule for a tenant.
func (m *MemoryAlertStore) DeleteAlertRule(_ context.Context, tenant, ruleID string) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	if tr, ok := m.rules[tenant]; ok {
		delete(tr, ruleID)
	}
	return nil
}

// CheckAndRecordThrottle checks sliding throttle window and increments suppressed count.
func (m *MemoryAlertStore) CheckAndRecordThrottle(_ context.Context, tenant, ruleID, fingerprint string, windowSeconds int, now time.Time) (bool, int64, error) {
	if windowSeconds <= 0 {
		return false, 0, nil
	}
	m.mu.Lock()
	defer m.mu.Unlock()

	k := throttleKey(tenant, ruleID, fingerprint)
	ts, exists := m.throttles[k]
	if !exists || now.After(ts.WindowExpiresAt) {
		// Fresh window
		m.throttles[k] = &ThrottleState{
			TenantID:        tenant,
			RuleID:          ruleID,
			Fingerprint:     fingerprint,
			FirstSeenAt:     now,
			LastSeenAt:      now,
			SuppressedCount: 0,
			WindowExpiresAt: now.Add(time.Duration(windowSeconds) * time.Second),
		}
		return false, 0, nil
	}

	// Within window: suppress alert and count
	ts.LastSeenAt = now
	ts.SuppressedCount++
	return true, ts.SuppressedCount, nil
}

// CleanupExpiredThrottles removes expired throttle states before the given time.
func (m *MemoryAlertStore) CleanupExpiredThrottles(_ context.Context, tenant string, before time.Time) (int64, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	var pruned int64
	for k, ts := range m.throttles {
		if (tenant == "" || ts.TenantID == tenant) && ts.WindowExpiresAt.Before(before) {
			delete(m.throttles, k)
			pruned++
		}
	}
	return pruned, nil
}

// CleanupExpired sweeps all throttles expired before now (Finding 1).
func (m *MemoryAlertStore) CleanupExpired(now time.Time) int64 {
	n, _ := m.CleanupExpiredThrottles(context.Background(), "", now)
	return n
}

// -------------------------------------------------------------------------
// EventStore PostgreSQL methods implementing AlertStore
// -------------------------------------------------------------------------

// UpsertAlertRule persists an alert rule to PostgreSQL with tenant RLS.
func (s *EventStore) UpsertAlertRule(ctx context.Context, rule AlertRule) error {
	if rule.ID == "" || rule.TenantID == "" {
		return fmt.Errorf("%w: rule id and tenant_id are required", ErrEventInvalid)
	}
	if rule.MinSeverity == "" {
		rule.MinSeverity = SeverityLow
	}
	eventTypes, _ := json.Marshal(rule.EventTypes)
	channels, _ := json.Marshal(rule.Channels)

	return s.db.WithTx(ctx, func(tx datastore.Tx) error {
		if err := s.setTenant(ctx, tx, rule.TenantID); err != nil {
			return err
		}
		n, err := tx.Exec(ctx, `INSERT INTO alert_rules
			(id, tenant_id, name, event_types, min_severity, channels, throttle_window_seconds, escalate, escalate_channel, enabled, updated_at)
			VALUES ($1, $2, $3, $4::jsonb, $5, $6::jsonb, $7, $8, $9, $10, now())
			ON CONFLICT (id) DO UPDATE SET
				name=EXCLUDED.name,
				event_types=EXCLUDED.event_types,
				min_severity=EXCLUDED.min_severity,
				channels=EXCLUDED.channels,
				throttle_window_seconds=EXCLUDED.throttle_window_seconds,
				escalate=EXCLUDED.escalate,
				escalate_channel=EXCLUDED.escalate_channel,
				enabled=EXCLUDED.enabled,
				updated_at=now()
			WHERE alert_rules.tenant_id=EXCLUDED.tenant_id`,
			rule.ID, rule.TenantID, rule.Name, string(eventTypes), rule.MinSeverity,
			string(channels), rule.ThrottleWindowSeconds, rule.Escalate, rule.EscalateChannel, rule.Enabled)
		if err == nil && n == 0 {
			return fmt.Errorf("%w: rule id belongs to another tenant", ErrEventInvalid)
		}
		return err
	})
}

// ListAlertRules returns all enabled alert rules for a tenant from PostgreSQL.
func (s *EventStore) ListAlertRules(ctx context.Context, tenant string) ([]AlertRule, error) {
	var out []AlertRule
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		if err := s.setTenant(ctx, tx, tenant); err != nil {
			return err
		}
		rows, err := tx.Query(ctx, `SELECT id, tenant_id, name, event_types, min_severity, channels,
			throttle_window_seconds, escalate, escalate_channel, enabled, created_at, updated_at
			FROM alert_rules WHERE tenant_id=$1 AND enabled=true ORDER BY id`, tenant)
		if err != nil {
			return err
		}
		defer rows.Close()
		for rows.Next() {
			var r AlertRule
			var evTypes, chs []byte
			if err := rows.Scan(&r.ID, &r.TenantID, &r.Name, &evTypes, &r.MinSeverity, &chs,
				&r.ThrottleWindowSeconds, &r.Escalate, &r.EscalateChannel, &r.Enabled,
				&r.CreatedAt, &r.UpdatedAt); err != nil {
				return err
			}
			_ = json.Unmarshal(evTypes, &r.EventTypes)
			_ = json.Unmarshal(chs, &r.Channels)
			out = append(out, r)
		}
		return rows.Err()
	})
	return out, err
}

// DeleteAlertRule removes a rule from PostgreSQL.
func (s *EventStore) DeleteAlertRule(ctx context.Context, tenant, ruleID string) error {
	return s.db.WithTx(ctx, func(tx datastore.Tx) error {
		if err := s.setTenant(ctx, tx, tenant); err != nil {
			return err
		}
		_, err := tx.Exec(ctx, `DELETE FROM alert_rules WHERE id=$1 AND tenant_id=$2`, ruleID, tenant)
		return err
	})
}

// CheckAndRecordThrottle checks sliding throttle state in PostgreSQL.
func (s *EventStore) CheckAndRecordThrottle(ctx context.Context, tenant, ruleID, fingerprint string, windowSeconds int, now time.Time) (bool, int64, error) {
	if windowSeconds <= 0 {
		return false, 0, nil
	}
	var suppressed bool
	var count int64

	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		if err := s.setTenant(ctx, tx, tenant); err != nil {
			return err
		}
		expiresAt := now.Add(time.Duration(windowSeconds) * time.Second)

		rows, err := tx.Query(ctx, `SELECT suppressed_count, window_expires_at
			FROM alert_throttle_state WHERE tenant_id=$1 AND rule_id=$2 AND fingerprint=$3
			FOR UPDATE`, tenant, ruleID, fingerprint)
		if err != nil {
			return err
		}

		if rows.Next() {
			var currentCount int64
			var winExpires time.Time
			if err := rows.Scan(&currentCount, &winExpires); err != nil {
				rows.Close()
				return err
			}
			rows.Close()

			if now.Before(winExpires) || now.Equal(winExpires) {
				// Suppress
				count = currentCount + 1
				suppressed = true
				_, err := tx.Exec(ctx, `UPDATE alert_throttle_state
					SET last_seen_at=$1, suppressed_count=$2
					WHERE tenant_id=$3 AND rule_id=$4 AND fingerprint=$5`,
					now, count, tenant, ruleID, fingerprint)
				return err
			}

			// Expired window: reset
			suppressed = false
			count = 0
			_, err := tx.Exec(ctx, `UPDATE alert_throttle_state
				SET first_seen_at=$1, last_seen_at=$1, suppressed_count=0, window_expires_at=$2
				WHERE tenant_id=$3 AND rule_id=$4 AND fingerprint=$5`,
				now, expiresAt, tenant, ruleID, fingerprint)
			return err
		}
		rows.Close()

		// First entry
		suppressed = false
		count = 0
		_, err = tx.Exec(ctx, `INSERT INTO alert_throttle_state
			(tenant_id, rule_id, fingerprint, first_seen_at, last_seen_at, suppressed_count, window_expires_at)
			VALUES ($1, $2, $3, $4, $4, 0, $5)`,
			tenant, ruleID, fingerprint, now, expiresAt)
		return err
	})

	return suppressed, count, err
}

// CleanupExpiredThrottles prunes expired throttle states from PostgreSQL.
func (s *EventStore) CleanupExpiredThrottles(ctx context.Context, tenant string, before time.Time) (int64, error) {
	var count int64
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		if err := s.setTenant(ctx, tx, tenant); err != nil {
			return err
		}
		n, err := tx.Exec(ctx, `DELETE FROM alert_throttle_state
			WHERE tenant_id=$1 AND window_expires_at < $2`, tenant, before)
		count = n
		return err
	})
	return count, err
}
