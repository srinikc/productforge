package bench

import (
	"bytes"
	"context"
	"strings"
	"testing"
	"time"
)

func TestCompareReportsLatencyAndErrors(t *testing.T) {
	rep := Report{Results: []Result{
		{Group: "db", Scenario: "db.pool", P95Ms: 10, P99Ms: 20},
		{Group: "object", Scenario: "object.read", P95Ms: 900, P99Ms: 3000},
		{Group: "queue", Scenario: "queue.claim", Err: "boom"},
	}}
	cfg := SLOConfig{Version: 1, Defaults: SLO{P95Ms: 500, P99Ms: 2000},
		Groups: map[string]SLO{"db": {P95Ms: 50, P99Ms: 100}}}
	bad := Compare(rep, cfg)
	if len(bad) < 3 {
		t.Fatalf("want latency/error violations, got %+v", bad)
	}
}

func TestPrometheusSinkIsBoundedAndEscaped(t *testing.T) {
	var b bytes.Buffer
	rep := Report{GeneratedAt: time.Unix(10, 0), Results: []Result{{Group: "db", Scenario: `db"x`, P50Ms: 1, P95Ms: 2, P99Ms: 3}}}
	if err := (PrometheusSink{W: &b}).Publish(context.Background(), rep); err != nil {
		t.Fatal(err)
	}
	out := b.String()
	if !strings.Contains(out, `group="db"`) || !strings.Contains(out, `db\"x`) {
		t.Fatalf("missing bounded labels: %s", out)
	}
	if !strings.Contains(out, "edp_bench_last_run_unixtime 10") {
		t.Fatalf("missing freshness metric: %s", out)
	}
}
