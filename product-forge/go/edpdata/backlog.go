package edpdata

import (
	"context"
	"encoding/json"
	"errors"

	"productforge/datastore"
)

// BacklogItem is a backlog work item's persisted form. `Data` holds the FULL item JSON (lossless) so the DB
// is a complete copy of the file item - no field is dropped. BI-PF-1399 owns the cutover.
type BacklogItem struct {
	ID       string
	TenantID string
	Type     string
	Status   string
	Title    string
	Body     string
	Data     json.RawMessage // full item JSON (jsonb)
	Revision int64
}

// BacklogStore is a Postgres repository over backlog_items (tenant-scoped; RLS enforced by the caller).
type BacklogStore struct{ db datastore.RelationalStore }

// NewBacklog returns a BacklogStore over db.
func NewBacklog(db datastore.RelationalStore) *BacklogStore { return &BacklogStore{db: db} }

func orEmpty(raw json.RawMessage) string {
	if len(raw) == 0 {
		return "{}"
	}
	return string(raw)
}

// Put upserts a backlog item (idempotent on id; material changes bump revision). `Data` is stored verbatim.
func (s *BacklogStore) Put(ctx context.Context, it BacklogItem) (BacklogItem, error) {
	if it.ID == "" || it.TenantID == "" {
		return BacklogItem{}, errors.New("edpdata: backlog id and tenant_id are required")
	}
	if it.Type == "" {
		it.Type = "feature"
	}
	if it.Status == "" {
		it.Status = "new"
	}
	data := orEmpty(it.Data)
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		_, err := tx.Exec(ctx,
			`INSERT INTO backlog_items (id, tenant_id, type, status, title, body, data, revision)
			 VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8)
			 ON CONFLICT (id) DO UPDATE SET type=EXCLUDED.type, status=EXCLUDED.status,
			   title=EXCLUDED.title, body=EXCLUDED.body, data=EXCLUDED.data,
			   revision=backlog_items.revision + 1, updated_at=now()`,
			it.ID, it.TenantID, it.Type, it.Status, it.Title, it.Body, data, it.Revision)
		return err
	})
	if err != nil {
		return BacklogItem{}, err
	}
	return s.Get(ctx, it.ID)
}

// Get reads a backlog item (including its full Data).
func (s *BacklogStore) Get(ctx context.Context, id string) (BacklogItem, error) {
	var it BacklogItem
	var found bool
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		rows, err := tx.Query(ctx,
			`SELECT id, tenant_id, type, status, title, body, data, revision FROM backlog_items WHERE id=$1`, id)
		if err != nil {
			return err
		}
		defer rows.Close()
		if rows.Next() {
			if err := rows.Scan(&it.ID, &it.TenantID, &it.Type, &it.Status, &it.Title, &it.Body, &it.Data, &it.Revision); err != nil {
				return err
			}
			found = true
		}
		return rows.Err()
	})
	if err != nil {
		return BacklogItem{}, err
	}
	if !found {
		return BacklogItem{}, ErrNotFound
	}
	return it, nil
}

// List returns items, optionally filtered by status.
func (s *BacklogStore) List(ctx context.Context, status string, limit int) ([]BacklogItem, error) {
	if limit <= 0 {
		limit = 50
	}
	var out []BacklogItem
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		rows, err := tx.Query(ctx,
			`SELECT id, tenant_id, type, status, title, body, data, revision FROM backlog_items
			 WHERE ($1 = '' OR status = $1) ORDER BY created_at DESC LIMIT $2`, status, limit)
		if err != nil {
			return err
		}
		defer rows.Close()
		for rows.Next() {
			var it BacklogItem
			if err := rows.Scan(&it.ID, &it.TenantID, &it.Type, &it.Status, &it.Title, &it.Body, &it.Data, &it.Revision); err != nil {
				return err
			}
			out = append(out, it)
		}
		return rows.Err()
	})
	return out, err
}

// Delete removes a backlog item.
func (s *BacklogStore) Delete(ctx context.Context, id string) error {
	var affected int64
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		n, err := tx.Exec(ctx, `DELETE FROM backlog_items WHERE id=$1`, id)
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
