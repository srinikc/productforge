package edpdata

import (
	"context"
	"fmt"
	"os"
	"testing"
	"time"

	"productforge/datastore"
)

func TestEventStorePostgresIntegration(t *testing.T) {
	if os.Getenv("PF_DB_DSN") == "" {
		t.Skip("PF_DB_DSN not set - skipping PostgreSQL event-store integration test")
	}
	ctx := context.Background()
	st, closeFn, err := OpenEventStoreFromEnv(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer closeFn()
	tenant := fmt.Sprintf("evt-test-%d", time.Now().UnixNano())
	ev, err := st.Append(ctx, Event{TenantID: tenant, EventID: tenant + "-e1", Type: "run_started"}, true)
	if err != nil {
		t.Fatal(err)
	}
	if ev.Seq != 1 {
		t.Fatalf("seq=%d want 1", ev.Seq)
	}
	var super, bypass bool
	if err := st.db.WithTx(ctx, func(tx datastore.Tx) error {
		rows, err := tx.Query(ctx, `SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user`)
		if err != nil {
			return err
		}
		defer rows.Close()
		if !rows.Next() {
			return nil
		}
		return rows.Scan(&super, &bypass)
	}); err != nil {
		t.Fatal(err)
	}
	if super || bypass {
		t.Fatal("runtime role must be NOSUPERUSER/NOBYPASSRLS")
	}
	rows, maxSeq, err := st.Read(ctx, tenant, 0, 10)
	if err != nil {
		t.Fatal(err)
	}
	if len(rows) != 1 || maxSeq != 1 {
		t.Fatalf("rows=%d max=%d", len(rows), maxSeq)
	}
}
