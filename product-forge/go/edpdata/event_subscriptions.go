package edpdata

import (
	"context"
	"encoding/json"
	"fmt"

	"productforge/datastore"
)

// Subscription is a persisted event subscription. One writer: EventStore.
type Subscription struct {
	ID         string            `json:"id"`
	TenantID   string            `json:"tenant_id"`
	EventTypes []string          `json:"event_types"`
	Filter     map[string]string `json:"filter,omitempty"`
	Transport  string            `json:"transport"`
	Target     string            `json:"target,omitempty"`
	AuthRef    string            `json:"auth_ref,omitempty"`
	Enabled    bool              `json:"enabled"`
	LastSeq    int64             `json:"last_seq"`
}

// UpsertSubscription creates or updates one subscription.
func (s *EventStore) UpsertSubscription(ctx context.Context, sub Subscription) error {
	if sub.ID == "" || sub.TenantID == "" || sub.Transport == "" {
		return fmt.Errorf("%w: id, tenant_id and transport are required", ErrEventInvalid)
	}
	types, _ := json.Marshal(sub.EventTypes)
	filter, _ := json.Marshal(sub.Filter)
	return s.db.WithTx(ctx, func(tx datastore.Tx) error {
		if err := s.setTenant(ctx, tx, sub.TenantID); err != nil {
			return err
		}
		_, err := tx.Exec(ctx, `INSERT INTO event_subscriptions
			(id,tenant_id,event_types,filter,transport,target,auth_ref,enabled,updated_at)
			VALUES ($1,$2,$3::jsonb,$4::jsonb,$5,$6,$7,$8,now())
			ON CONFLICT (id) DO UPDATE SET
				event_types=EXCLUDED.event_types, filter=EXCLUDED.filter,
				transport=EXCLUDED.transport, target=EXCLUDED.target,
				auth_ref=EXCLUDED.auth_ref, enabled=EXCLUDED.enabled, updated_at=now()
			WHERE event_subscriptions.tenant_id=EXCLUDED.tenant_id`,
			sub.ID, sub.TenantID, string(types), string(filter), sub.Transport,
			sub.Target, sub.AuthRef, sub.Enabled)
		return err
	})
}

// ListSubscriptions returns enabled subscriptions for a tenant.
func (s *EventStore) ListSubscriptions(ctx context.Context, tenant string) ([]Subscription, error) {
	var out []Subscription
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		if err := s.setTenant(ctx, tx, tenant); err != nil {
			return err
		}
		rows, err := tx.Query(ctx, `SELECT id,tenant_id,event_types,filter,transport,target,auth_ref,enabled,last_seq
			FROM event_subscriptions WHERE tenant_id=$1 AND enabled=true ORDER BY id`, tenant)
		if err != nil {
			return err
		}
		defer rows.Close()
		for rows.Next() {
			var sub Subscription
			var types, filter []byte
			if err := rows.Scan(&sub.ID, &sub.TenantID, &types, &filter, &sub.Transport,
				&sub.Target, &sub.AuthRef, &sub.Enabled, &sub.LastSeq); err != nil {
				return err
			}
			_ = json.Unmarshal(types, &sub.EventTypes)
			_ = json.Unmarshal(filter, &sub.Filter)
			out = append(out, sub)
		}
		return rows.Err()
	})
	return out, err
}
