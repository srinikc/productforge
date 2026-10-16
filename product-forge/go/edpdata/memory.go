package edpdata

import (
	"context"
	"errors"

	"productforge/datastore"
)

// MemoryStore implements datastore.MemoryRepository: metadata + provenance in the SoR; large payloads are
// referenced via ObjectRef (the object store). Search applies the tenant/project/source ACL filters in SQL
// (RLS also enforces the tenant); it never returns rows outside the requested scope.
type MemoryStore struct{ db datastore.RelationalStore }

// NewMemory returns a MemoryStore over db.
func NewMemory(db datastore.RelationalStore) *MemoryStore { return &MemoryStore{db: db} }

// Put upserts a memory entry.
func (s *MemoryStore) Put(ctx context.Context, e datastore.MemoryEntry) (datastore.MemoryEntry, error) {
	if e.ID == "" || e.TenantID == "" {
		return datastore.MemoryEntry{}, errors.New("edpdata: memory id and tenant_id are required")
	}
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		_, err := tx.Exec(ctx,
			`INSERT INTO memory (id, tenant_id, project_id, kind, object_ref, acl_scope)
			 VALUES ($1,$2,NULLIF($3,''),$4,$5,$6)
			 ON CONFLICT (id) DO UPDATE SET project_id=EXCLUDED.project_id, kind=EXCLUDED.kind,
			   object_ref=EXCLUDED.object_ref, acl_scope=EXCLUDED.acl_scope`,
			e.ID, e.TenantID, e.Project, e.Kind, e.ObjectRef, e.ACLScope)
		return err
	})
	if err != nil {
		return datastore.MemoryEntry{}, err
	}
	return s.Get(ctx, e.ID)
}

// Get reads a memory entry.
func (s *MemoryStore) Get(ctx context.Context, id string) (datastore.MemoryEntry, error) {
	var e datastore.MemoryEntry
	var found bool
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		rows, err := tx.Query(ctx,
			`SELECT id, tenant_id, COALESCE(project_id,''), kind, object_ref, acl_scope
			 FROM memory WHERE id=$1`, id)
		if err != nil {
			return err
		}
		defer rows.Close()
		if rows.Next() {
			if err := rows.Scan(&e.ID, &e.TenantID, &e.Project, &e.Kind, &e.ObjectRef, &e.ACLScope); err != nil {
				return err
			}
			found = true
		}
		return rows.Err()
	})
	if err != nil {
		return datastore.MemoryEntry{}, err
	}
	if !found {
		return datastore.MemoryEntry{}, ErrNotFound
	}
	return e, nil
}

// Delete removes a memory entry.
func (s *MemoryStore) Delete(ctx context.Context, id string) error {
	var affected int64
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		n, err := tx.Exec(ctx, `DELETE FROM memory WHERE id=$1`, id)
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

// Search returns up to k entries within scope (project/source ACL filters applied). Text/vector ranking is
// a follow-up (FTS/pgvector); this returns by kind/scope with a stable order.
func (s *MemoryStore) Search(ctx context.Context, q string, scope datastore.MemoryScope, k int) ([]datastore.MemoryEntry, error) {
	if k <= 0 {
		k = 20
	}
	var out []datastore.MemoryEntry
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		rows, err := tx.Query(ctx,
			`SELECT id, tenant_id, COALESCE(project_id,''), kind, object_ref, acl_scope
			 FROM memory
			 WHERE ($1 = '' OR project_id = $1) AND ($2 = '' OR acl_scope = $2) AND ($3 = '' OR kind = $3)
			 ORDER BY created_at DESC LIMIT $4`,
			scope.Project, scope.Source, q, k)
		if err != nil {
			return err
		}
		defer rows.Close()
		for rows.Next() {
			var e datastore.MemoryEntry
			if err := rows.Scan(&e.ID, &e.TenantID, &e.Project, &e.Kind, &e.ObjectRef, &e.ACLScope); err != nil {
				return err
			}
			out = append(out, e)
		}
		return rows.Err()
	})
	return out, err
}
