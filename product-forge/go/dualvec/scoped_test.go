package dualvec

import (
	"context"
	"errors"
	"testing"

	"productforge/datastore"
)

func TestScopedMemoryOperations(t *testing.T) {
	store, err := NewSqliteMemoryStore(":memory:")
	if err != nil {
		t.Fatal(err)
	}
	defer store.Close()
	ctx := context.Background()
	entries := []datastore.MemoryEntry{
		{ID: "scope-a", TenantID: "tenant-a", Project: "proj-1", Kind: "semantic", ACLScope: "project", Content: "alpha", Owner: "alice"},
		{ID: "scope-b", TenantID: "tenant-b", Project: "proj-1", Kind: "semantic", ACLScope: "project", Content: "alpha", Owner: "bob"},
		{ID: "scope-p2", TenantID: "tenant-a", Project: "proj-2", Kind: "semantic", ACLScope: "project", Content: "alpha", Owner: "alice"},
		{ID: "scope-private", TenantID: "tenant-a", Project: "proj-1", Kind: "semantic", ACLScope: "private", Content: "alpha", Owner: "alice"},
	}
	for _, e := range entries {
		if _, err := store.Put(ctx, e); err != nil {
			t.Fatalf("put %s: %v", e.ID, err)
		}
	}

	scope := datastore.MemoryScope{TenantID: "tenant-a", Project: "proj-1", User: "alice"}
	if _, err := store.GetScoped(ctx, "scope-a", scope); err != nil {
		t.Fatalf("scoped get: %v", err)
	}
	if _, err := store.GetScoped(ctx, "scope-b", scope); !errors.Is(err, datastore.ErrNotFound) {
		t.Fatalf("cross-tenant scoped get: %v", err)
	}
	if _, err := store.GetScoped(ctx, "scope-p2", scope); !errors.Is(err, datastore.ErrNotFound) {
		t.Fatalf("cross-project scoped get: %v", err)
	}
	if _, err := store.GetScoped(ctx, "scope-private", datastore.MemoryScope{TenantID: "tenant-a", Project: "proj-1", User: "bob"}); !errors.Is(err, datastore.ErrNotFound) {
		t.Fatalf("private scoped get: %v", err)
	}
	hits, err := store.Search(ctx, "alpha", scope, 10)
	if err != nil {
		t.Fatal(err)
	}
	if len(hits) != 2 {
		t.Fatalf("scoped search hits=%d want 2", len(hits))
	}
	for _, hit := range hits {
		if hit.TenantID != "tenant-a" || hit.Project != "proj-1" {
			t.Fatalf("leaked hit: %+v", hit)
		}
	}
	if err := store.DeleteScoped(ctx, "scope-b", scope); !errors.Is(err, datastore.ErrNotFound) {
		t.Fatalf("cross-tenant scoped delete: %v", err)
	}
	if _, err := store.Get(ctx, "scope-b"); err != nil {
		t.Fatalf("record must remain after denied delete: %v", err)
	}
	if err := store.DeleteScoped(ctx, "scope-a", scope); err != nil {
		t.Fatalf("scoped delete: %v", err)
	}
}
