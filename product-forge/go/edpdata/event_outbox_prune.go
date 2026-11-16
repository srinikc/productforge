package edpdata

import (
	"context"
	"fmt"
	"time"

	"productforge/datastore"
)

// ErrOutboxBound means pending outbox rows exceeded the configured bound.
var ErrOutboxBound = fmt.Errorf("edpdata: event outbox bound exceeded")

// EnforceOutboxBound applies backpressure; it never deletes pending/claimed rows.
func (s *EventStore) EnforceOutboxBound(ctx context.Context, tenant string, maxPending int64) error {
	if tenant == "" || maxPending <= 0 {
		return fmt.Errorf("%w: tenant and positive bound required", ErrEventInvalid)
	}
	var n int64
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		if err := s.setTenant(ctx, tx, tenant); err != nil {
			return err
		}
		rows, err := tx.Query(ctx, `SELECT count(*) FROM events_outbox WHERE tenant_id=$1 AND status IN ('pending','claimed')`, tenant)
		if err != nil {
			return err
		}
		defer rows.Close()
		if rows.Next() {
			if err := rows.Scan(&n); err != nil {
				return err
			}
		}
		return rows.Err()
	})
	if err != nil {
		return err
	}
	if n > maxPending {
		return fmt.Errorf("%w: pending=%d max=%d", ErrOutboxBound, n, maxPending)
	}
	return nil
}

// PruneOutbox removes only delivered/failed outbox rows older than retention.
// Pending/claimed rows are never deleted.
func (s *EventStore) PruneOutbox(ctx context.Context, tenant string, retention time.Duration) (int64, error) {
	if tenant == "" {
		return 0, fmt.Errorf("%w: tenant_id required", ErrEventInvalid)
	}
	if retention <= 0 {
		retention = 7 * 24 * time.Hour
	}
	var n int64
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		if err := s.setTenant(ctx, tx, tenant); err != nil {
			return err
		}
		var err error
		n, err = tx.Exec(ctx, `DELETE FROM events_outbox
			WHERE tenant_id=$1 AND status IN ('delivered','failed')
			AND created_at < now() - $2::interval`, tenant, fmt.Sprintf("%d seconds", int(retention.Seconds())))
		return err
	})
	return n, err
}
