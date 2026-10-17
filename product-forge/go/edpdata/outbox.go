package edpdata

import (
	"context"
	"errors"

	"productforge/datastore"
)

// OutboxStore implements datastore.OutboxStore over the `outbox` table (EDP-19 / BI-PF-1311): a durable,
// at-least-once async-effect queue written in the same tx as the state change. Lease-free claim batches
// (FOR UPDATE SKIP LOCKED) then mark delivered/failed.
type OutboxStore struct{ db datastore.RelationalStore }

// NewOutbox returns an OutboxStore over db.
func NewOutbox(db datastore.RelationalStore) *OutboxStore { return &OutboxStore{db: db} }

// Append writes one event (call it inside the same tx as the state change).
func (s *OutboxStore) Append(ctx context.Context, e datastore.Event) error {
	if e.ID == "" || e.TenantID == "" {
		return errors.New("edpdata: outbox id and tenant_id are required")
	}
	return s.db.WithTx(ctx, func(tx datastore.Tx) error {
		_, err := tx.Exec(ctx,
			`INSERT INTO outbox (id, tenant_id, type, payload, at) VALUES ($1,$2,$3,$4,$5)
			 ON CONFLICT (id) DO NOTHING`,
			e.ID, e.TenantID, e.Type, e.Payload, e.At)
		return err
	})
}

// ClaimBatch leases up to n pending events (oldest first) and returns them.
func (s *OutboxStore) ClaimBatch(ctx context.Context, n int) ([]datastore.Event, error) {
	if n <= 0 {
		n = 50
	}
	var out []datastore.Event
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		rows, err := tx.Query(ctx,
			`UPDATE outbox SET status='claimed', attempts=attempts+1
			 WHERE id IN (SELECT id FROM outbox WHERE status='pending' ORDER BY at
			              FOR UPDATE SKIP LOCKED LIMIT $1)
			 RETURNING id, tenant_id, type, payload, at`, n)
		if err != nil {
			return err
		}
		defer rows.Close()
		for rows.Next() {
			var e datastore.Event
			if err := rows.Scan(&e.ID, &e.TenantID, &e.Type, &e.Payload, &e.At); err != nil {
				return err
			}
			out = append(out, e)
		}
		return rows.Err()
	})
	return out, err
}

func (s *OutboxStore) setStatus(ctx context.Context, id, status, reason string) error {
	var affected int64
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		n, err := tx.Exec(ctx,
			`UPDATE outbox SET status=$1, reason=$2, delivered_at=CASE WHEN $1='delivered' THEN now() ELSE delivered_at END
			 WHERE id=$3`, status, reason, id)
		affected = n
		return err
	})
	if err != nil {
		return err
	}
	if affected == 0 {
		return ErrNotFound
	}
	return nil
}

// MarkDelivered marks an event delivered.
func (s *OutboxStore) MarkDelivered(ctx context.Context, id string) error {
	return s.setStatus(ctx, id, "delivered", "")
}

// MarkFailed dead-letters an event with a reason.
func (s *OutboxStore) MarkFailed(ctx context.Context, id, reason string) error {
	return s.setStatus(ctx, id, "failed", reason)
}
