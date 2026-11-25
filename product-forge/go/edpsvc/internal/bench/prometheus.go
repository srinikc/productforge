package bench

import (
	"context"
	"fmt"
	"io"
	"strconv"
	"strings"
)

// PrometheusSink writes a Report as bounded Prometheus text metrics.
type PrometheusSink struct {
	W io.Writer
}

func (s PrometheusSink) Publish(_ context.Context, rep Report) error {
	if s.W == nil {
		return nil
	}
	for _, r := range rep.Results {
		labels := fmt.Sprintf(`group="%s",scenario="%s"`, escape(r.Group), escape(r.Scenario))
		if _, err := fmt.Fprintf(s.W, "edp_bench_p50_ms{%s} %s\n", labels, f(r.P50Ms)); err != nil {
			return err
		}
		if _, err := fmt.Fprintf(s.W, "edp_bench_p95_ms{%s} %s\n", labels, f(r.P95Ms)); err != nil {
			return err
		}
		if _, err := fmt.Fprintf(s.W, "edp_bench_p99_ms{%s} %s\n", labels, f(r.P99Ms)); err != nil {
			return err
		}
		errs := 0
		if r.Err != "" {
			errs = 1
		}
		if _, err := fmt.Fprintf(s.W, "edp_bench_scenario_errors{%s} %d\n", labels, errs); err != nil {
			return err
		}
	}
	_, err := fmt.Fprintf(s.W, "edp_bench_last_run_unixtime %d\n", rep.GeneratedAt.Unix())
	return err
}

func f(v float64) string { return strconv.FormatFloat(v, 'f', 3, 64) }

func escape(v string) string {
	return strings.NewReplacer(`\`, `\\`, `"`, `\"`, "\n", `\n`).Replace(v)
}
