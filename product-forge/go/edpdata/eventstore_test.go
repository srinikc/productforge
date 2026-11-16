package edpdata

import (
	"context"
	"testing"
)

func TestEventStoreAppendAssignsSeqAndOutbox(t *testing.T) {
	f := &fakeStore{queries: [][][]any{{{int64(0)}}, {{int64(7)}}}}
	st := NewEventStore(f)
	ev, err := st.Append(context.Background(), Event{
		TenantID: "t1", EventID: "e1", Type: "run_started",
		Payload: []byte(`{"k":"v"}`),
	}, true)
	if err != nil {
		t.Fatal(err)
	}
	if ev.Seq != 7 {
		t.Fatalf("seq=%d want 7", ev.Seq)
	}
	if len(f.execs) < 4 {
		t.Fatalf("execs=%d want >=4 (tenant, timeout, event, outbox)", len(f.execs))
	}
}

func TestEventStoreAppendRejectsMissingFields(t *testing.T) {
	st := NewEventStore(&fakeStore{})
	if _, err := st.Append(context.Background(), Event{TenantID: "t1"}, false); err == nil {
		t.Fatal("missing event_id/type accepted")
	}
}
