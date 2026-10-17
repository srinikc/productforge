package edpdata

import (
	"context"
	"os"
	"testing"
	"time"

	"productforge/datastore"
	"productforge/store"
)

func TestOutbox_Integration(t *testing.T) {
	dsn := os.Getenv("PF_RUNTIME_DSN")
	if dsn == "" {
		t.Skip("set PF_RUNTIME_DSN (non-superuser role, migrations applied) to run the outbox test")
	}
	ctx := context.Background()
	st, err := store.Open(ctx, dsn)
	if err != nil {
		t.Fatal(err)
	}
	defer st.Close()

	tenant := "t-ob-" + time.Now().Format("150405.000000000")
	bind := store.BindTenant(st, tenant)
	if err := bind.WithTx(ctx, func(tx datastore.Tx) error {
		_, e := tx.Exec(ctx, `INSERT INTO tenants (id, slug, name, region, status) VALUES ($1,$1,$1,'','active')`, tenant)
		return e
	}); err != nil {
		t.Fatal(err)
	}
	defer bind.WithTx(ctx, func(tx datastore.Tx) error {
		_, _ = tx.Exec(ctx, `DELETE FROM outbox WHERE tenant_id=$1`, tenant)
		_, _ = tx.Exec(ctx, `DELETE FROM tenants WHERE id=$1`, tenant)
		return nil
	})

	ob := NewOutbox(bind)
	if err := ob.Append(ctx, datastore.Event{ID: "e1-" + tenant, TenantID: tenant, Type: "t", Payload: []byte("a"), At: time.Now()}); err != nil {
		t.Fatal(err)
	}
	if err := ob.Append(ctx, datastore.Event{ID: "e2-" + tenant, TenantID: tenant, Type: "t", Payload: []byte("b"), At: time.Now()}); err != nil {
		t.Fatal(err)
	}
	evs, err := ob.ClaimBatch(ctx, 10)
	if err != nil || len(evs) != 2 {
		t.Fatalf("claim: n=%d err=%v", len(evs), err)
	}
	if err := ob.MarkDelivered(ctx, evs[0].ID); err != nil {
		t.Fatal(err)
	}
	if err := ob.MarkFailed(ctx, evs[1].ID, "boom"); err != nil {
		t.Fatal(err)
	}
	statuses := map[string]string{}
	if err := bind.WithTx(ctx, func(tx datastore.Tx) error {
		rows, err := tx.Query(ctx, `SELECT id, status FROM outbox WHERE tenant_id=$1`, tenant)
		if err != nil {
			return err
		}
		defer rows.Close()
		for rows.Next() {
			var id, stt string
			if err := rows.Scan(&id, &stt); err != nil {
				return err
			}
			statuses[id] = stt
		}
		return rows.Err()
	}); err != nil {
		t.Fatal(err)
	}
	if statuses[evs[0].ID] != "delivered" || statuses[evs[1].ID] != "failed" {
		t.Fatalf("statuses = %v", statuses)
	}
}
