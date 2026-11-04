package edpdata

import (
	"context"
	"errors"
	"fmt"
	"math"
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
		_, _ = tx.Exec(ctx, `DELETE FROM memory WHERE tenant_id=$1`, tenant)
		_, _ = tx.Exec(ctx, `DELETE FROM backlog_items WHERE tenant_id=$1`, tenant)
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

	// Memory lifecycle + scoped search.
	mem := NewMemory(bind)
	if _, err := mem.Put(ctx, datastore.MemoryEntry{ID: "mem-" + tenant, TenantID: tenant,
		Kind: "semantic", ACLScope: "shared", Source: "team"}); err != nil {
		t.Fatal(err)
	}
	hits, err := mem.Search(ctx, "", datastore.MemoryScope{TenantID: tenant, Source: "team"}, 10)
	if err != nil || len(hits) != 1 {
		t.Fatalf("memory search: hits=%d err=%v", len(hits), err)
	}
	none, err := mem.Search(ctx, "", datastore.MemoryScope{TenantID: tenant, Source: "other"}, 10)
	if err != nil || len(none) != 0 {
		t.Fatalf("memory scope filter leaked: hits=%d err=%v", len(none), err)
	}
	if err := mem.Delete(ctx, "mem-"+tenant); err != nil {
		t.Fatal(err)
	}

	// Backlog item lifecycle + revision bump + direct scope/project scoping (BI-PF-1421).
	bl := NewBacklog(bind)
	bi := "BL-" + tenant
	if _, err := bl.Put(ctx, BacklogItem{ID: bi, TenantID: tenant, Type: "feature", Title: "first"}); err != nil {
		t.Fatal(err)
	}
	if _, err := bl.Put(ctx, BacklogItem{ID: bi, TenantID: tenant, Type: "feature", Title: "second",
		Scope: "project", ProjectID: "demo-app"}); err != nil {
		t.Fatal(err)
	}
	gotBL, err := bl.Get(ctx, bi)
	if err != nil || gotBL.Title != "second" || gotBL.Revision < 1 {
		t.Fatalf("backlog put/get: %+v err=%v", gotBL, err)
	}
	if gotBL.Scope != "project" || gotBL.ProjectID != "demo-app" {
		t.Fatalf("scope/project not directly scoped: %+v", gotBL)
	}
	if items, err := bl.List(ctx, "", 10); err != nil || len(items) == 0 {
		t.Fatalf("backlog list: n=%d err=%v", len(items), err)
	}
	if err := bl.Delete(ctx, bi); err != nil {
		t.Fatal(err)
	}

	// DB-owned ID authority: idempotent reservation + disjoint ranges.
	// Never rewind the shared global counter: consumed ids stay consumed.
	resID := "res-" + tenant
	b1, err := bl.Reserve(ctx, "project", tenant, resID, 3)
	if err != nil || b1.End-b1.Start+1 != 3 {
		t.Fatalf("reserve block: %+v err=%v", b1, err)
	}
	b1Again, err := bl.Reserve(ctx, "project", tenant, resID, 3)
	if err != nil || b1Again != b1 {
		t.Fatalf("reserve idempotency: first=%+v again=%+v err=%v", b1, b1Again, err)
	}
	b2, err := bl.Reserve(ctx, "project", tenant, "res2-"+tenant, 2)
	if err != nil || b2.Start <= b1.End {
		t.Fatalf("reserve disjoint: first=%+v second=%+v err=%v", b1, b2, err)
	}
	if err := bind.WithTx(ctx, func(tx datastore.Tx) error {
		_, e := tx.Exec(ctx, `DELETE FROM backlog_id_reservations WHERE reservation_id IN ($1,$2)`, resID, "res2-"+tenant)
		return e
	}); err != nil {
		t.Fatal(err)
	}
}

func TestBacklogReservationCounter(t *testing.T) {
	dsn := os.Getenv("PF_RUNTIME_DSN")
	if dsn == "" {
		t.Skip("set PF_RUNTIME_DSN to run the reservation counter test")
	}
	ctx := context.Background()
	st, err := store.Open(ctx, dsn)
	if err != nil {
		t.Fatal(err)
	}
	defer st.Close()
	tenant := "authority-counter-" + time.Now().Format("150405.000000000")
	bind := store.BindTenant(st, tenant)
	bl := NewBacklog(bind)
	readCounter := func() int64 {
		t.Helper()
		var n int64
		if err := bind.WithTx(ctx, func(tx datastore.Tx) error {
			rows, err := tx.Query(ctx, `SELECT reservation_count FROM backlog_id_allocations WHERE authority='global'`)
			if err != nil {
				return err
			}
			defer rows.Close()
			if !rows.Next() {
				return ErrAuthorityRow
			}
			return rows.Scan(&n)
		}); err != nil {
			t.Fatal(err)
		}
		return n
	}
	before := readCounter()
	// Never rewind next_id here: the authority is shared and reservations consume ids.
	res1, res2 := "counter-1-"+tenant, "counter-2-"+tenant
	_, err = bl.Reserve(ctx, "project", tenant, res1, 2)
	if err != nil {
		t.Fatal(err)
	}
	if got := readCounter(); got != before+1 {
		t.Fatalf("counter after first reservation = %d, want %d", got, before+1)
	}
	if _, err := bl.Reserve(ctx, "project", tenant, res1, 2); err != nil {
		t.Fatal(err)
	}
	if got := readCounter(); got != before+1 {
		t.Fatalf("idempotent retry changed counter to %d, want %d", got, before+1)
	}
	_, err = bl.Reserve(ctx, "project", tenant, res2, 1)
	if err != nil {
		t.Fatal(err)
	}
	if got := readCounter(); got != before+2 {
		t.Fatalf("counter after second reservation = %d, want %d", got, before+2)
	}
	if err := bind.WithTx(ctx, func(tx datastore.Tx) error {
		_, err := tx.Exec(ctx, `DELETE FROM backlog_id_reservations WHERE reservation_id IN ($1,$2)`, res1, res2)
		return err
	}); err != nil {
		t.Fatal(err)
	}
	if got := readCounter(); got != before {
		t.Fatalf("counter after delete = %d, want %d", got, before)
	}
}

type fakeRows struct {
	data [][]any
	pos  int
}

func (r *fakeRows) Next() bool {
	if r.pos >= len(r.data) {
		return false
	}
	r.pos++
	return true
}

func (r *fakeRows) Scan(dest ...any) error {
	row := r.data[r.pos-1]
	for i, d := range dest {
		switch p := d.(type) {
		case *string:
			*p = row[i].(string)
		case *bool:
			*p = row[i].(bool)
		case *int64:
			*p = row[i].(int64)
		default:
			return errors.New("fakeRows: unsupported scan target")
		}
	}
	return nil
}

func (r *fakeRows) Err() error   { return nil }
func (r *fakeRows) Close() error { return nil }

type fakeTx struct{ store *fakeStore }
type fakeStore struct {
	queries [][][]any
	execs   [][]any
}

func (f *fakeStore) Ping(context.Context) error           { return nil }
func (f *fakeStore) Capabilities() datastore.Capabilities { return datastore.Capabilities{} }
func (f *fakeStore) WithTx(_ context.Context, fn func(datastore.Tx) error) error {
	return fn(&fakeTx{store: f})
}
func (f *fakeStore) Exec(context.Context, string, ...any) (int64, error) { return 1, nil }
func (t *fakeTx) Exec(_ context.Context, _ string, args ...any) (int64, error) {
	t.store.execs = append(t.store.execs, args)
	return 1, nil
}
func (t *fakeTx) Query(ctx context.Context, sql string, args ...any) (datastore.Rows, error) {
	return t.store.Query(ctx, sql, args...)
}
func (t *fakeTx) Commit(context.Context) error   { return nil }
func (t *fakeTx) Rollback(context.Context) error { return nil }
func (f *fakeStore) Query(context.Context, string, ...any) (datastore.Rows, error) {
	if len(f.queries) == 0 {
		return &fakeRows{}, nil
	}
	rows := f.queries[0]
	f.queries = f.queries[1:]
	return &fakeRows{data: rows}, nil
}

func TestAuthorityTimeoutComesFromConfig(t *testing.T) {
	f := &fakeStore{}
	_, _ = NewBacklog(f).WithTimeout(2345 * time.Millisecond).Authority(context.Background())
	if len(f.execs) == 0 || len(f.execs[0]) == 0 || fmt.Sprint(f.execs[0][0]) != "2345ms" {
		t.Fatalf("statement timeout not applied from config: %#v", f.execs)
	}
}

func TestAuthorityIDSpaceExhaustionFailsClosed(t *testing.T) {
	f := &fakeStore{queries: [][][]any{{{int64(math.MaxInt64)}}}}
	_, err := NewBacklog(f).Reserve(context.Background(), "product_forge", "", "res-exhausted", 2)
	if !errors.Is(err, ErrReservationExhausted) {
		t.Fatalf("want ErrReservationExhausted, got %v", err)
	}
}

func TestBacklogAuthorityMissingRowFailsClosed(t *testing.T) {
	f := &fakeStore{queries: [][][]any{
		{{"alloc", "reservations", "items", true, "tenant", true, true}},
		{},
	}}
	_, err := NewBacklog(f).Authority(context.Background())
	if !errors.Is(err, ErrAuthorityRow) {
		t.Fatalf("want ErrAuthorityRow, got %v", err)
	}
}

func TestBacklogAuthorityMissingRLSPolicyFailsClosed(t *testing.T) {
	f := &fakeStore{queries: [][][]any{
		{{"alloc", "reservations", "items", true, "tenant", false, true}},
	}}
	_, err := NewBacklog(f).Authority(context.Background())
	if !errors.Is(err, ErrAuthoritySchema) {
		t.Fatalf("want ErrAuthoritySchema, got %v", err)
	}
}
func TestBacklogAuthoritySuccessWithoutDB(t *testing.T) {
	f := &fakeStore{queries: [][][]any{
		{{"alloc", "reservations", "items", true, "tenant", true, true}},
		{{int64(100), int64(0)}},
		{{int64(2)}},
	}}
	a, err := NewBacklog(f).Authority(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if a.NextID != 100 || a.ItemCount != 2 {
		t.Fatalf("authority=%+v", a)
	}
}

func TestBacklogAuthorityMissingMigrationsFailsClosed(t *testing.T) {
	f := &fakeStore{queries: [][][]any{
		{{"alloc", "reservations", "items", true, "tenant", true, false}},
	}}
	_, err := NewBacklog(f).Authority(context.Background())
	if !errors.Is(err, ErrAuthoritySchema) {
		t.Fatalf("want ErrAuthoritySchema, got %v", err)
	}
}

func TestBacklogAuthorityZeroNextIDFailsClosed(t *testing.T) {
	f := &fakeStore{queries: [][][]any{
		{{"alloc", "reservations", "items", true, "tenant", true, true}},
		{{int64(0), int64(0)}},
	}}
	_, err := NewBacklog(f).Authority(context.Background())
	if !errors.Is(err, ErrAuthorityRow) {
		t.Fatalf("want ErrAuthorityRow, got %v", err)
	}
}

func TestBacklogAuthorityMissingSchemaFailsClosed(t *testing.T) {
	f := &fakeStore{queries: [][][]any{
		{{"alloc", "reservations", "items", false, "tenant", true, true}},
	}}
	_, err := NewBacklog(f).Authority(context.Background())
	if !errors.Is(err, ErrAuthoritySchema) {
		t.Fatalf("want ErrAuthoritySchema, got %v", err)
	}
}

func TestBacklogPutCrossTenantConflict(t *testing.T) {
	dsn := os.Getenv("PF_RUNTIME_DSN")
	if dsn == "" {
		t.Skip("set PF_RUNTIME_DSN to run the cross-tenant conflict test")
	}
	ctx := context.Background()
	st, err := store.Open(ctx, dsn)
	if err != nil {
		t.Fatal(err)
	}
	defer st.Close()
	tenantA := "authority-a-" + time.Now().Format("150405.000000000")
	tenantB := "authority-b-" + time.Now().Format("150405.000000000")
	id := "BL-cross-" + tenantA
	a := NewBacklog(store.BindTenant(st, tenantA))
	b := NewBacklog(store.BindTenant(st, tenantB))
	if _, err := a.Put(ctx, BacklogItem{ID: id, TenantID: tenantA, Title: "a"}); err != nil {
		t.Fatal(err)
	}
	defer func() { _ = a.Delete(ctx, id) }()
	_, err = b.Put(ctx, BacklogItem{ID: id, TenantID: tenantB, Title: "b"})
	if !errors.Is(err, ErrTenantConflict) {
		t.Fatalf("want ErrTenantConflict, got %v", err)
	}
}
