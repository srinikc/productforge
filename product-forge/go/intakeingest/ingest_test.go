package intakeingest

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"regexp"
	"strings"
	"testing"
	"time"

	"productforge/datastore"
	"productforge/objstore"
	"productforge/store"
)

func TestArtifactIDStable(t *testing.T) {
	a := ArtifactID("t1", "intake", "conversations.json", "abc")
	if a != ArtifactID("t1", "intake", "conversations.json", "abc") {
		t.Fatal("artifact id is not deterministic")
	}
	for _, other := range []string{
		ArtifactID("t2", "intake", "conversations.json", "abc"),
		ArtifactID("t1", "builds", "conversations.json", "abc"),
		ArtifactID("t1", "intake", "ideas.json", "abc"),
		ArtifactID("t1", "intake", "conversations.json", "abd"),
	} {
		if other == a {
			t.Fatalf("artifact id collides across a different input: %s", other)
		}
	}
	if len(a) != 32 {
		t.Fatalf("want 32 hex chars, got %d", len(a))
	}
}

func TestObjectKeyTenantPrefixed(t *testing.T) {
	got := ObjectKey("t1", "builds", "sum")
	if got != "tenant/t1/builds/sum" {
		t.Fatalf("unexpected key %q", got)
	}
	if !strings.HasPrefix(got, "tenant/t1/") {
		t.Fatal("object key is not tenant-prefixed")
	}
}

func TestIngestRejectsTooLarge(t *testing.T) {
	svc := New(nil, nil, 4)
	res, err := svc.Ingest(context.Background(), "t1", "intake", "big.json",
		strings.NewReader("12345"), "application/json", true)
	if !errors.Is(err, ErrTooLarge) {
		t.Fatalf("want ErrTooLarge, got %v", err)
	}
	if res.Status != Failed {
		t.Fatalf("want failed status, got %s", res.Status)
	}
}

func TestTenantTraversalRejected(t *testing.T) {
	svc := New(nil, nil, 0)
	for _, tenant := range []string{"../escape", "a/b", "..", "a\\b", "a b"} {
		_, err := svc.Ingest(context.Background(), tenant, "intake", "a.json",
			strings.NewReader("x"), "", true)
		if !errors.Is(err, ErrBadTenant) {
			t.Fatalf("tenant %q must be rejected with ErrBadTenant, got %v", tenant, err)
		}
	}
	if _, err := svc.Ingest(context.Background(), "", "intake", "a.json",
		strings.NewReader("x"), "", true); !errors.Is(err, ErrNoTenant) {
		t.Fatalf("empty tenant must be ErrNoTenant, got %v", err)
	}
	if _, err := svc.Ingest(context.Background(), "t1", "intake", "a.json",
		strings.NewReader("x"), "", true); err != nil {
		t.Fatalf("safe tenant must be accepted, got %v", err)
	}
}

func TestDryRunIsPlanned(t *testing.T) {
	svc := New(nil, nil, 0)
	res, err := svc.Ingest(context.Background(), "t1", "intake", "a.json",
		strings.NewReader("x"), "", true)
	if err != nil {
		t.Fatal(err)
	}
	if res.Status != Planned {
		t.Fatalf("dry run must report %q, got %q", Planned, res.Status)
	}
}

func TestEnsureRuntimeRoleRefusesBypass(t *testing.T) {
	dsn := os.Getenv("PF_RUNTIME_DSN")
	if dsn == "" {
		t.Skip("set PF_RUNTIME_DSN to run the role posture test")
	}
	ctx := context.Background()
	st, err := store.Open(ctx, dsn)
	if err != nil {
		t.Fatal(err)
	}
	defer st.Close()
	p, err := RuntimeRole(ctx, st)
	if err != nil {
		t.Fatal(err)
	}
	if p.Superuser || p.BypassRLS {
		t.Fatalf("PF_RUNTIME_DSN role %q bypasses RLS (rolsuper=%v rolbypassrls=%v); the isolation tests would be vacuous",
			p.Name, p.Superuser, p.BypassRLS)
	}
	if _, err := EnsureRuntimeRole(ctx, st, false); err != nil {
		t.Fatalf("a non-bypass role must be accepted: %v", err)
	}
}

func TestReportGolden(t *testing.T) {
	started := time.Date(2026, 10, 24, 0, 0, 0, 0, time.UTC)
	rep := Report{
		Schema: Schema, RunID: "00000000-0000-4000-8000-000000000000", Mode: "ingest",
		Tenant: "t1", StartedAt: started, DurationMS: 12,
		Files: []FileResult{{Store: "intake/a.json", Bucket: "intake", Name: "a.json", Status: Written,
			ArtifactID: "abc", Revision: 0, Checksum: "def", Bytes: 3, DurationMS: 1}},
		Counts: map[string]int{"planned": 0, "written": 1, "skipped-unchanged": 0, "drift": 0, "failed": 0},
	}
	got, err := json.MarshalIndent(rep, "", "  ")
	if err != nil {
		t.Fatal(err)
	}
	want := `{
  "schema": "pf.intake-ingest/1",
  "run_id": "00000000-0000-4000-8000-000000000000",
  "mode": "ingest",
  "tenant": "t1",
  "dry_run": false,
  "started_at": "2026-10-24T00:00:00Z",
  "duration_ms": 12,
  "files": [
    {
      "store": "intake/a.json",
      "bucket": "intake",
      "name": "a.json",
      "status": "written",
      "artifact_id": "abc",
      "revision": 0,
      "checksum": "def",
      "bytes": 3,
      "duration_ms": 1
    }
  ],
  "counts": {
    "drift": 0,
    "failed": 0,
    "planned": 0,
    "skipped-unchanged": 0,
    "written": 1
  }
}`
	if string(got) != want {
		t.Fatalf("report schema drifted:\n%s", got)
	}
}

func TestNewRunIDIsUUIDv4(t *testing.T) {
	re := regexp.MustCompile(`^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$`)
	id, err := NewRunID()
	if err != nil {
		t.Fatal(err)
	}
	if !re.MatchString(id) {
		t.Fatalf("run id is not UUIDv4: %q", id)
	}
}

func TestServiceIntegration(t *testing.T) {
	dsn := os.Getenv("PF_RUNTIME_DSN")
	if dsn == "" {
		t.Skip("set PF_RUNTIME_DSN (non-BYPASSRLS role, migrations applied) to run the ingestion integration test")
	}
	ctx := context.Background()
	st, err := store.Open(ctx, dsn)
	if err != nil {
		t.Fatal(err)
	}
	defer st.Close()
	if _, err := EnsureRuntimeRole(ctx, st, false); err != nil {
		t.Fatalf("runtime role must not bypass RLS: %v", err)
	}
	obj, err := objstore.NewLocalStore(t.TempDir(), 0)
	if err != nil {
		t.Fatal(err)
	}
	stamp := fmt.Sprintf("%d", time.Now().UnixNano())
	tenantA := "t-ing-a-" + stamp
	tenantB := "t-ing-b-" + stamp

	createTenant(t, st, tenantA)
	createTenant(t, st, tenantB)
	defer cleanupTenant(t, st, tenantA)
	defer cleanupTenant(t, st, tenantB)

	svcA := New(store.BindTenant(st, tenantA), obj, 0)
	svcB := New(store.BindTenant(st, tenantB), obj, 0)
	name := "conversations.json"
	original := []byte("conversation payload v1")
	changed := []byte("conversation payload v2")

	r1, err := svcA.Ingest(ctx, tenantA, "intake", name, bytes.NewReader(original), "application/json", false)
	if err != nil || r1.Status != Written || r1.Revision != 0 {
		t.Fatalf("first ingest: %+v err=%v", r1, err)
	}
	r2, err := svcA.Ingest(ctx, tenantA, "intake", name, bytes.NewReader(original), "application/json", false)
	if err != nil || r2.Status != SkippedUnchanged || r2.ArtifactID != r1.ArtifactID {
		t.Fatalf("unchanged re-ingest: %+v err=%v", r2, err)
	}
	if n := countArtifacts(t, st, tenantA, "intake/"+name); n != 1 {
		t.Fatalf("unchanged re-ingest must not add a row, got %d", n)
	}

	r3, err := svcA.Ingest(ctx, tenantA, "intake", name, bytes.NewReader(changed), "application/json", false)
	if err != nil || r3.Status != Written || r3.ArtifactID == r1.ArtifactID || r3.Revision != 1 {
		t.Fatalf("changed ingest: %+v err=%v", r3, err)
	}
	// Reverting to the old payload is a no-op on the existing immutable row/revision.
	r4, err := svcA.Ingest(ctx, tenantA, "intake", name, bytes.NewReader(original), "application/json", false)
	if err != nil || r4.Status != SkippedUnchanged || r4.ArtifactID != r1.ArtifactID || r4.Revision != 0 {
		t.Fatalf("revert ingest: %+v err=%v", r4, err)
	}
	if n := countArtifacts(t, st, tenantA, "intake/"+name); n != 2 {
		t.Fatalf("want 2 revisions after changed payload, got %d", n)
	}

	// Verify the current latest (changed) passes; the stale source drifts.
	v, err := svcA.Verify(ctx, tenantA, "intake", name, bytes.NewReader(changed))
	if err != nil || v.Status != SkippedUnchanged {
		t.Fatalf("verify current: %+v err=%v", v, err)
	}
	v, err = svcA.Verify(ctx, tenantA, "intake", name, bytes.NewReader(original))
	if err != nil || v.Status != Drift {
		t.Fatalf("verify stale source must drift: %+v err=%v", v, err)
	}

	// Tenant B cannot see tenant A's metadata (RLS), even with the same content.
	v, err = svcB.Verify(ctx, tenantB, "intake", name, bytes.NewReader(changed))
	if err == nil || v.Status != Failed {
		t.Fatalf("cross-tenant verify must fail closed: %+v err=%v", v, err)
	}
	if strings.Contains(err.Error(), "object-store") {
		t.Fatalf("cross-tenant access must not reach the object layer: %v", err)
	}

	// A missing object makes verify fail (never a silent pass).
	if err := obj.Delete(ctx, ObjectKey(tenantA, "intake", r3.Checksum), ""); err != nil {
		t.Fatal(err)
	}
	v, err = svcA.Verify(ctx, tenantA, "intake", name, bytes.NewReader(changed))
	if err == nil || v.Status != Failed {
		t.Fatalf("verify with a missing object must fail: %+v err=%v", v, err)
	}
}

func createTenant(t *testing.T, st datastore.RelationalStore, tenant string) {
	t.Helper()
	bind := store.BindTenant(st, tenant)
	if err := bind.WithTx(context.Background(), func(tx datastore.Tx) error {
		_, err := tx.Exec(context.Background(),
			`INSERT INTO tenants (id, slug, name, region, status) VALUES ($1,$1,$1,'','active')`, tenant)
		return err
	}); err != nil {
		t.Fatal(err)
	}
}

func cleanupTenant(t *testing.T, st datastore.RelationalStore, tenant string) {
	t.Helper()
	bind := store.BindTenant(st, tenant)
	_ = bind.WithTx(context.Background(), func(tx datastore.Tx) error {
		_, _ = tx.Exec(context.Background(), `DELETE FROM artifacts WHERE tenant_id=$1`, tenant)
		_, _ = tx.Exec(context.Background(), `DELETE FROM stored_objects WHERE tenant_id=$1`, tenant)
		_, _ = tx.Exec(context.Background(), `DELETE FROM tenants WHERE id=$1`, tenant)
		return nil
	})
}

func countArtifacts(t *testing.T, st datastore.RelationalStore, tenant, name string) int {
	t.Helper()
	n := 0
	bind := store.BindTenant(st, tenant)
	if err := bind.WithTx(context.Background(), func(tx datastore.Tx) error {
		rows, err := tx.Query(context.Background(),
			`SELECT count(*) FROM artifacts WHERE tenant_id=$1 AND name=$2`, tenant, name)
		if err != nil {
			return err
		}
		defer rows.Close()
		if rows.Next() {
			return rows.Scan(&n)
		}
		return rows.Err()
	}); err != nil {
		t.Fatal(err)
	}
	return n
}
