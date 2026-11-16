package edpdata

import (
	"context"
	"testing"
	"time"
)

type fakePayloadStore struct {
	refs    []string
	deleted []string
}

func (f *fakePayloadStore) List(context.Context) ([]string, error) { return f.refs, nil }
func (f *fakePayloadStore) Delete(_ context.Context, ref string) error {
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
	ps := &fakePayloadStore{refs: []string{"ref-live", "ref-orphan"}}
	n, err := st.ReconcilePayloads(context.Background(), "t1", ps)
	if err != nil {
		t.Fatal(err)
	}
	if n != 1 || len(ps.deleted) != 1 || ps.deleted[0] != "ref-orphan" {
		t.Fatalf("deleted=%v n=%d", ps.deleted, n)
	}
}
