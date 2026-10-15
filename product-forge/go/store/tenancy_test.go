package store

import (
	"context"
	"errors"
	"fmt"
	"os"
	"testing"
	"time"

	"productforge/datastore"
)

func TestWithTenantRequiresTenantID(t *testing.T) {
	err := WithTenant(context.Background(), nil, "", func(datastore.Tx) error { return nil })
	if !errors.Is(err, ErrNoTenant) {
		t.Fatalf("want ErrNoTenant, got %v", err)
	}
}

func TestVerifyMembershipRequiresArgs(t *testing.T) {
	if _, _, err := VerifyMembership(context.Background(), nil, "", "p"); !errors.Is(err, ErrNoTenant) {
		t.Fatalf("want ErrNoTenant, got %v", err)
	}
	if _, _, err := VerifyMembership(context.Background(), nil, "t", ""); !errors.Is(err, ErrNoTenant) {
		t.Fatalf("want ErrNoTenant, got %v", err)
	}
}

// TestTenantRLS_Integration proves isolation: with RLS applied, a context set to tenant B cannot see
// tenant A's rows, and no context sees nothing. Requires PF_DB_DSN pointing at a DB with migrations
// 0001–0003 applied (skipped otherwise). Runs on a non-owner role in production; the owner is FORCE-RLS
// here so it also holds.
func TestTenantRLS_Integration(t *testing.T) {
	dsn := os.Getenv("PF_RUNTIME_DSN")
	if dsn == "" {
		t.Skip("set PF_RUNTIME_DSN (non-superuser runtime role, migrations applied) to run the tenant-RLS integration test")
	}
	ctx := context.Background()
	st, err := Open(ctx, dsn)
	if err != nil {
		t.Fatal(err)
	}
	defer st.Close()

	suffix := fmt.Sprint(time.Now().UnixNano())
	a, b := "tA-"+suffix, "tB-"+suffix
	seed := func(tenantID, projectID string) error {
		return WithTenant(ctx, st, tenantID, func(tx datastore.Tx) error {
			if _, err := tx.Exec(ctx,
				`INSERT INTO tenants (id, slug, name, region, status) VALUES ($1,$1,$1,'', 'active')`, tenantID); err != nil {
				return err
			}
			_, err := tx.Exec(ctx,
				`INSERT INTO projects (id, tenant_id, slug, name, status) VALUES ($1,$2,$1,$1,'active')`,
				projectID, tenantID)
			return err
		})
	}
	if err := seed(a, "pA-"+suffix); err != nil {
		t.Fatalf("seed A: %v", err)
	}
	defer WithTenant(ctx, st, a, func(tx datastore.Tx) error {
		_, _ = tx.Exec(ctx, `DELETE FROM projects WHERE tenant_id=$1`, a)
		_, _ = tx.Exec(ctx, `DELETE FROM tenants WHERE id=$1`, a)
		return nil
	})

	count := func(tenantID string) int {
		n := -1
		_ = WithTenant(ctx, st, tenantID, func(tx datastore.Tx) error {
			rows, err := tx.Query(ctx, `SELECT count(*) FROM projects`)
			if err != nil {
				return err
			}
			defer rows.Close()
			if rows.Next() {
				_ = rows.Scan(&n)
			}
			return rows.Err()
		})
		return n
	}

	if got := count(a); got != 1 {
		t.Fatalf("tenant A should see 1 project, saw %d (RLS not enforced?)", got)
	}
	if got := count(b); got != 0 {
		t.Fatalf("tenant B must see 0 of A's projects, saw %d (RLS leak!)", got)
	}
}
