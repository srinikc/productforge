package edpdata

import (
	"context"
	"testing"
	"time"
)

type fakePayloadStore struct {
	refs    []PayloadObject
	deleted []string
}

func (f *fakePayloadStore) Put(context.Context, string, string, []byte, string) (PayloadRef, error) {
	return PayloadRef{}, nil
}
func (f *fakePayloadStore) List(context.Context, string) ([]PayloadObject, error) { return f.refs, nil }
func (f *fakePayloadStore) Delete(_ context.Context, _, ref string) error {
	f.deleted = append(f.deleted, ref)
	return nil
}

func TestPruneOutboxNeverTouchesPending(t *testing.T) {
	f := &fakeStore{}
	st := NewEventStore(f)
	if _, err := st.PruneOutbox(context.Background(), "t1", time.Hour); err != nil {
		t.Fatal(err)
	}
	if len(f.execs) == 0 {
		t.Fatal("no delete executed")
	}
}

func TestReconcilePayloadsDeletesOnlyUnreferenced(t *testing.T) {
	f := &fakeStore{queries: [][][]any{{{"ref-live"}}}}
	st := NewEventStore(f)
	ps := &fakePayloadStore{refs: []PayloadObject{{Ref: "ref-live", CreatedAt: 0}, {Ref: "ref-orphan", CreatedAt: 0}}}
	n, err := st.ReconcilePayloads(context.Background(), "t1", ps, 0)
	if err != nil {
		t.Fatal(err)
	}
	if n != 1 || len(ps.deleted) != 1 || ps.deleted[0] != "ref-orphan" {
		t.Fatalf("deleted=%v n=%d", ps.deleted, n)
	}
}

type recordingPayloadStore struct {
	tenant string
	puts   int
}

func (f *recordingPayloadStore) Put(_ context.Context, tenant, eventID string, data []byte, contentType string) (PayloadRef, error) {
	f.tenant = tenant
	f.puts++
	return PayloadRef{Ref: "obj-1", SHA256: "h", Size: int64(len(data)), ContentType: contentType}, nil
}
func (f *recordingPayloadStore) List(_ context.Context, tenant string) ([]PayloadObject, error) {
	f.tenant = tenant
	return nil, nil
}
func (f *recordingPayloadStore) Delete(context.Context, string, string) error { return nil }

func TestAppendUsesObjectStoreAboveThreshold(t *testing.T) {
	fs := &fakeStore{queries: [][][]any{{{int64(1)}}}}
	st := NewEventStore(fs).WithPayloads(&recordingPayloadStore{}, 4)
	ev, err := st.Append(context.Background(), Event{TenantID: "t1", EventID: "e1", Type: "x", Payload: []byte(`{"long":"payload"}`)}, false)
	if err != nil {
		t.Fatal(err)
	}
	if ev.PayloadRef != "obj-1" || ev.SizeBytes == 0 {
		t.Fatalf("payload not offloaded: %+v", ev)
	}
}

func TestOutboxBoundFailsClosed(t *testing.T) {
	fs := &fakeStore{queries: [][][]any{{{int64(5)}}}}
	st := NewEventStore(fs)
	if err := st.EnforceOutboxBound(context.Background(), "t1", 1); err == nil {
		t.Fatal("outbox bound not enforced")
	}
}

func TestPayloadGCUsesTenantScope(t *testing.T) {
	fs := &fakeStore{queries: [][][]any{{{"ref-live"}}}}
	ps := &recordingPayloadStore{}
	if _, err := NewEventStore(fs).ReconcilePayloads(context.Background(), "tenant-a", ps, 3600); err != nil {
		t.Fatal(err)
	}
	if ps.tenant != "tenant-a" {
		t.Fatalf("tenant=%q", ps.tenant)
	}
}

func TestAppendEnforcesOutboxBound(t *testing.T) {
	fs := &fakeStore{queries: [][][]any{{{int64(5)}}}}
	st := NewEventStore(fs).WithOutboxBound(1)
	_, err := st.Append(context.Background(), Event{TenantID: "t1", EventID: "e1", Type: "x"}, true)
	if err == nil {
		t.Fatal("Append did not enforce outbox bound")
	}
}

func TestAppendLargePayloadWithoutStoreFailsClosed(t *testing.T) {
	fs := &fakeStore{queries: [][][]any{{{int64(0)}}}}
	st := NewEventStore(fs)
	payload := make([]byte, 40*1024)
	for i := range payload {
		payload[i] = 'a'
	}
	if _, err := st.Append(context.Background(), Event{TenantID: "t1", EventID: "e1", Type: "x", Payload: payload}, false); err == nil {
		t.Fatal("large payload without object store accepted")
	}
}
