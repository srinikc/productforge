package artifacts

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"io"
	"os"
	"testing"
	"time"

	"productforge/datastore"
	"productforge/objstore"
	"productforge/store"
)

func TestArtifactService_Integration(t *testing.T) {
	dsn := os.Getenv("PF_RUNTIME_DSN")
	if dsn == "" {
		t.Skip("set PF_RUNTIME_DSN (non-superuser role, migrations applied) to run the artifacts integration test")
	}
	ctx := context.Background()
	st, err := store.Open(ctx, dsn)
	if err != nil {
		t.Fatal(err)
	}
	defer st.Close()
	obj, err := objstore.NewLocalStore(t.TempDir(), 0)
	if err != nil {
		t.Fatal(err)
	}

	tenant := "t-art-" + time.Now().Format("150405.000000000")
	bind := store.BindTenant(st, tenant)
	svc := New(bind, obj)

	if err := bind.WithTx(ctx, func(tx datastore.Tx) error {
		_, e := tx.Exec(ctx, `INSERT INTO tenants (id, slug, name, region, status) VALUES ($1,$1,$1,'','active')`, tenant)
		return e
	}); err != nil {
		t.Fatal(err)
	}
	defer bind.WithTx(ctx, func(tx datastore.Tx) error {
		_, _ = tx.Exec(ctx, `DELETE FROM artifacts WHERE tenant_id=$1`, tenant)
		_, _ = tx.Exec(ctx, `DELETE FROM stored_objects WHERE tenant_id=$1`, tenant)
		_, _ = tx.Exec(ctx, `DELETE FROM tenants WHERE id=$1`, tenant)
		return nil
	})

	body := []byte("artifact payload v1")
	sum := sha256.Sum256(body)
	checksum := hex.EncodeToString(sum[:])
	info, err := obj.Put(ctx, checksum, bytes.NewReader(body), int64(len(body)),
		datastore.PutOptions{ContentType: "text/plain"})
	if err != nil {
		t.Fatal(err)
	}

	registered, err := svc.Register(ctx, datastore.Artifact{ID: "art-" + tenant, TenantID: tenant,
		Type: "text/plain", Checksum: info.Checksum, Size: int64(len(body)), Version: info.Version})
	if err != nil {
		t.Fatal(err)
	}
	if registered.ID == "" || registered.Checksum != info.Checksum || registered.Size != int64(len(body)) {
		t.Fatalf("register returned %+v", registered)
	}

	rc, err := svc.FetchContent(ctx, registered.ID)
	if err != nil {
		t.Fatal(err)
	}
	got, _ := io.ReadAll(rc)
	_ = rc.Close()
	if !bytes.Equal(got, body) {
		t.Fatalf("content mismatch")
	}
	if ok, err := svc.Verify(ctx, registered.ID); err != nil || !ok {
		t.Fatalf("verify: ok=%v err=%v", ok, err)
	}

	if err := svc.Delete(ctx, registered.ID); err != nil {
		t.Fatal(err)
	}
	if _, err := svc.Get(ctx, registered.ID); err != ErrNotFound {
		t.Fatalf("after delete want ErrNotFound, got %v", err)
	}
}
