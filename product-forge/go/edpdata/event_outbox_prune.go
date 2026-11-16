package edpdata

import (
	"context"
	"fmt"
	"time"

	"productforge/datastore"
)

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
