package dualvec

import (
	"context"
	"fmt"
	"math"
	"os"
	"sync"
	"testing"
	"time"

	"productforge/datastore"
	"productforge/store"
)

func makeUnitVector(dim int, primaryIdx int) []float32 {
	v := make([]float32, dim)
	if primaryIdx >= 0 && primaryIdx < dim {
		v[primaryIdx] = 1.0
	}
	return v
}

func makeBlendedVector(dim int, idxA, idxB int, weightA, weightB float32) []float32 {
	v := make([]float32, dim)
	v[idxA] = weightA
	v[idxB] = weightB
	norm := float32(math.Sqrt(float64(weightA*weightA + weightB*weightB)))
	if norm > 0 {
		v[idxA] /= norm
		v[idxB] /= norm
	}
	return v
}

func TestEngineDetection(t *testing.T) {
	tests := []struct {
		dsn      string
		expected EngineType
	}{
		{"", EngineSQLite},
		{":memory:", EngineSQLite},
		{"sqlite://./data/agent.db", EngineSQLite},
		{"sqlite3://local.db", EngineSQLite},
		{"file:memory.db?cache=shared", EngineSQLite},
		{"postgres://user:pass@localhost:5432/db", EnginePostgres},
		{"postgresql://user:pass@localhost:5432/db", EnginePostgres},
	}
	for _, tc := range tests {
		got := DetectEngine(tc.dsn)
		if got != tc.expected {
			t.Errorf("DetectEngine(%q) = %v; want %v", tc.dsn, got, tc.expected)
		}
	}
}

// runMemoryConformance verifies the 8 canonical memory types, vector validation, ACL scoping,
// and isolation guarantees across any datastore.MemoryRepository backend (AC-1, AC-2, AC-3, AC-4).
func runMemoryConformance(t *testing.T, store datastore.MemoryRepository, tenant string) {
	ctx := context.Background()

	// 1. All eight canonical memory kinds must be accepted
	kinds := []string{
		"raw_evidence", "semantic", "episodic", "decision",
		"procedural", "failure", "policy", "working",
	}
	for i, kind := range kinds {
		e := datastore.MemoryEntry{
			ID:        fmt.Sprintf("%s-kind-%d", tenant, i),
			TenantID:  tenant,
			Project:   fmt.Sprintf("proj-%s", tenant),
			Kind:      kind,
			ACLScope:  "project",
			Content:   fmt.Sprintf("Memory content for kind %s", kind),
			Source:    "test-conformance",
			Owner:     "tester",
			Embedding: makeUnitVector(EmbeddingDim, i),
		}
		got, err := store.Put(ctx, e)
		if err != nil {
			t.Fatalf("Put failed for canonical kind %q: %v", kind, err)
		}
		if got.Kind != kind {
			t.Errorf("got kind %q; want %q", got.Kind, kind)
		}
	}

	// 2. Unknown memory kind must fail closed
	_, err := store.Put(ctx, datastore.MemoryEntry{
		ID:       fmt.Sprintf("%s-invalid-kind", tenant),
		TenantID: tenant,
		Kind:     "hallucinated_kind",
		ACLScope: "project",
		Owner:    "tester",
	})
	if err == nil {
		t.Fatal("expected error for unknown memory kind, got nil")
	}

	// 3. Unknown ACL scope must fail closed
	_, err = store.Put(ctx, datastore.MemoryEntry{
		ID:       fmt.Sprintf("%s-invalid-acl", tenant),
		TenantID: tenant,
		Kind:     "semantic",
		ACLScope: "super_public",
		Owner:    "tester",
	})
	if err == nil {
		t.Fatal("expected error for unknown ACL scope, got nil")
	}

	// 4. Invalid vector dimension must fail closed
	_, err = store.Put(ctx, datastore.MemoryEntry{
		ID:        fmt.Sprintf("%s-invalid-dim", tenant),
		TenantID:  tenant,
		Kind:      "semantic",
		ACLScope:  "project",
		Owner:     "tester",
		Embedding: []float32{1.0, 2.0, 3.0}, // Only 3 dims, requires 1536
	})
	if err == nil {
		t.Fatal("expected error for vector dimension mismatch, got nil")
	}

	// 5. Nearest neighbor vector ranking
	targetID := fmt.Sprintf("%s-target", tenant)
	distractorID := fmt.Sprintf("%s-distractor", tenant)
	orthogonalID := fmt.Sprintf("%s-orthogonal", tenant)

	_, err = store.Put(ctx, datastore.MemoryEntry{
		ID:        targetID,
		TenantID:  tenant,
		Kind:      "semantic",
		ACLScope:  "project",
		Content:   "Highly relevant vector target",
		Embedding: makeBlendedVector(EmbeddingDim, 10, 20, 0.95, 0.05),
	})
	if err != nil {
		t.Fatalf("Put target failed: %v", err)
	}

	_, err = store.Put(ctx, datastore.MemoryEntry{
		ID:        distractorID,
		TenantID:  tenant,
		Kind:      "semantic",
		ACLScope:  "project",
		Content:   "Partially relevant distractor",
		Embedding: makeBlendedVector(EmbeddingDim, 10, 20, 0.5, 0.5),
	})
	if err != nil {
		t.Fatalf("Put distractor failed: %v", err)
	}

	_, err = store.Put(ctx, datastore.MemoryEntry{
		ID:        orthogonalID,
		TenantID:  tenant,
		Kind:      "semantic",
		ACLScope:  "project",
		Content:   "Completely orthogonal entry",
		Embedding: makeUnitVector(EmbeddingDim, 100),
	})
	if err != nil {
		t.Fatalf("Put orthogonal failed: %v", err)
	}

	queryScope := datastore.MemoryScope{
		TenantID: tenant,
		Vector:   makeUnitVector(EmbeddingDim, 10),
	}
	hits, err := store.Search(ctx, "target", queryScope, 3)
	if err != nil {
		t.Fatalf("Search failed: %v", err)
	}
	if len(hits) == 0 {
		t.Fatal("expected search hits, got 0")
	}
	if hits[0].ID != targetID {
		t.Errorf("top ranked result = %q; want %q", hits[0].ID, targetID)
	}

	// 6. Negative Leakage Isolation (Tenant and ACL)
	otherTenant := tenant + "-other"
	_, _ = store.Put(ctx, datastore.MemoryEntry{
		ID:       fmt.Sprintf("%s-priv", tenant),
		TenantID: tenant,
		Kind:     "decision",
		ACLScope: "private",
		Owner:    "alice",
		Content:  "Secret private decision",
	})

	hitsOtherUser, err := store.Search(ctx, "", datastore.MemoryScope{
		TenantID: tenant,
		User:     "bob",
	}, 10)
	if err != nil {
		t.Fatalf("Search for other user failed: %v", err)
	}
	for _, h := range hitsOtherUser {
		if h.ID == fmt.Sprintf("%s-priv", tenant) {
			t.Errorf("PRIVACY LEAKAGE: Bob was able to view Alice's private entry %q", h.ID)
		}
	}

	// Cross-tenant search must return zero rows from this tenant
	hitsOtherTenant, err := store.Search(ctx, "", datastore.MemoryScope{
		TenantID: otherTenant,
	}, 10)
	if err != nil {
		t.Fatalf("Search for other tenant failed: %v", err)
	}
	for _, h := range hitsOtherTenant {
		if h.TenantID == tenant {
			t.Errorf("CROSS-TENANT LEAKAGE: Other tenant retrieved entry belonging to %q", tenant)
		}
	}
}

func TestSqliteMemoryStoreConformance(t *testing.T) {
	store, err := NewSqliteMemoryStore(":memory:")
	if err != nil {
		t.Fatalf("failed to create sqlite store: %v", err)
	}
	defer store.Close()

	runMemoryConformance(t, store, "sqlite-tenant")
}

func TestPgMemoryStoreConformance(t *testing.T) {
	dsn := os.Getenv("PF_RUNTIME_DSN")
	if dsn == "" {
		dsn = os.Getenv("PF_DB_DSN")
	}
	if dsn == "" {
		t.Skip("skipping PG conformance test: PF_DB_DSN / PF_RUNTIME_DSN not set")
	}
	ctx := context.Background()
	st, err := store.Open(ctx, dsn)
	if err != nil {
		t.Skipf("skipping PG conformance test: unable to connect to DB: %v", err)
	}
	defer st.Close()

	tenant := fmt.Sprintf("pg-conf-%d", time.Now().UnixNano()%1000000)
	otherTenant := tenant + "-other"

	if err := st.WithTx(ctx, func(tx datastore.Tx) error {
		if _, e := tx.Exec(ctx, `SELECT set_config('app.tenant_id', $1, true)`, tenant); e != nil {
			return e
		}
		if _, e := tx.Exec(ctx, `INSERT INTO tenants (id, slug, name, region, status) VALUES ($1,$1,$1,'','active')`, tenant); e != nil {
			return e
		}
		projID := fmt.Sprintf("proj-%s", tenant)
		if _, e := tx.Exec(ctx, `INSERT INTO projects (id, tenant_id, slug, name, status) VALUES ($1, $2, $1, $1, 'active')`, projID, tenant); e != nil {
			return e
		}
		return nil
	}); err != nil {
		t.Skipf("skipping PG conformance test: unable to seed test tenant: %v", err)
	}

	_ = st.WithTx(ctx, func(tx datastore.Tx) error {
		_, _ = tx.Exec(ctx, `SELECT set_config('app.tenant_id', $1, true)`, otherTenant)
		_, _ = tx.Exec(ctx, `INSERT INTO tenants (id, slug, name, region, status) VALUES ($1,$1,$1,'','active')`, otherTenant)
		return nil
	})

	t.Cleanup(func() {
		_ = st.WithTx(context.Background(), func(tx datastore.Tx) error {
			projID := fmt.Sprintf("proj-%s", tenant)
			_, _ = tx.Exec(context.Background(), `SELECT set_config('app.tenant_id', $1, true)`, tenant)
			_, _ = tx.Exec(context.Background(), `DELETE FROM projects WHERE id=$1`, projID)
			_, _ = tx.Exec(context.Background(), `DELETE FROM tenants WHERE id=$1`, tenant)
			_, _ = tx.Exec(context.Background(), `SELECT set_config('app.tenant_id', $1, true)`, otherTenant)
			_, _ = tx.Exec(context.Background(), `DELETE FROM tenants WHERE id=$1`, otherTenant)
			return nil
		})
	})

	pgStore := NewPgMemoryStore(store.BindTenant(st, tenant))
	runMemoryConformance(t, pgStore, tenant)
}

type testObserver struct {
	mu     sync.Mutex
	events []string
}

func (o *testObserver) Observe(engine EngineType, op string, tenant string, project string, duration time.Duration, err error) {
	o.mu.Lock()
	defer o.mu.Unlock()
	o.events = append(o.events, fmt.Sprintf("%s:%s", engine, op))
}

func TestDualVecObservability(t *testing.T) {
	obs := &testObserver{}
	SetObserver(obs)
	defer SetObserver(nil)

	store, err := NewSqliteMemoryStore(":memory:")
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer store.Close()

	ctx := context.Background()
	_, _ = store.Put(ctx, datastore.MemoryEntry{
		ID:       "obs-test-1",
		TenantID: "tenant-obs",
		Kind:     "semantic",
		ACLScope: "project",
		Content:  "Telemetry test content",
	})
	_, _ = store.Get(ctx, "obs-test-1")
	_, _ = store.Search(ctx, "test", datastore.MemoryScope{TenantID: "tenant-obs"}, 5)
	_ = store.Delete(ctx, "obs-test-1")

	obs.mu.Lock()
	defer obs.mu.Unlock()

	expectedOps := []string{"sqlite:Put", "sqlite:Get", "sqlite:Search", "sqlite:Delete"}
	for _, expected := range expectedOps {
		found := false
		for _, ev := range obs.events {
			if ev == expected {
				found = true
				break
			}
		}
		if !found {
			t.Errorf("expected observability event %q; got events %v", expected, obs.events)
		}
	}
}
