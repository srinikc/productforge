// pfaudit-retention is the single writer for audit retention (EDP-20 / BI-PF-1312).
//
//	coverage | candidates | holds | export | purge | restore
//
// Two-stage policy: hot -> cold immutable archive (verified SHA-256 manifest) -> audited purge after a
// grace window. Row-level holds are extracted before a month leaves the hot table.
package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"productforge/datastore"
	"productforge/objstore"
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
	root := fs.String("object-root", os.Getenv("PF_OBJECT_ROOT"), "local object-store root")
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
	obj := objectStore(*root)
	if _, err := pool.Exec(ctx, `SELECT pg_advisory_lock(hashtext('AURE'))`); err != nil {
		fail("retention lock: %v", err)
	}
	defer pool.Exec(ctx, `SELECT pg_advisory_unlock(hashtext('AURE'))`)

	switch cmd {
	case "coverage":
		c, err := pfaudit.ReadCoverage(ctx, pool)
		if err != nil {
			fail("%v", err)
		}
		fmt.Printf("min=%v max=%v grace=%v months_ahead=%d\n",
			fmtTime(c.MinMonth), fmtTime(c.MaxMonth), fmtTime(c.GraceMonth), c.MonthsAhead)
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
		fmt.Printf("holds: extracted %d row(s) from %s\n", n, *month)
	case "export":
		months, err := pfaudit.RetentionCandidates(ctx, pool, *keep)
		if err != nil {
			fail("%v", err)
		}
		for _, m := range months {
			if *dry {
				fmt.Printf("would export+drop %s\n", m)
				continue
			}
			if n, err := pfaudit.ExtractHolds(ctx, pool, m); err != nil {
				fail("holds %s: %v", m, err)
			} else if n > 0 {
				fmt.Printf("%s: extracted %d held row(s)\n", m, n)
			}
			man, err := pfaudit.ExportMonth(ctx, pool, obj, m)
			if err != nil {
				fail("export %s: %v", m, err)
			}
			fmt.Printf("%s: exported rows=%d sha256=%s key=%s\n", m, man.Rows, man.Checksum, man.Keys)
			if _, err := pool.Exec(ctx, `SELECT audit_drop_partition($1)`, m); err != nil {
				fail("drop %s: %v", m, err)
			}
			fmt.Printf("%s: hot partition dropped\n", m)
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
}

func objectStore(root string) datastore.ObjectStore {
	if root == "" {
		root = os.TempDir() + string(os.PathSeparator) + "pfaudit-objects"
	}
	obj, err := objstore.NewLocalStore(root, 1<<34)
	if err != nil {
		fail("object store: %v", err)
	}
	return obj
}

func fmtTime(t *time.Time) string {
	if t == nil {
		return "-"
	}
	return t.Format("2006-01-02")
}

func usage() {
	fmt.Fprintln(os.Stderr, "usage: pfaudit-retention <coverage|candidates|holds|export|purge|restore> [flags]")
	os.Exit(2)
}

func fail(format string, args ...any) {
	fmt.Fprintf(os.Stderr, "pfaudit-retention: "+format+"\n", args...)
	os.Exit(1)
}
