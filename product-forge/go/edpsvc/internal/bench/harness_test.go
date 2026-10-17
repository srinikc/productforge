package bench

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestMeasureComputesPercentiles(t *testing.T) {
	r := Measure("g", "s", 25, func(i int) error {
		time.Sleep(time.Duration(i%3) * 50 * time.Microsecond)
		return nil
	})
	if r.Ops != 25 || r.P50Ms <= 0 {
		t.Fatalf("measure: %+v", r)
	}
	if !(r.P50Ms <= r.P95Ms && r.P95Ms <= r.P99Ms) {
		t.Fatalf("percentiles not monotonic: p50=%v p95=%v p99=%v", r.P50Ms, r.P95Ms, r.P99Ms)
	}
}

func TestMeasureRecordsFirstError(t *testing.T) {
	r := Measure("g", "s", 10, func(i int) error {
		if i == 3 {
			return context.DeadlineExceeded
		}
		return nil
	})
	if r.Err == "" || r.Ops != 3 {
		t.Fatalf("first error not recorded: %+v", r)
	}
}

func TestReportRoundTripsAndIsVersioned(t *testing.T) {
	p := filepath.Join(t.TempDir(), "baseline.json")
	rep := Report{Version: BaselineVersion, GeneratedAt: time.Now().UTC(), DSN: "x",
		Results: []Result{{Group: "db", Scenario: "db.pool_counts", Ops: 5, P50Ms: 1.5}}}
	if err := WriteReport(p, rep); err != nil {
		t.Fatal(err)
	}
	raw, err := os.ReadFile(p)
	if err != nil {
		t.Fatal(err)
	}
	var got Report
	if err := json.Unmarshal(raw, &got); err != nil {
		t.Fatal(err)
	}
	if got.Version != BaselineVersion || len(got.Results) != 1 || got.Results[0].P50Ms != 1.5 {
		t.Fatalf("round-trip: %+v", got)
	}
}

func TestScenariosCoverSixGroups(t *testing.T) {
	seen := map[string]bool{}
	for _, s := range scenarios() {
		seen[s.group] = true
	}
	want := Groups()
	if len(want) != 6 || len(seen) != 6 {
		t.Fatalf("groups: want 6, got scenarios=%v", seen)
	}
	for _, g := range want {
		if !seen[g] {
			t.Fatalf("group %q has no scenario", g)
		}
	}
}

func TestRunAllWithoutDSNStillReports(t *testing.T) {
	rep, err := RunAll(context.Background(), "", "", 3)
	if err != nil {
		t.Fatal(err)
	}
	if rep.Version != BaselineVersion || len(rep.Results) == 0 {
		t.Fatalf("report: %+v", rep)
	}
	for _, r := range rep.Results {
		if r.Err == "" {
			t.Fatalf("expected skip err for %s", r.Scenario)
		}
	}
}
