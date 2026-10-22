package pfaudit

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"productforge/migrate"
	"productforge/store"
)

func setup(t *testing.T) *pgxpool.Pool {
	t.Helper()
	dsn := os.Getenv("PF_DB_DSN")
	if dsn == "" {
		t.Skip("PF_DB_DSN not set - skipping PostgreSQL integration test")
	}
	ctx := context.Background()
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		t.Fatalf("pool: %v", err)
	}
	t.Cleanup(pool.Close)
	// disposable test DB: start from a clean schema so tests never inherit each other's state.
	// Migration 0004 creates pf_app (not idempotent across a schema reset), so drop it too.
	_, _ = pool.Exec(ctx, `DROP OWNED BY pf_app`)
	_, _ = pool.Exec(ctx, `DROP ROLE IF EXISTS pf_app`)
	if _, err := pool.Exec(ctx, `DROP SCHEMA public CASCADE`); err != nil {
		t.Fatalf("reset schema: %v", err)
	}
	if _, err := pool.Exec(ctx, `CREATE SCHEMA public`); err != nil {
		t.Fatalf("create schema: %v", err)
	}
	pg, err := store.Open(ctx, dsn)
	if err != nil {
		t.Fatalf("open: %v", err)
	}
	t.Cleanup(pg.Close)
	migs, err := migrate.LoadDir(filepath.Join("..", "..", "migrations"))
	if err != nil {
		t.Fatalf("load migrations: %v", err)
	}
	if _, err := migrate.Up(ctx, pg, migs); err != nil {
		t.Fatalf("migrate: %v", err)
	}
	return pool
}

// TestAuditRLSIntegration proves tenant isolation at the parent AND that the app role cannot write a leaf
// directly (privilege-enforced hardening), covering two Gate-1.5 findings.
func TestAuditRLSIntegration(t *testing.T) {
	ctx := context.Background()
	pool := setup(t)

	tenant := fmt.Sprintf("rls-a-%d", time.Now().UnixNano())
	other := tenant + "-b"
	for _, tn := range []string{tenant, other} {
		if _, err := pool.Exec(ctx, `INSERT INTO audit (tenant_id, actor, action, at) VALUES ($1,'a','rls',now())`, tn); err != nil {
			t.Fatalf("seed %s: %v", tn, err)
		}
	}

	// same-tenant read through RLS
	run := func(fn func(tx pgx.Tx) error) error {
		tx, err := pool.Begin(ctx)
		if err != nil {
			return err
		}
		defer tx.Rollback(ctx)
		if _, err := tx.Exec(ctx, `SET LOCAL ROLE pf_app`); err != nil {
			return err
		}
		if _, err := tx.Exec(ctx, `SELECT set_config('app.tenant_id', $1, true)`, tenant); err != nil {
			return err
		}
		if err := fn(tx); err != nil {
			return err
		}
		return tx.Commit(ctx)
	}
	var see int64
	if err := run(func(tx pgx.Tx) error {
		return tx.QueryRow(ctx, `SELECT count(*) FROM audit WHERE tenant_id LIKE 'rls-%'`).Scan(&see)
	}); err != nil {
		t.Fatalf("tenant select: %v", err)
	}
	if see != 1 {
		t.Fatalf("tenant saw %d rows, want 1 (RLS leak or over-filter)", see)
	}
	if err := run(func(tx pgx.Tx) error {
		_, err := tx.Exec(ctx, `UPDATE audit SET action='tampered' WHERE tenant_id = $1`, tenant)
		return err
	}); err == nil {
		t.Fatal("app role UPDATE must be denied (append-only)")
	}
	if err := run(func(tx pgx.Tx) error {
		_, err := tx.Exec(ctx, `INSERT INTO audit (tenant_id, actor, action, at) VALUES ($1,'a','b',now())`, tenant)
		return err
	}); err != nil {
		t.Fatalf("app role INSERT on parent must be allowed: %v", err)
	}
	if err := run(func(tx pgx.Tx) error {
		_, err := tx.Exec(ctx, `INSERT INTO public.audit_202601 (tenant_id, actor, action, at)
			VALUES ($1,'a','leaf',now())`, tenant)
		return err
	}); err == nil {
		t.Fatal("direct INSERT into a leaf must be denied (no leaf grants)")
	}
}

// TestUnhardenedLeafDetected proves audit_assert_hardened catches a privileged raw ATTACH.
func TestUnhardenedLeafDetected(t *testing.T) {
	ctx := context.Background()
	pool := setup(t)

	// a unique future month, so re-runs never reuse an already-hardened leaf
	y := 2100 + int(time.Now().UnixNano()%200)
	m := time.Month(int(time.Now().UnixNano()%12) + 1)
	from := time.Date(y, m, 1, 0, 0, 0, 0, time.UTC)
	to := from.AddDate(0, 1, 0)
	leaf := "audit_" + from.Format("200601")
	var parent string
	if err := pool.QueryRow(ctx, `SELECT audit_parent()::text`).Scan(&parent); err != nil || parent == "" {
		t.Fatalf("audit_parent: %v (%q)", err, parent)
	}
	if _, err := pool.Exec(ctx, fmt.Sprintf(
		`CREATE TABLE IF NOT EXISTS public.%s PARTITION OF %s FOR VALUES FROM ('%s') TO ('%s')`,
		leaf, parent, from.Format("2006-01-02 15:04:05+00"), to.Format("2006-01-02 15:04:05+00"))); err != nil {
		t.Skipf("cannot create a raw partition (needs owner): %v", err)
	}
	if _, err := pool.Exec(ctx, `SELECT audit_assert_hardened()`); err == nil {
		t.Fatalf("unhardened leaf %s was not detected", leaf)
	}
	if _, err := pool.Exec(ctx, `SELECT audit_harden_partition($1)`, leaf); err != nil {
		t.Fatalf("harden: %v", err)
	}
	if _, err := pool.Exec(ctx, `SELECT audit_assert_hardened()`); err != nil {
		t.Fatalf("assert after harden: %v", err)
	}
}
