package edpdata

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"sync"

	"productforge/datastore"
)

// The eight canonical memory types (EDP-21). Unknown types fail closed.
var memoryKinds = map[string]bool{
	"raw_evidence": true, "semantic": true, "episodic": true, "decision": true,
	"procedural": true, "failure": true, "policy": true, "working": true,
}

var memoryACL = map[string]bool{"": true, "private": true, "project": true, "tenant": true, "shared": true}

// EmbeddingDim is the fixed vector contract (callers supply vectors of exactly this size).
const EmbeddingDim = 1536

// MemoryStore implements datastore.MemoryRepository: metadata + provenance in the SoR; large payloads are
// referenced via ObjectRef (the object store). Search applies tenant/project/source/kind/user ACL filters in
// SQL (RLS also enforces the tenant via store.BindTenant's app.tenant_id) and never returns rows outside the
// requested scope.
type MemoryStore struct {
	db      datastore.RelationalStore
	vecOnce sync.Once
	hasVec  bool
}

// NewMemory returns a MemoryStore over db.
func NewMemory(db datastore.RelationalStore) *MemoryStore { return &MemoryStore{db: db} }

func (s *MemoryStore) vectorAvailable(ctx context.Context, tx datastore.Tx) bool {
	s.vecOnce.Do(func() {
		rows, err := tx.Query(ctx, `SELECT EXISTS (
			SELECT 1 FROM information_schema.columns
			WHERE table_schema = 'public' AND table_name = 'memory' AND column_name = 'embedding')`)
		if err != nil {
			return
		}
		defer rows.Close()
		if rows.Next() {
			_ = rows.Scan(&s.hasVec)
		}
	})
	return s.hasVec
}

// Put upserts a memory entry (validating the type/ACL contract and embedding dimension).
func (s *MemoryStore) Put(ctx context.Context, e datastore.MemoryEntry) (datastore.MemoryEntry, error) {
	if e.ID == "" || e.TenantID == "" {
		return datastore.MemoryEntry{}, errors.New("edpdata: memory id and tenant_id are required")
	}
	if e.Kind != "" && !memoryKinds[e.Kind] {
		return datastore.MemoryEntry{}, fmt.Errorf("edpdata: unknown memory kind %q", e.Kind)
	}
	if !memoryACL[e.ACLScope] {
		return datastore.MemoryEntry{}, fmt.Errorf("edpdata: unknown acl_scope %q", e.ACLScope)
	}
	if len(e.Embedding) != 0 && len(e.Embedding) != EmbeddingDim {
		return datastore.MemoryEntry{}, fmt.Errorf("edpdata: embedding must have %d dimensions, got %d", EmbeddingDim, len(e.Embedding))
	}
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		if _, err := tx.Exec(ctx,
			`INSERT INTO memory (id, tenant_id, project_id, kind, object_ref, acl_scope, content, source, owner)
			 VALUES ($1,$2,NULLIF($3,''),$4,$5,$6,$7,$8,$9)
			 ON CONFLICT (id) DO UPDATE SET project_id=EXCLUDED.project_id, kind=EXCLUDED.kind,
			   object_ref=EXCLUDED.object_ref, acl_scope=EXCLUDED.acl_scope, content=EXCLUDED.content,
			   source=EXCLUDED.source, owner=EXCLUDED.owner`,
			e.ID, e.TenantID, e.Project, e.Kind, e.ObjectRef, e.ACLScope, e.Content, e.Source, e.Owner); err != nil {
			return err
		}
		if len(e.Embedding) != 0 && s.vectorAvailable(ctx, tx) {
			vec := formatVector(e.Embedding)
			if _, err := tx.Exec(ctx, `UPDATE memory SET embedding = $1::vector WHERE id = $2`, vec, e.ID); err != nil {
				return err
			}
		}
		return nil
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
			`SELECT id, tenant_id, COALESCE(project_id,''), kind, object_ref, acl_scope,
			        content, source, owner
			 FROM memory WHERE id=$1`, id)
		if err != nil {
			return err
		}
		defer rows.Close()
		if rows.Next() {
			if err := rows.Scan(&e.ID, &e.TenantID, &e.Project, &e.Kind, &e.ObjectRef, &e.ACLScope,
				&e.Content, &e.Source, &e.Owner); err != nil {
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

// Search is FTS-first and merges vector similarity when an embedding is supplied AND pgvector is available.
// ACL filters (tenant, project, source, kinds, private-owner) are applied IN SQL before ranking.
func (s *MemoryStore) Search(ctx context.Context, q string, scope datastore.MemoryScope, k int) ([]datastore.MemoryEntry, error) {
	if k <= 0 {
		k = 20
	}
	if k > 200 {
		k = 200
	}
	args := []any{}
	add := func(v any) string { args = append(args, v); return fmt.Sprintf("$%d", len(args)) }

	where := []string{"TRUE"}
	if scope.TenantID != "" {
		where = append(where, "tenant_id = "+add(scope.TenantID))
	}
	if scope.Project != "" {
		where = append(where, "project_id = "+add(scope.Project))
	}
	if scope.Source != "" {
		where = append(where, "source = "+add(scope.Source))
	}
	if len(scope.Kinds) > 0 {
		where = append(where, "kind = ANY("+add(scope.Kinds)+")")
	}
	if scope.User != "" {
		where = append(where, "(acl_scope <> 'private' OR owner = "+add(scope.User)+")")
	} else {
		where = append(where, "acl_scope <> 'private'")
	}
	q = strings.TrimSpace(q)
	rankExpr := "0::float4"
	ftsIdx := -1
	if q != "" {
		tsq := add(q)
		ftsIdx = len(where)
		where = append(where, "tsv @@ websearch_to_tsquery('english', "+tsq+")")
		rankExpr = "ts_rank(tsv, websearch_to_tsquery('english', " + tsq + "))"
	}

	hybrid := false
	if len(scope.Vector) != 0 {
		if len(scope.Vector) != EmbeddingDim {
			return nil, fmt.Errorf("edpdata: query embedding must have %d dimensions, got %d", EmbeddingDim, len(scope.Vector))
		}
		var ok bool
		if err := s.db.WithTx(ctx, func(tx datastore.Tx) error { ok = s.vectorAvailable(ctx, tx); return nil }); err != nil {
			return nil, err
		}
		if ok {
			hybrid = true
			vec := add(formatVector(scope.Vector))
			sim := "CASE WHEN embedding IS NULL THEN 0 ELSE 1 - (embedding <=> " + vec + "::vector) END"
			rankExpr = "(0.7 * " + rankExpr + " + 0.3 * " + sim + ")"
			if ftsIdx >= 0 {
				// FTS matches and vector neighbours are both eligible.
				tsq := add(q)
				where[ftsIdx] = "(tsv @@ websearch_to_tsquery('english', " + tsq + ") OR embedding IS NOT NULL)"
			} else {
				where = append(where, "embedding IS NOT NULL")
			}
		}
	}

	order := "created_at DESC, id ASC"
	if q != "" || hybrid {
		order = "score DESC, created_at DESC, id ASC"
	}
	sql := fmt.Sprintf(`SELECT id, tenant_id, COALESCE(project_id,''), kind, object_ref, acl_scope,
	       content, source, owner, %s AS score
		FROM memory WHERE %s ORDER BY %s LIMIT %s`,
		rankExpr, strings.Join(where, " AND "), order, add(k))

	var out []datastore.MemoryEntry
	err := s.db.WithTx(ctx, func(tx datastore.Tx) error {
		rows, err := tx.Query(ctx, sql, args...)
		if err != nil {
			return err
		}
		defer rows.Close()
		for rows.Next() {
			var e datastore.MemoryEntry
			if err := rows.Scan(&e.ID, &e.TenantID, &e.Project, &e.Kind, &e.ObjectRef, &e.ACLScope,
				&e.Content, &e.Source, &e.Owner, &e.Score); err != nil {
				return err
			}
			out = append(out, e)
		}
		return rows.Err()
	})
	return out, err
}

// formatVector renders a float32 slice as a pgvector literal ('[a,b,c]') without a pgvector Go dependency.
func formatVector(v []float32) string {
	var b strings.Builder
	b.WriteByte('[')
	for i, x := range v {
		if i > 0 {
			b.WriteByte(',')
		}
		fmt.Fprintf(&b, "%g", x)
	}
	b.WriteByte(']')
	return b.String()
}
