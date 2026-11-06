// Command bench runs EDP-22 reproducible store baselines and optionally enforces SLO budgets.
package main

import (
	"context"
	"flag"
	"fmt"
	"os"

	"productforge/edpsvc/internal/bench"
)

func main() {
	dsn := flag.String("dsn", os.Getenv("PF_BENCH_DSN"), "benchmark PostgreSQL DSN (read-only role recommended)")
	ops := flag.Int("ops", 20, "measured operations per scenario")
	out := flag.String("out", "", "write versioned baseline JSON here")
	sink := flag.String("sink", "", "write Prometheus metrics here (default stdout)")
	baseline := flag.String("baseline", "config/edp-slo.json", "SLO budget file")
	enforce := flag.Bool("enforce", false, "exit non-zero on benchmark/SLO violations")
	allowSkip := flag.Bool("allow-skip", false, "allow missing DSN and record skipped scenarios")
	flag.Parse()

	if *dsn == "" && !*allowSkip {
		fmt.Fprintln(os.Stderr, "bench: PF_BENCH_DSN/dsn is required (use --allow-skip for explicit skipped evidence)")
		os.Exit(2)
	}
	var w *os.File = os.Stdout
	if *sink != "" {
		f, err := os.Create(*sink)
		if err != nil {
			fmt.Fprintln(os.Stderr, "bench:", err)
			os.Exit(1)
		}
		defer f.Close()
		w = f
	}
	rep, err := bench.RunAllWithSink(context.Background(), *dsn, *out, *ops, bench.PrometheusSink{W: w})
	if err != nil {
		fmt.Fprintln(os.Stderr, "bench:", err)
		os.Exit(1)
	}
	if *enforce {
		cfg, err := bench.LoadSLO(*baseline)
		if err != nil {
			fmt.Fprintln(os.Stderr, "bench:", err)
			os.Exit(1)
		}
		bad := bench.Compare(rep, cfg)
		for _, v := range bad {
			fmt.Fprintln(os.Stderr, "bench violation:", v)
		}
		if len(bad) > 0 {
			os.Exit(1)
		}
	}
	fmt.Printf("bench: %d scenario(s), version %s\n", len(rep.Results), rep.Version)
}
