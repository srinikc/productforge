package edpdata

import (
	"context"
	"fmt"

	"productforge/datastore"
)

// PayloadStore is the object-store subset used for event payload GC.
type PayloadStore interface {
	List(ctx context.Context) ([]string, error)
	Delete(ctx context.Context, ref string) error
}

// ReconcilePayloads deletes object refs that no event row references.
func (s *EventStore) ReconcilePayloads(ctx context.Context, tenant string, store PayloadStore) (int, error) {
	if tenant == "" || store == nil {
		return 0, fmt.Errorf("%w: tenant and payload store required", ErrEventInvalid)
	}
	refs, err := store.List(ctx)
	if err != nil {
		return 0, err
	}
	live := map[string]bool{}
	err = s.db.WithTx(ctx, func(tx datastore.Tx) error {
		if err := s.setTenant(ctx, tx, tenant); err != nil {
			return err
		}
		rows, err := tx.Query(ctx, `SELECT DISTINCT payload_ref FROM events WHERE tenant_id=$1 AND payload_ref <> ''`, tenant)
		if err != nil {
			return err
		}
		defer rows.Close()
		for rows.Next() {
			var ref string
			if err := rows.Scan(&ref); err != nil {
				return err
			}
			live[ref] = true
		}
		return rows.Err()
	})
	if err != nil {
		return 0, err
	}
	deleted := 0
	for _, ref := range refs {
		if live[ref] {
			continue
		}
		if err := store.Delete(ctx, ref); err != nil {
			return deleted, err
		}
		deleted++
	}
	return deleted, nil
}
