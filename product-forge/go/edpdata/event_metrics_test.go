package edpdata

import (
	"context"
	"testing"
	"time"
)

type recordingMetrics struct {
	rows             int64
	rowsTenant       string
	rowsStatus       string
	boundExceeded    int
	pruned           int64
	projectionFailed int
}

func (m *recordingMetrics) OutboxRows(tenant, status string, count int64) {
	m.rowsTenant, m.rowsStatus, m.rows = tenant, status, count
}
func (m *recordingMetrics) OutboxBoundExceeded(string) { m.boundExceeded++ }
func (m *recordingMetrics) OutboxPruned(_ string, n int64) {
	m.pruned = n
}
func (m *recordingMetrics) ProjectionFailed(string) { m.projectionFailed++ }

func TestOutboxBoundEmitsGaugeAndCounter(t *testing.T) {
	f := &fakeStore{queries: [][][]any{{{int64(5)}}}}
	m := &recordingMetrics{}
	st := NewEventStore(f).WithMetrics(m).WithOutboxBound(1)
	if err := st.EnforceOutboxBound(context.Background(), "t1", 1); err == nil {
		t.Fatal("expected bound error")
	}
	if m.rows != 5 || m.rowsTenant != "t1" || m.rowsStatus != "pending" {
		t.Fatalf("rows metric = %+v", m)
	}
	if m.boundExceeded != 1 {
		t.Fatalf("bound counter = %d", m.boundExceeded)
	}
}

func TestPruneEmitsPrunedCount(t *testing.T) {
	m := &recordingMetrics{}
	st := NewEventStore(&fakeStore{}).WithMetrics(m)
	n, err := st.PruneOutbox(context.Background(), "t1", time.Hour)
	if err != nil {
		t.Fatal(err)
	}
	if n != 1 || m.pruned != 1 {
		t.Fatalf("pruned n=%d metric=%d", n, m.pruned)
	}
}

func TestProjectionFailureEmitsSignal(t *testing.T) {
	m := &recordingMetrics{}
	st := NewEventStore(&fakeStore{}).WithMetrics(m)
	st.RecordProjectionFailure("t1")
	if m.projectionFailed != 1 {
		t.Fatalf("projection failures = %d", m.projectionFailed)
	}
}
