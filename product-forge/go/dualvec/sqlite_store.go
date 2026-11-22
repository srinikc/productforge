package dualvec

import (
	"context"
	"database/sql"
	"encoding/binary"
	"errors"
	"fmt"
	"math"
	"sort"
	"strings"
	"sync"
	"time"

	_ "modernc.org/sqlite"
	"productforge/datastore"
)

// The eight canonical memory types (EDP-21). Unknown types fail closed.
var memoryKinds = map[string]bool{
	"raw_evidence": true, "semantic": true, "episodic": true, "decision": true,
	"procedural": true, "failure": true, "policy": true, "working": true,
}

var memoryACL = map[string]bool{"": true, "private": true, "project": true, "tenant": true, "shared": true}

// EmbeddingDim is the fixed vector contract (1536 dimensions).
const EmbeddingDim = 1536

// SqliteMemoryStore implements datastore.MemoryRepository over embedded SQLite with
// native pure-Go vector cosine similarity and lexical token search.
type SqliteMemoryStore struct {
	db *sql.DB
	mu sync.RWMutex
}

// NewSqliteMemoryStore creates and initializes a SQLite memory store at the given DSN or path.
func NewSqliteMemoryStore(dsn string) (*SqliteMemoryStore, error) {
	if dsn == "" {
		dsn = ":memory:"
	}
	// Strip sqlite:// prefix if present
	dsn = strings.TrimPrefix(dsn, "sqlite://")
	dsn = strings.TrimPrefix(dsn, "sqlite3://")

	db, err := sql.Open("sqlite", dsn)
	if err != nil {
		return nil, fmt.Errorf("dualvec: failed to open sqlite: %w", err)
	}

	// Single connection for in-memory DBs to prevent state loss across connection pools
	if dsn == ":memory:" || strings.Contains(dsn, "mode=memory") {
		db.SetMaxOpenConns(1)
	}

	store := &SqliteMemoryStore{db: db}
	if err := store.initSchema(context.Background()); err != nil {
		_ = db.Close()
		return nil, err
	}
	return store, nil
}

func (s *SqliteMemoryStore) initSchema(ctx context.Context) error {
	schema := `
	CREATE TABLE IF NOT EXISTS memory_entries (
		id TEXT PRIMARY KEY,
		tenant_id TEXT NOT NULL,
		project_id TEXT,
		kind TEXT NOT NULL,
		object_ref TEXT,
		acl_scope TEXT,
		content TEXT,
		source TEXT,
		owner TEXT,
		embedding BLOB,
		created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
	);
	CREATE INDEX IF NOT EXISTS idx_mem_tenant_proj ON memory_entries(tenant_id, project_id);
	CREATE INDEX IF NOT EXISTS idx_mem_owner ON memory_entries(owner);
	CREATE INDEX IF NOT EXISTS idx_mem_kind ON memory_entries(kind);
	`
	_, err := s.db.ExecContext(ctx, schema)
	if err != nil {
		return fmt.Errorf("dualvec: failed to initialize sqlite schema: %w", err)
	}
	return nil
}

// Close closes the underlying database handle.
func (s *SqliteMemoryStore) Close() error {
	return s.db.Close()
}

// encodeVector serializes a float32 slice into packed little-endian bytes.
func encodeVector(v []float32) []byte {
	if len(v) == 0 {
		return nil
	}
	buf := make([]byte, len(v)*4)
	for i, f := range v {
		binary.LittleEndian.PutUint32(buf[i*4:], math.Float32bits(f))
	}
	return buf
}

// decodeVector deserializes packed little-endian bytes into a float32 slice.
func decodeVector(b []byte) []float32 {
	if len(b) == 0 || len(b)%4 != 0 {
		return nil
	}
	n := len(b) / 4
	v := make([]float32, n)
	for i := 0; i < n; i++ {
		v[i] = math.Float32frombits(binary.LittleEndian.Uint32(b[i*4:]))
	}
	return v
}

// cosineSimilarity computes cosine similarity between two float32 vectors in [-1.0, 1.0].
func cosineSimilarity(a, b []float32) float32 {
	if len(a) != len(b) || len(a) == 0 {
		return 0
	}
	var dot, normA, normB float32
	for i := 0; i < len(a); i++ {
		dot += a[i] * b[i]
		normA += a[i] * a[i]
		normB += b[i] * b[i]
	}
	if normA <= 0 || normB <= 0 {
		return 0
	}
	return dot / (float32(math.Sqrt(float64(normA))) * float32(math.Sqrt(float64(normB))))
}

// lexicalScore calculates a simple token overlap score in [0.0, 1.0].
func lexicalScore(query, content string) float32 {
	if query == "" || content == "" {
		return 0
	}
	qTokens := strings.Fields(strings.ToLower(query))
	if len(qTokens) == 0 {
		return 0
	}
	cLower := strings.ToLower(content)
	matched := 0
	for _, tok := range qTokens {
		if strings.Contains(cLower, tok) {
			matched++
		}
	}
	return float32(matched) / float32(len(qTokens))
}

// Put upserts a memory entry validating taxonomy and dimension contracts.
func (s *SqliteMemoryStore) Put(ctx context.Context, e datastore.MemoryEntry) (datastore.MemoryEntry, error) {
	if e.ID == "" || e.TenantID == "" {
		return datastore.MemoryEntry{}, errors.New("dualvec: memory id and tenant_id are required")
	}
	if e.Kind != "" && !memoryKinds[e.Kind] {
		return datastore.MemoryEntry{}, fmt.Errorf("dualvec: unknown memory kind %q", e.Kind)
	}
	if !memoryACL[e.ACLScope] {
		return datastore.MemoryEntry{}, fmt.Errorf("dualvec: unknown acl_scope %q", e.ACLScope)
	}
	if len(e.Embedding) != 0 && len(e.Embedding) != EmbeddingDim {
		return datastore.MemoryEntry{}, fmt.Errorf("dualvec: embedding must have %d dimensions, got %d", EmbeddingDim, len(e.Embedding))
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	// Check tenancy on conflict
	var existingTenant, existingOwner string
	err := s.db.QueryRowContext(ctx, "SELECT tenant_id, owner FROM memory_entries WHERE id = ?", e.ID).Scan(&existingTenant, &existingOwner)
	if err == nil {
		if existingTenant != e.TenantID || existingOwner != e.Owner {
			return datastore.MemoryEntry{}, fmt.Errorf("dualvec: memory %s belongs to another tenant/owner", e.ID)
		}
	} else if !errors.Is(err, sql.ErrNoRows) {
		return datastore.MemoryEntry{}, fmt.Errorf("dualvec: check existing failed: %w", err)
	}

	vecBlob := encodeVector(e.Embedding)
	query := `
	INSERT INTO memory_entries (id, tenant_id, project_id, kind, object_ref, acl_scope, content, source, owner, embedding, updated_at)
	VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	ON CONFLICT(id) DO UPDATE SET
		project_id = excluded.project_id,
		kind = excluded.kind,
		object_ref = excluded.object_ref,
		acl_scope = excluded.acl_scope,
		content = excluded.content,
		source = excluded.source,
		owner = excluded.owner,
		embedding = excluded.embedding,
		updated_at = excluded.updated_at;
	`
	_, err = s.db.ExecContext(ctx, query,
		e.ID, e.TenantID, e.Project, e.Kind, e.ObjectRef, e.ACLScope,
		e.Content, e.Source, e.Owner, vecBlob, time.Now().UTC(),
	)
	if err != nil {
		return datastore.MemoryEntry{}, fmt.Errorf("dualvec: put failed: %w", err)
	}

	return s.getLocked(ctx, e.ID)
}

// Get reads a memory entry by ID.
func (s *SqliteMemoryStore) Get(ctx context.Context, id string) (datastore.MemoryEntry, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.getLocked(ctx, id)
}

func (s *SqliteMemoryStore) getLocked(ctx context.Context, id string) (datastore.MemoryEntry, error) {
	var e datastore.MemoryEntry
	var project sql.NullString
	var vecBlob []byte

	query := `
	SELECT id, tenant_id, project_id, kind, object_ref, acl_scope, content, source, owner, embedding
	FROM memory_entries WHERE id = ?
	`
	err := s.db.QueryRowContext(ctx, query, id).Scan(
		&e.ID, &e.TenantID, &project, &e.Kind, &e.ObjectRef, &e.ACLScope,
		&e.Content, &e.Source, &e.Owner, &vecBlob,
	)
	if errors.Is(err, sql.ErrNoRows) {
		return datastore.MemoryEntry{}, errors.New("dualvec: memory entry not found")
	}
	if err != nil {
		return datastore.MemoryEntry{}, fmt.Errorf("dualvec: get failed: %w", err)
	}
	if project.Valid {
		e.Project = project.String
	}
	e.Embedding = decodeVector(vecBlob)
	return e, nil
}

// Delete removes a memory entry by ID.
func (s *SqliteMemoryStore) Delete(ctx context.Context, id string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	res, err := s.db.ExecContext(ctx, "DELETE FROM memory_entries WHERE id = ?", id)
	if err != nil {
		return fmt.Errorf("dualvec: delete failed: %w", err)
	}
	n, _ := res.RowsAffected()
	if n == 0 {
		return errors.New("dualvec: memory entry not found")
	}
	return nil
}

type scoredEntry struct {
	entry datastore.MemoryEntry
	score float32
}

// Search queries memory entries applying strict tenant, project, ACL, and kind filters.
func (s *SqliteMemoryStore) Search(ctx context.Context, q string, scope datastore.MemoryScope, k int) ([]datastore.MemoryEntry, error) {
	if scope.TenantID == "" {
		return nil, errors.New("dualvec: tenant_id scope is required")
	}
	if k <= 0 {
		k = 10
	}

	s.mu.RLock()
	defer s.mu.RUnlock()

	var conditions []string
	var args []any

	// 1. Strict Tenant Isolation
	conditions = append(conditions, "tenant_id = ?")
	args = append(args, scope.TenantID)

	// 2. Project Scope Filter
	if scope.Project != "" {
		conditions = append(conditions, "(project_id = ? OR project_id IS NULL OR project_id = '')")
		args = append(args, scope.Project)
	}

	// 3. Source Filter
	if scope.Source != "" {
		conditions = append(conditions, "source = ?")
		args = append(args, scope.Source)
	}

	// 4. Kinds Filter
	if len(scope.Kinds) > 0 {
		placeholders := make([]string, len(scope.Kinds))
		for i, kind := range scope.Kinds {
			placeholders[i] = "?"
			args = append(args, kind)
		}
		conditions = append(conditions, fmt.Sprintf("kind IN (%s)", strings.Join(placeholders, ",")))
	}

	// 5. ACL Scope Predicate (Server-side privacy enforcement)
	// Private entries are strictly visible only to their owner.
	if scope.User != "" {
		conditions = append(conditions, "(acl_scope != 'private' OR owner = ?)")
		args = append(args, scope.User)
	} else {
		conditions = append(conditions, "acl_scope != 'private'")
	}

	whereClause := strings.Join(conditions, " AND ")
	query := fmt.Sprintf(`
	SELECT id, tenant_id, project_id, kind, object_ref, acl_scope, content, source, owner, embedding
	FROM memory_entries WHERE %s
	`, whereClause)

	rows, err := s.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("dualvec: search query failed: %w", err)
	}
	defer rows.Close()

	var candidates []scoredEntry
	hasVectorQuery := len(scope.Vector) == EmbeddingDim
	hasTextQuery := strings.TrimSpace(q) != ""

	for rows.Next() {
		var e datastore.MemoryEntry
		var project sql.NullString
		var vecBlob []byte

		if err := rows.Scan(
			&e.ID, &e.TenantID, &project, &e.Kind, &e.ObjectRef, &e.ACLScope,
			&e.Content, &e.Source, &e.Owner, &vecBlob,
		); err != nil {
			return nil, err
		}
		if project.Valid {
			e.Project = project.String
		}
		e.Embedding = decodeVector(vecBlob)

		var finalScore float32
		if hasVectorQuery && len(e.Embedding) == EmbeddingDim {
			vecScore := cosineSimilarity(scope.Vector, e.Embedding)
			if hasTextQuery {
				lexScore := lexicalScore(q, e.Content)
				finalScore = 0.7*vecScore + 0.3*lexScore
			} else {
				finalScore = vecScore
			}
		} else if hasTextQuery {
			finalScore = lexicalScore(q, e.Content)
		} else {
			finalScore = 1.0 // Unfiltered match
		}

		// Only retain non-zero or matched entries if a query was specified
		if (hasVectorQuery || hasTextQuery) && finalScore <= 0 {
			continue
		}

		e.Score = finalScore
		candidates = append(candidates, scoredEntry{entry: e, score: finalScore})
	}

	if err := rows.Err(); err != nil {
		return nil, err
	}

	// Deterministic sort: score DESC, id ASC
	sort.Slice(candidates, func(i, j int) bool {
		if math.Abs(float64(candidates[i].score-candidates[j].score)) > 1e-6 {
			return candidates[i].score > candidates[j].score
		}
		return candidates[i].entry.ID < candidates[j].entry.ID
	})

	if len(candidates) > k {
		candidates = candidates[:k]
	}

	results := make([]datastore.MemoryEntry, len(candidates))
	for i, c := range candidates {
		results[i] = c.entry
	}
	return results, nil
}
