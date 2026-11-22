package dualvec

import (
	"context"
	"fmt"
	"math"
	"testing"

	"productforge/datastore"
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
	// Normalize
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

func TestSqliteMemoryStoreConformance(t *testing.T) {
	ctx := context.Background()
	store, err := NewSqliteMemoryStore(":memory:")
	if err != nil {
		t.Fatalf("failed to create sqlite store: %v", err)
	}
	defer store.Close()

	// 1. All eight canonical memory kinds must be accepted
	kinds := []string{
		"raw_evidence", "semantic", "episodic", "decision",
		"procedural", "failure", "policy", "working",
	}
	for i, kind := range kinds {
		e := datastore.MemoryEntry{
			ID:        fmt.Sprintf("mem-kind-%d", i),
			TenantID:  "tenant-conformance",
			Project:   "proj-conformance",
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
	_, err = store.Put(ctx, datastore.MemoryEntry{
		ID:       "invalid-kind",
		TenantID: "tenant-conformance",
		Kind:     "hallucinated_kind",
		ACLScope: "project",
		Owner:    "tester",
	})
	if err == nil {
		t.Fatal("expected error for unknown memory kind, got nil")
	}

	// 3. Unknown ACL scope must fail closed
	_, err = store.Put(ctx, datastore.MemoryEntry{
		ID:       "invalid-acl",
		TenantID: "tenant-conformance",
		Kind:     "semantic",
		ACLScope: "super_public",
		Owner:    "tester",
	})
	if err == nil {
		t.Fatal("expected error for unknown ACL scope, got nil")
	}

	// 4. Invalid vector dimension must fail closed
	_, err = store.Put(ctx, datastore.MemoryEntry{
		ID:        "invalid-dim",
		TenantID:  "tenant-conformance",
		Kind:      "semantic",
		ACLScope:  "project",
		Owner:     "tester",
		Embedding: []float32{1.0, 2.0, 3.0}, // Only 3 dims, requires 1536
	})
	if err == nil {
		t.Fatal("expected error for invalid vector dimension, got nil")
	}

	// 5. Get and Delete operations
	getEntry, err := store.Get(ctx, "mem-kind-0")
	if err != nil {
		t.Fatalf("Get failed: %v", err)
	}
	if getEntry.ID != "mem-kind-0" {
		t.Errorf("Get returned ID %q; want mem-kind-0", getEntry.ID)
	}
	if len(getEntry.Embedding) != EmbeddingDim {
		t.Errorf("Get returned %d dims; want %d", len(getEntry.Embedding), EmbeddingDim)
	}

	if err := store.Delete(ctx, "mem-kind-0"); err != nil {
		t.Fatalf("Delete failed: %v", err)
	}
	_, err = store.Get(ctx, "mem-kind-0")
	if err == nil {
		t.Fatal("expected error after delete, got nil")
	}
}

func TestNearestNeighborVectorRanking(t *testing.T) {
	ctx := context.Background()
	store, err := NewSqliteMemoryStore(":memory:")
	if err != nil {
		t.Fatalf("failed to create sqlite store: %v", err)
	}
	defer store.Close()

	// Insert three items with varying vector similarities to index 10:
	// Item 1: Exactly aligned with index 10 (cosine similarity = 1.0)
	// Item 2: Blended with index 10 and 20 (cosine similarity ~ 0.707)
	// Item 3: Orthogonal (aligned with index 30, cosine similarity = 0.0)
	queryVec := makeUnitVector(EmbeddingDim, 10)

	_, err = store.Put(ctx, datastore.MemoryEntry{
		ID:        "item-exact",
		TenantID:  "t1",
		Kind:      "semantic",
		ACLScope:  "tenant",
		Content:   "Alpha architecture documentation",
		Owner:     "architect",
		Embedding: queryVec,
	})
	if err != nil {
		t.Fatalf("Put exact failed: %v", err)
	}

	_, err = store.Put(ctx, datastore.MemoryEntry{
		ID:        "item-blended",
		TenantID:  "t1",
		Kind:      "semantic",
		ACLScope:  "tenant",
		Content:   "Beta design patterns",
		Owner:     "architect",
		Embedding: makeBlendedVector(EmbeddingDim, 10, 20, 0.7, 0.7),
	})
	if err != nil {
		t.Fatalf("Put blended failed: %v", err)
	}

	_, err = store.Put(ctx, datastore.MemoryEntry{
		ID:        "item-orthogonal",
		TenantID:  "t1",
		Kind:      "semantic",
		ACLScope:  "tenant",
		Content:   "Gamma unrelated code",
		Owner:     "architect",
		Embedding: makeUnitVector(EmbeddingDim, 30),
	})
	if err != nil {
		t.Fatalf("Put orthogonal failed: %v", err)
	}

	// Search by query vector
	results, err := store.Search(ctx, "", datastore.MemoryScope{
		TenantID: "t1",
		Vector:   queryVec,
	}, 10)
	if err != nil {
		t.Fatalf("Search failed: %v", err)
	}

	if len(results) < 2 {
		t.Fatalf("expected at least 2 non-zero results, got %d", len(results))
	}

	if results[0].ID != "item-exact" {
		t.Errorf("Rank 1 item = %q; want item-exact", results[0].ID)
	}
	if results[1].ID != "item-blended" {
		t.Errorf("Rank 2 item = %q; want item-blended", results[1].ID)
	}
	if results[0].Score <= results[1].Score {
		t.Errorf("Score 1 (%f) should be strictly greater than Score 2 (%f)", results[0].Score, results[1].Score)
	}
}

func TestNegativeLeakageIsolation(t *testing.T) {
	ctx := context.Background()
	store, err := NewSqliteMemoryStore(":memory:")
	if err != nil {
		t.Fatalf("failed to create sqlite store: %v", err)
	}
	defer store.Close()

	// Seed Tenant A and Tenant B data
	_, _ = store.Put(ctx, datastore.MemoryEntry{
		ID:       "tenant-a-public",
		TenantID: "tenant-A",
		Project:  "project-A",
		Kind:     "policy",
		ACLScope: "tenant",
		Content:  "Secret internal policy of Tenant A",
		Source:   "source-A",
		Owner:    "alice",
	})

	_, _ = store.Put(ctx, datastore.MemoryEntry{
		ID:       "tenant-a-private",
		TenantID: "tenant-A",
		Project:  "project-A",
		Kind:     "decision",
		ACLScope: "private",
		Content:  "Alice private decision for Tenant A",
		Source:   "source-A",
		Owner:    "alice",
	})

	_, _ = store.Put(ctx, datastore.MemoryEntry{
		ID:       "tenant-b-public",
		TenantID: "tenant-B",
		Project:  "project-B",
		Kind:     "policy",
		ACLScope: "tenant",
		Content:  "Public policy of Tenant B",
		Source:   "source-B",
		Owner:    "bob",
	})

	// Negative Test 1: Tenant B search must NEVER return Tenant A rows
	resultsB, err := store.Search(ctx, "policy", datastore.MemoryScope{
		TenantID: "tenant-B",
		User:     "bob",
	}, 10)
	if err != nil {
		t.Fatalf("Search Tenant B failed: %v", err)
	}
	for _, r := range resultsB {
		if r.TenantID != "tenant-B" {
			t.Errorf("CROSS-TENANT LEAKAGE: Tenant B retrieved entry belonging to %q", r.TenantID)
		}
	}

	// Negative Test 2: Project-scoped isolation
	resultsProj, err := store.Search(ctx, "policy", datastore.MemoryScope{
		TenantID: "tenant-A",
		Project:  "project-X", // Non-matching project
	}, 10)
	if err != nil {
		t.Fatalf("Search failed: %v", err)
	}
	for _, r := range resultsProj {
		if r.Project != "" && r.Project != "project-X" {
			t.Errorf("CROSS-PROJECT LEAKAGE: Project X query retrieved Project %q", r.Project)
		}
	}

	// Negative Test 3: Private entries must NOT be visible to other users in the same tenant
	resultsSameTenantOtherUser, err := store.Search(ctx, "", datastore.MemoryScope{
		TenantID: "tenant-A",
		User:     "charlie", // Charlie in Tenant A should NOT see Alice's private entry
	}, 10)
	if err != nil {
		t.Fatalf("Search failed: %v", err)
	}
	for _, r := range resultsSameTenantOtherUser {
		if r.ID == "tenant-a-private" {
			t.Errorf("PRIVACY LEAKAGE: Charlie accessed Alice's private memory entry")
		}
	}

	// Affirmative test: Alice CAN see her own private entry
	resultsAlice, err := store.Search(ctx, "", datastore.MemoryScope{
		TenantID: "tenant-A",
		User:     "alice",
	}, 10)
	if err != nil {
		t.Fatalf("Search failed: %v", err)
	}
	foundAlicePrivate := false
	for _, r := range resultsAlice {
		if r.ID == "tenant-a-private" {
			foundAlicePrivate = true
			break
		}
	}
	if !foundAlicePrivate {
		t.Error("expected Alice to be able to retrieve her own private memory entry")
	}
}
