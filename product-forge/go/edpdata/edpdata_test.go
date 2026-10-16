package edpdata

import (
	"context"
	"os"
	"testing"
	"time"

	"productforge/datastore"
	"productforge/store"
)

func TestAuditAndJobs_Integration(t *testing.T) {
	dsn := os.Getenv("PF_RUNTIME_DSN")
	if dsn == "" {
		t.Skip("set PF_RUNTIME_DSN (non-superuser role, migrations applied) to run the edpdata integration test")
	}
	ctx := context.Background()
	st, err := store.Open(ctx, dsn)
	if err != nil {
		t.Fatal(err)
	}
	defer st.Close()

	tenant := "t-edp-" + time.Now().Format("150405.000000000")
	bind := store.BindTenant(st, tenant)
	if err := bind.WithTx(ctx, func(tx datastore.Tx) error {
		_, e := tx.Exec(ctx, `INSERT INTO tenants (id, slug, name, region, status) VALUES ($1,$1,$1,'','active')`, tenant)
		return e
	}); err != nil {
		t.Fatal(err)
	}
	defer bind.WithTx(ctx, func(tx datastore.Tx) error {
		_, _ = tx.Exec(ctx, `DELETE FROM jobs WHERE tenant_id=$1`, tenant)
		_, _ = tx.Exec(ctx, `DELETE FROM audit WHERE tenant_id=$1`, tenant)
		_, _ = tx.Exec(ctx, `DELETE FROM tenants WHERE id=$1`, tenant)
		return nil
	})

	// Audit is append-only.
	if err := NewAudit(bind).Append(ctx, datastore.AuditEvent{TenantID: tenant, Actor: "t", Action: "probe", At: time.Now()}); err != nil {
		t.Fatal(err)
	}

	// Jobs lifecycle.
	jobs := NewJobs(bind)
	jobID := "job-" + tenant
	if _, err := jobs.Submit(ctx, datastore.Job{ID: jobID, TenantID: tenant, Kind: "unit"}); err != nil {
		t.Fatal(err)
	}
	j, ok, err := jobs.Claim(ctx, "worker-1", time.Minute)
	if err != nil || !ok {
		t.Fatalf("claim: ok=%v err=%v", ok, err)
	}
	if j.ID != jobID || j.LeaseID != "worker-1" {
		t.Fatalf("claimed %+v", j)
	}
	if err := jobs.Complete(ctx, j.ID, j.LeaseID); err != nil {
		t.Fatal(err)
	}
	got, err := jobs.Get(ctx, jobID)
	if err != nil || got.Status != "completed" {
		t.Fatalf("after complete: %+v err=%v", got, err)
	}
}
