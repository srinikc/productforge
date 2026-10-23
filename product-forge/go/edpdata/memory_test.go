package edpdata

import (
	"context"
	"fmt"
	"os"
	"testing"
	"time"

	"productforge/datastore"
	"productforge/store"
)

func memorySetup(t *testing.T) (*store.PgStore, context.Context, string) {
	t.Helper()
	dsn := os.Getenv("PF_DB_DSN")
	if dsn == "" {
		if os.Getenv("PF_REQUIRE_MEMORY_TESTS") == "1" {
			t.Fatal("PF_REQUIRE_MEMORY_TESTS=1 but PF_DB_DSN is unset")
		}
		t.Skip("PF_DB_DSN not set - skipping memory integration test")
	}
	ctx := context.Background()
	st, err := store.Open(ctx, dsn)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(st.Close)
	tenant := fmt.Sprintf("mem-%d", time.Now().UnixNano())
	if err := st.WithTx(ctx, func(tx datastore.Tx) error {
		if _, e := tx.Exec(ctx, `INSERT INTO tenants (id, slug, name, region, status) VALUES ($1,$1,$1,'','active')`, tenant); e != nil {
			return e
		}
		for _, p := range []string{"p1", "p2"} {
			if _, e := tx.Exec(ctx, `INSERT INTO projects (id, tenant_id, slug, name, status) VALUES ($1,$2,$1,$1,'active')`, p, tenant); e != nil {
				return e
			}
		}
		return nil
	}); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		_ = st.WithTx(context.Background(), func(tx datastore.Tx) error {
			_, _ = tx.Exec(context.Background(), `DELETE FROM tenants WHERE id=$1`, tenant)
			return nil
		})
	})
	return st, ctx, tenant
}

func TestMemoryEightTypesAndFTS(t *testing.T) {
	st, ctx, tenant := memorySetup(t)
	mem := NewMemory(store.BindTenant(st, tenant))
	kinds := []string{"raw_evidence", "semantic", "episodic", "decision", "procedural", "failure", "policy", "working"}
	for i, k := range kinds {
		if _, err := mem.Put(ctx, datastore.MemoryEntry{
			ID: fmt.Sprintf("%s-%s", tenant, k), TenantID: tenant, Kind: k,
			Content: fmt.Sprintf("entry %d about quarterly revenue growth and margins", i),
			Source:  "test", Owner: "alice", ACLScope: "project", Project: "p1",
		}); err != nil {
			t.Fatalf("put %s: %v", k, err)
		}
	}
	if _, err := mem.Put(ctx, datastore.MemoryEntry{ID: tenant + "-bad", TenantID: tenant, Kind: "nonsense"}); err == nil {
		t.Fatal("unknown memory kind must be rejected")
	}
	hits, err := mem.Search(ctx, "revenue growth", datastore.MemoryScope{TenantID: tenant}, 20)
	if err != nil {
		t.Fatal(err)
	}
	if len(hits) != 8 {
		t.Fatalf("FTS hits = %d, want 8", len(hits))
	}
	for i := 1; i < len(hits); i++ {
		if hits[i].Score > hits[i-1].Score {
			t.Fatalf("FTS results are not ranked: %f > %f", hits[i].Score, hits[i-1].Score)
		}
	}
	only, err := mem.Search(ctx, "revenue", datastore.MemoryScope{TenantID: tenant, Kinds: []string{"policy"}}, 20)
	if err != nil {
		t.Fatal(err)
	}
	if len(only) != 1 || only[0].Kind != "policy" {
		t.Fatalf("kind filter mismatch: %+v", only)
	}
	if _, err := mem.Search(ctx, "revenue", datastore.MemoryScope{TenantID: tenant, Vector: []float32{1, 2}}, 20); err == nil {
		t.Fatal("wrong embedding dimension must fail closed")
	}
}

func TestMemoryACLLeakage(t *testing.T) {
	st, ctx, tenant := memorySetup(t)
	other := tenant + "-other"
	if err := st.WithTx(ctx, func(tx datastore.Tx) error {
		_, e := tx.Exec(ctx, `INSERT INTO tenants (id, slug, name, region, status) VALUES ($1,$1,$1,'','active')`, other)
		return e
	}); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		_ = st.WithTx(context.Background(), func(tx datastore.Tx) error {
			_, _ = tx.Exec(context.Background(), `DELETE FROM tenants WHERE id=$1`, other)
			return nil
		})
	})
	mem := NewMemory(store.BindTenant(st, tenant))
	put := func(id, project, source, owner, acl string) {
		if _, err := mem.Put(ctx, datastore.MemoryEntry{ID: id, TenantID: tenant, Project: project,
			Source: source, Owner: owner, ACLScope: acl, Kind: "semantic", Content: "secret revenue plan"}); err != nil {
			t.Fatalf("put %s: %v", id, err)
		}
	}
	put("p1-a", "p1", "s1", "alice", "private")
	put("p1-b", "p1", "s1", "bob", "private")
	put("p2-a", "p2", "s1", "alice", "project")
	put("p1-s2", "p1", "s2", "alice", "project")
	put("public", "p1", "s1", "carol", "tenant")

	mustNotSee := func(name string, scope datastore.MemoryScope, forbidden ...string) {
		hits, err := mem.Search(ctx, "revenue", scope, 50)
		if err != nil {
			t.Fatalf("%s: %v", name, err)
		}
		got := map[string]bool{}
		for _, h := range hits {
			got[h.ID] = true
		}
		for _, id := range forbidden {
			if got[id] {
				t.Fatalf("%s leaked %s", name, id)
			}
		}
	}
	mustNotSee("other project", datastore.MemoryScope{TenantID: tenant, Project: "p1", User: "alice"},
		"p2-a")
	mustNotSee("other source", datastore.MemoryScope{TenantID: tenant, Source: "s1", User: "alice"},
		"p1-s2")
	mustNotSee("other user private", datastore.MemoryScope{TenantID: tenant, User: "alice"},
		"p1-b")
	mustNotSee("no user private", datastore.MemoryScope{TenantID: tenant},
		"p1-a", "p1-b")
	hits, err := mem.Search(ctx, "revenue", datastore.MemoryScope{TenantID: tenant, User: "alice"}, 50)
	if err != nil {
		t.Fatal(err)
	}
	found := false
	for _, h := range hits {
		if h.ID == "p1-a" {
			found = true
		}
	}
	if !found {
		t.Fatal("owner must see their private entry")
	}
	// Tenant isolation: a search scoped to the other tenant must return nothing from this tenant.
	cross, err := mem.Search(ctx, "revenue", datastore.MemoryScope{TenantID: other}, 50)
	if err != nil {
		t.Fatal(err)
	}
	if len(cross) != 0 {
		t.Fatalf("cross-tenant leakage: %+v", cross)
	}
}
