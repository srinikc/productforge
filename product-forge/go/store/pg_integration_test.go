package store

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"testing"
	"time"

	"productforge/migrate"
)

// TestPgIntegration runs the DAL against a real PostgreSQL instance. It self-skips unless PF_DB_DSN is set
// (so CI/offline stays green), and applies the migrations first (idempotent).
func TestPgIntegration(t *testing.T) {
	dsn := os.Getenv("PF_DB_DSN")
	if dsn == "" {
		t.Skip("PF_DB_DSN not set - skipping PostgreSQL integration test")
	}
	ctx := context.Background()
	pg, err := Open(ctx, dsn)
	if err != nil {
		t.Fatalf("open: %v", err)
	}
	defer pg.Close()

	migs, err := migrate.LoadDir(filepath.Join("..", "..", "migrations"))
	if err != nil {
		t.Fatalf("load migrations: %v", err)
	}
	if _, err := migrate.Up(ctx, pg, migs); err != nil {
		t.Fatalf("migrate: %v", err)
	}

	repos := NewPostgres(pg)
	id := fmt.Sprintf("it-%d", time.Now().UnixNano())

	tn, err := repos.Tenants.Create(ctx, Tenant{ID: id, Slug: id, Name: "IT", Region: "in-v1"})
	if err != nil {
		t.Fatalf("create tenant: %v", err)
	}
	if tn.Version != 0 {
		t.Fatalf("new tenant version = %d, want 0", tn.Version)
	}

	// optimistic update with the correct version succeeds and bumps the version
	up, err := repos.Tenants.Update(ctx, id, tn.Version, "IT-renamed", "active")
	if err != nil {
		t.Fatalf("update tenant: %v", err)
	}
	if up.Version != tn.Version+1 || up.Name != "IT-renamed" {
		t.Fatalf("update result = %+v", up)
	}

	// a stale expected version must conflict (no silent clobber)
	if _, err := repos.Tenants.Update(ctx, id, tn.Version, "IT-x", "active"); !errors.Is(err, ErrVersionConflict) {
		t.Fatalf("stale update: want ErrVersionConflict, got %v", err)
	}

	// projects (tenant listing hot path)
	if _, err := repos.Projects.Create(ctx, Project{ID: id + "-p", TenantID: id, Slug: "p1", Name: "P1"}); err != nil {
		t.Fatalf("create project: %v", err)
	}
	ps, err := repos.Projects.ListByTenant(ctx, id)
	if err != nil {
		t.Fatalf("list projects: %v", err)
	}
	if len(ps) != 1 || ps[0].Slug != "p1" {
		t.Fatalf("projects = %+v", ps)
	}

	if err := repos.Tenants.Delete(ctx, id); err != nil {
		t.Fatalf("delete tenant: %v", err)
	}
	if _, err := repos.Tenants.Get(ctx, id); !errors.Is(err, ErrNotFound) {
		t.Fatalf("get after delete: want ErrNotFound, got %v", err)
	}
}
