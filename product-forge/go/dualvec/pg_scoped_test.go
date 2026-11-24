package dualvec

import (
	"context"
	"errors"
	"os"
	"testing"

	"productforge/datastore"
	"productforge/store"
)

func TestPgScopedMemory(t *testing.T) {
	dsn := os.Getenv("PF_TEST_MEMORY_DSN")
	if dsn == "" {
		dsn = os.Getenv("PF_DB_DSN")
	}
	if dsn == "" {
		t.Skip("PF_TEST_MEMORY_DSN/PF_DB_DSN not set")
	}
	ctx := context.Background()
	st, err := store.Open(ctx, dsn)
	if err != nil {
		t.Fatal(err)
	}
	defer st.Close()
	const tenant = "pfmemory-test-tenant"
	const project = "pfmemory-test-project"
	err = st.WithTx(ctx, func(tx datastore.Tx) error {
		if _, err := tx.Exec(ctx, `SELECT set_config('app.tenant_id', $1, true)`, tenant); err != nil {
			return err
		}
		if _, err := tx.Exec(ctx, `INSERT INTO tenants (id, slug, name, region, status) VALUES ($1,$1,$1,'','active') ON CONFLICT (id) DO NOTHING`, tenant); err != nil {
			return err
		}
		_, err := tx.Exec(ctx, `INSERT INTO projects (id, tenant_id, slug, name, status) VALUES ($1,$2,$1,$1,'active') ON CONFLICT (id) DO NOTHING`, project, tenant)
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
	repo := NewPgMemoryStore(store.BindTenant(st, tenant))
	entry := datastore.MemoryEntry{ID: "pg-scoped-1", TenantID: tenant, Project: project, Kind: "semantic",
		ACLScope: "project", Content: "pg scoped", Owner: "alice"}
	if _, err := repo.Put(ctx, entry); err != nil {
		t.Fatal(err)
	}
	scope := datastore.MemoryScope{TenantID: tenant, Project: project, User: "alice"}
	if _, err := repo.GetScoped(ctx, entry.ID, scope); err != nil {
		t.Fatalf("scoped get: %v", err)
	}
	if _, err := repo.GetScoped(ctx, entry.ID, datastore.MemoryScope{TenantID: tenant, Project: "other", User: "alice"}); !errors.Is(err, datastore.ErrNotFound) {
		t.Fatalf("cross-project get: %v", err)
	}
	if err := repo.DeleteScoped(ctx, entry.ID, datastore.MemoryScope{TenantID: "other", Project: project, User: "alice"}); !errors.Is(err, datastore.ErrNotFound) {
		t.Fatalf("cross-tenant delete: %v", err)
	}
	if err := repo.DeleteScoped(ctx, entry.ID, scope); err != nil {
		t.Fatalf("scoped delete: %v", err)
	}
}
