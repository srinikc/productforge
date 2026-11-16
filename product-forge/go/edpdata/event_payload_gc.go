package edpdata

import (
	"context"
	"fmt"
	"time"

	"productforge/datastore"
)

// PayloadObject is one tenant-scoped object-store entry.
type PayloadObject struct {
	Ref       string
	CreatedAt int64 // unix seconds
}

// PayloadStore is the object-store subset used for event payloads.
type PayloadStore interface {
	Put(ctx context.Context, tenant, eventID string, data []byte, contentType string) (PayloadRef, error)
	List(ctx context.Context, tenant string) ([]PayloadObject, error)
	Delete(ctx context.Context, tenant, ref string) error
}

// PayloadRef is the durable DB reference for a large payload.
type PayloadRef struct {
	Ref         string
	SHA256      string
	Size        int64
	ContentType string
}

// ReconcilePayloads deletes tenant-scoped object refs that no event row references.
// Objects younger than graceSeconds are skipped to avoid TOCTOU on in-flight appends.
func (s *EventStore) ReconcilePayloads(ctx context.Context, tenant string, store PayloadStore, graceSeconds int64) (int, error) {
	if tenant == "" || store == nil {
		return 0, fmt.Errorf("%w: tenant and payload store required", ErrEventInvalid)
	}
	objects, err := store.List(ctx, tenant)
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
	now := time.Now().Unix()
	deleted := 0
	for _, obj := range objects {
		if live[obj.Ref] || (graceSeconds > 0 && now-obj.CreatedAt < graceSeconds) {
			continue
		}
		if err := store.Delete(ctx, tenant, obj.Ref); err != nil {
			return deleted, err
		}
		deleted++
	}
	return deleted, nil
}
