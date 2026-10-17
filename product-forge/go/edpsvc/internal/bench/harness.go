// Package bench is the EDP-06 reproducible baseline-performance harness for the core data-plane operations
// (artifact list/read, project load/save, run transitions, memory retrieval, job claim/lease, DB/pool counts).
//
// It measures each scenario's latency over N operations and reports p50/p95/p99, then emits a versioned
// baseline report artifact (JSON). DB-backed scenarios run when PF_RUNTIME_DSN is set and self-skip otherwise,
// so the harness is safe in CI. Publishing the report into the observability/SLO sink is EDP-22's job (via the
// Sink seam below); this package is the measurement + artifact owner.
package bench

import (
	"context"
	"encoding/json"
	"os"
	"sort"
	"time"
)

// BaselineVersion is stamped on every emitted baseline report (artifact versioning).
const BaselineVersion = "baseline-v1"

// Result is the measured latency summary for one scenario.
type Result struct {
	Group    string  `json:"group"`
	Scenario string  `json:"scenario"`
	Ops      int     `json:"ops"`
	P50Ms    float64 `json:"p50_ms"`
	P95Ms    float64 `json:"p95_ms"`
	P99Ms    float64 `json:"p99_ms"`
	Err      string  `json:"err,omitempty"`
}

// Report is the versioned baseline artifact.
type Report struct {
	Version     string    `json:"version"`
	GeneratedAt time.Time `json:"generated_at"`
	DSN         string    `json:"dsn"`
	Results     []Result  `json:"results"`
}

// Measure runs fn ops times, collecting per-op latency, and returns the p50/p95/p99 summary. The first error
// stops the loop and is recorded on the Result (the measured samples so far are still reported).
func Measure(group, name string, ops int, fn func(i int) error) Result {
	if ops < 1 {
		ops = 1
	}
	r := Result{Group: group, Scenario: name}
	lat := make([]time.Duration, 0, ops)
	for i := 0; i < ops; i++ {
		t0 := time.Now()
		if err := fn(i); err != nil {
			r.Err = err.Error()
			break
		}
		lat = append(lat, time.Since(t0))
	}
	r.Ops = len(lat)
	if len(lat) == 0 {
		return r
	}
	sort.Slice(lat, func(i, j int) bool { return lat[i] < lat[j] })
	r.P50Ms = toMs(percentile(lat, 0.50))
	r.P95Ms = toMs(percentile(lat, 0.95))
	r.P99Ms = toMs(percentile(lat, 0.99))
	return r
}

// percentile returns the nearest-rank percentile of an already-sorted slice.
func percentile(sorted []time.Duration, p float64) time.Duration {
	if len(sorted) == 0 {
		return 0
	}
	idx := int(float64(len(sorted)-1) * p)
	if idx < 0 {
		idx = 0
	}
	if idx >= len(sorted) {
		idx = len(sorted) - 1
	}
	return sorted[idx]
}

func toMs(d time.Duration) float64 { return float64(d.Microseconds()) / 1000.0 }

// WriteReport writes the report as pretty JSON (a versioned artifact) at path.
func WriteReport(path string, rep Report) error {
	b, err := json.MarshalIndent(rep, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(b, '\n'), 0o644)
}

// Sink is where a baseline Report is published for observability / SLO consumption. The harness owns the
// measurement + the versioned artifact; the SINK is owned by EDP-22 (the benchmarks/SLO item), which provides
// a concrete Sink (e.g. an OTel metrics exporter or the SLO store) so this package stays transport-agnostic.
type Sink interface {
	Publish(ctx context.Context, rep Report) error
}

// Publish sends rep to sink. A nil sink is a no-op: the metrics are still captured and the artifact written,
// they are simply not forwarded to an observability store (which does not exist until EDP-22).
func Publish(ctx context.Context, sink Sink, rep Report) error {
	if sink == nil {
		return nil
	}
	return sink.Publish(ctx, rep)
}
