// pfaudit-retention is the single writer for audit retention (EDP-20 / BI-PF-1312).
//
//	coverage | candidates | holds | export | purge | restore
//
// Two-stage policy: hot -> cold immutable archive (verified SHA-256 manifest) -> audited purge after a
// grace window. Row-level holds are extracted before a month leaves the hot table.
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"productforge/datastore"
	"productforge/pfaudit"
)

func main() {
	ctx := context.Background()
	if len(os.Args) < 2 {
		usage()
	}
	cmd := os.Args[1]
	fs := flag.NewFlagSet(cmd, flag.ExitOnError)
	dsn := fs.String("dsn", os.Getenv("PF_DB_DSN"), "PostgreSQL DSN")
	keep := fs.Int("keep-months", 13, "months of hot audit data to keep")
	month := fs.String("month", "", "audit_YYYYMM partition")
	actor := fs.String("actor", os.Getenv("PF_OPERATOR"), "operator identity (recorded)")
	reason := fs.String("reason", "", "reason (recorded)")
	dry := fs.Bool("dry-run", false, "print the plan without changing anything")
	_ = fs.Parse(os.Args[2:])

	if *dsn == "" {
		fail("PF_DB_DSN (or --dsn) is required")
	}
	pool, err := pgxpool.New(ctx, *dsn)
	if err != nil {
		fail("connect: %v", err)
	}
	defer pool.Close()
	obj := objectStore(ctx)
	met := pfaudit.NewMetrics()
	// The lock must live on one dedicated connection: a pool-level Exec may unlock on a different backend.
	lockConn, err := pool.Acquire(ctx)
	if err != nil {
		fail("retention lock conn: %v", err)
	}
	defer lockConn.Release()
	if _, err := lockConn.Exec(ctx, `SELECT pg_advisory_lock(hashtext('AURE'))`); err != nil {
		fail("retention lock: %v", err)
	}
	defer lockConn.Exec(ctx, `SELECT pg_advisory_unlock(hashtext('AURE'))`)

	switch cmd {
	case "coverage":
		c, err := pfaudit.ReadCoverage(ctx, pool)
		if err != nil {
			fail("%v", err)
		}
		fmt.Printf("min=%v max=%v grace=%v months_ahead=%d\n",
			fmtTime(c.MinMonth), fmtTime(c.MaxMonth), fmtTime(c.GraceMonth), c.MonthsAhead)
		met.Gauge(pfaudit.MetricMonthsAhead, float64(c.MonthsAhead))
		if c.MonthsAhead < 2 {
			met.Inc(pfaudit.MetricLowCoverage)
		}
		if c.MinMonth != nil && c.MaxMonth != nil {
			fmt.Printf("retention: keep %d month(s); candidates are fully-old months only\n", *keep)
		}
	case "candidates":
		months, err := pfaudit.RetentionCandidates(ctx, pool, *keep)
		if err != nil {
			fail("%v", err)
		}
		for _, m := range months {
			fmt.Println(m)
		}
	case "holds":
		if *month == "" {
			fail("--month is required")
		}
		if *dry {
			fmt.Printf("would extract held rows from %s\n", *month)
			return
		}
		n, err := pfaudit.ExtractHolds(ctx, pool, *month)
		if err != nil {
			fail("%v", err)
		}
		met.Inc(pfaudit.MetricHoldExtract)
		if err := verifyHolds(ctx, pool, met, *month); err != nil {
			fail("%v", err)
		}
		fmt.Printf("holds: extracted %d row(s) from %s (verified)\n", n, *month)
	case "export":
		months, err := pfaudit.RetentionCandidates(ctx, pool, *keep)
		if err != nil {
			fail("%v", err)
		}
		for _, mon := range months {
			if *dry {
				fmt.Printf("would export+drop %s\n", mon)
				continue
			}
			if n, err := pfaudit.ExtractHolds(ctx, pool, mon); err != nil {
				fail("holds %s: %v", mon, err)
			} else if n > 0 {
				fmt.Printf("%s: extracted %d held row(s)\n", mon, n)
				met.Inc(pfaudit.MetricHoldExtract)
			}
			if err := verifyHolds(ctx, pool, met, mon); err != nil {
				fail("holds %s: %v", mon, err)
			}
			man, err := pfaudit.ExportMonth(ctx, pool, obj, mon)
			if err != nil {
				fail("export %s: %v", mon, err)
			}
			met.Inc(pfaudit.MetricExport)
			if err != nil {
				fail("export %s: %v", mon, err)
			}
			fmt.Printf("%s: exported rows=%d sha256=%s key=%s\n", mon, man.Rows, man.Checksum, man.Keys)
			if _, err := pool.Exec(ctx, `SELECT audit_drop_partition($1)`, mon); err != nil {
				fail("drop %s: %v", mon, err)
			}
			fmt.Printf("%s: hot partition dropped\n", mon)
		}
	case "purge":
		if *month == "" || *actor == "" || *reason == "" {
			fail("--month, --actor and --reason are required")
		}
		if *dry {
			fmt.Printf("would purge archived objects for %s (grace + approval checked in DB)\n", *month)
			return
		}
		if err := pfaudit.PurgeMonth(ctx, pool, obj, *month, *actor, *reason); err != nil {
			fail("%v", err)
		}
		met.Inc(pfaudit.MetricPurge)
		fmt.Printf("purged %s (irreversible; approval recorded)\n", *month)
	case "restore":
		if *month == "" {
			fail("--month is required")
		}
		n, err := pfaudit.RestoreMonth(ctx, pool, obj, *month)
		if err != nil {
			fail("%v", err)
		}
		fmt.Printf("restored %d row(s) from %s into a scratch partitioned table\n", n, *month)
	default:
		usage()
	}
	emitMetrics(met)
}

func verifyHolds(ctx context.Context, pool *pgxpool.Pool, met *pfaudit.Metrics, month string) error {
	archived, missing, err := pfaudit.VerifyHoldExtraction(ctx, pool, month)
	if err != nil {
		return err
	}
	if missing != 0 {
		met.Inc(pfaudit.MetricHoldUnarchived)
		return fmt.Errorf("holds %s: %d held row(s) are NOT archived - refusing to drop", month, missing)
	}
	fmt.Printf("holds %s: archived=%d missing=0\n", month, archived)
	return nil
}

func emitMetrics(m *pfaudit.Metrics) {
	c, g := m.Snapshot()
	if len(c) == 0 && len(g) == 0 {
		return
	}
	b, _ := json.Marshal(map[string]any{"metrics": c, "gauges": g})
	fmt.Println(string(b))
}

func objectStore(ctx context.Context) datastore.ObjectStore {
	obj, err := pfaudit.ObjectStore(ctx)
	if err != nil {
		fail("object store: %v", err)
	}
	if sse := pfaudit.DefaultSSE(); sse != "" {
		if err := pfaudit.CheckSSE(obj, sse); err != nil {
			fail("%v", err)
		}
	}
	return obj
}

func fmtTime(t *time.Time) string { return pfaudit.MonthLabel(t) }

func usage() {
	fmt.Fprintln(os.Stderr, "usage: pfaudit-retention <coverage|candidates|holds|export|purge|restore> [flags]")
	os.Exit(2)
}

func fail(format string, args ...any) {
	fmt.Fprintf(os.Stderr, "pfaudit-retention: "+format+"\n", args...)
	os.Exit(1)
}
