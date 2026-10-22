// pfaudit-swap is the out-of-transaction audit partitioning swap (EDP-20 / BI-PF-1312).
//
//	plan | status | backup | prestage | verify | swap | close | down
//
// It is idempotent and crash-safe: every run re-derives its phase from the catalog, so a kill after the
// rename simply resumes at post-swap verification.
package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"os/exec"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgconn"
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
	batch := fs.Int("batch", pfaudit.DefaultBatchRows, "rows per copy batch")
	maxDelta := fs.Int("max-delta", pfaudit.DefaultMaxDeltaRows, "maximum delta rows to drain under the lock")
	objRoot := fs.String("object-root", os.Getenv("PF_OBJECT_ROOT"), "local object-store root (when no cloud adapter)")
	backupKey := fs.String("backup-key", os.Getenv("PF_AUDIT_BACKUP_KEY"), "object key of the encrypted pre-swap dump")
	recipient := fs.String("age-recipient", os.Getenv("PF_AGE_RECIPIENT"), "age recipient for the encrypted dump")
	force := fs.Bool("force-with-reason", false, "down: proceed even with archives/holds (audited)")
	reason := fs.String("reason", "", "down: mandatory reason when forcing")
	_ = fs.Parse(os.Args[2:])

	if *dsn == "" {
		fail("PF_DB_DSN (or --dsn) is required")
	}
	pool, err := pgxpool.New(ctx, *dsn)
	if err != nil {
		fail("connect: %v", err)
	}
	defer pool.Close()

	switch cmd {
	case "plan", "status":
		var major int
		if err := pool.QueryRow(ctx, "SHOW server_version_num").Scan(&major); err != nil {
			fail("server version: %v", err)
		}
		if major < 140000 {
			fail("PostgreSQL >= 14 is required (server_version_num=%d)", major)
		}
		st, err := pfaudit.DetectState(ctx, pool)
		if err != nil {
			fail("%v", err)
		}
		fmt.Printf("state=%s\n", st)
		if b, m, err := pfaudit.CheckConfig(ctx, pool); err != nil {
			fmt.Printf("config: %v\n", err)
		} else {
			fmt.Printf("config: batch_rows=%d max_delta_rows=%d\n", b, m)
		}
		cov, err := pfaudit.ReadCoverage(ctx, pool)
		if err == nil {
			fmt.Printf("coverage: min=%v max=%v grace=%v months_ahead=%d\n",
				deref(cov.MinMonth), deref(cov.MaxMonth), deref(cov.GraceMonth), cov.MonthsAhead)
		}
	case "backup":
		if *recipient == "" {
			fail("--age-recipient (or PF_AGE_RECIPIENT) is required: the dump must be encrypted at rest")
		}
		if *backupKey == "" {
			*backupKey = fmt.Sprintf("audit-backup/%s/audit.dump.age", time.Now().UTC().Format("20060102T150405"))
		}
		if err := backup(ctx, *dsn, *objRoot, *backupKey, *recipient); err != nil {
			fail("%v", err)
		}
		fmt.Printf("backup written: %s\n", *backupKey)
		fail("run the restore rehearsal before prestage; then: --backup-key %s", *backupKey)
	case "prestage":
		runPrestage(ctx, pool, *batch)
		_, _, _ = pfaudit.CheckConfig(ctx, pool)
	case "verify":
		problems, err := pfaudit.Verify(ctx, pool)
		for t, p := range problems {
			fmt.Printf("MISMATCH %s: %s\n", t, p)
		}
		if err != nil {
			fail("%v", err)
		}
		fmt.Println("verify: OK (per-tenant count + sha256 match)")
	case "swap":
		runSwap(ctx, pool, *maxDelta)
	case "close":
		if *backupKey == "" {
			fail("--backup-key is required to close: the dump must survive until sign-off")
		}
		if err := pfaudit.RecordState(ctx, pool, "swap_closed", fmt.Sprintf(`{"backup":%q}`, *backupKey)); err != nil {
			fail("record close: %v", err)
		}
		obj := openObjectStore(*objRoot)
		if err := obj.Delete(ctx, *backupKey, ""); err != nil {
			fail("delete backup after sign-off: %v", err)
		}
		fmt.Println("closed: sign-off recorded, encrypted dump destroyed")
	case "down":
		if err := pfaudit.Down(ctx, pool, *force, *reason); err != nil {
			fail("%v", err)
		}
		fmt.Println("down: reverted to the flat audit table")
	default:
		usage()
	}
}

func runPrestage(ctx context.Context, pool *pgxpool.Pool, batch int) {
	var cursor int64
	if err := pool.QueryRow(ctx, `SELECT COALESCE((value->>'last_id')::bigint, 0) FROM audit_migration_state WHERE key = 'copy'`).
		Scan(&cursor); err != nil {
		cursor = 0
	}
	total := 0
	for {
		r, err := pfaudit.CopyBatch(ctx, pool, cursor, batch)
		if err != nil {
			fail("prestage: %v", err)
		}
		cursor = r.LastID
		total += int(r.Inserted)
		if _, err := pool.Exec(ctx, `INSERT INTO audit_migration_state(key, value, updated_at)
			VALUES ('copy', jsonb_build_object('last_id', $1), now())
			ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()`, cursor); err != nil {
			fail("persist cursor: %v", err)
		}
		fmt.Printf("prestage: read=%d inserted=%d cursor=%d\n", r.Read, r.Inserted, r.LastID)
		if r.Done {
			break
		}
	}
	fmt.Printf("prestage complete: %d row(s) newly staged\n", total)
}

func runSwap(ctx context.Context, pool *pgxpool.Pool, maxDelta int) {
	backoff := time.Second
	for attempt := 1; attempt <= pfaudit.MaxSwapAttempts; attempt++ {
		n, err := pfaudit.Swap(ctx, pool, maxDelta)
		if err == nil {
			if err := pfaudit.RecordState(ctx, pool, "swapped", fmt.Sprintf(`{"drained":%d}`, n)); err != nil {
				fail("record swap: %v", err)
			}
			fmt.Printf("swap: committed (drained %d row(s))\n", n)
			return
		}
		var pgErr *pgconn.PgError
		retryable := strings.Contains(err.Error(), "exceeds max_delta_rows")
		if errors.As(err, &pgErr) {
			retryable = retryable || pgErr.Code == "55P03"
		}
		if !retryable {
			fail("swap: %v", err)
		}
		fmt.Printf("swap attempt %d/%d deferred: %v\n", attempt, pfaudit.MaxSwapAttempts, err)
		time.Sleep(backoff)
		backoff *= 2
	}
	_ = pfaudit.RecordState(ctx, pool, "retry_exhausted", "{}")
	fail("swap: retry budget exhausted; re-run prestage and retry")
}

func backup(ctx context.Context, dsn, root, key, recipient string) error {
	dump := exec.CommandContext(ctx, "pg_dump", "-Fc", "-t", "audit", "-f", "-", dsn)
	age := exec.CommandContext(ctx, "age", "-r", recipient)
	dp, err := dump.StdoutPipe()
	if err != nil {
		return err
	}
	pr, pw := io.Pipe()
	age.Stdin = dp
	age.Stdout = pw
	dump.Stderr, age.Stderr = os.Stderr, os.Stderr
	if err := dump.Start(); err != nil {
		return fmt.Errorf("pg_dump: %w", err)
	}
	if err := age.Start(); err != nil {
		return fmt.Errorf("age: %w", err)
	}
	go func() { pw.CloseWithError(age.Wait()) }()
	obj := openObjectStore(root)
	info, putErr := obj.Put(ctx, key, pr, -1, datastore.PutOptions{
		ContentType: "application/octet-stream", Immutable: true, Retention: 14 * 24 * time.Hour,
	})
	if werr := dump.Wait(); werr != nil {
		return fmt.Errorf("pg_dump: %w", werr)
	}
	if putErr != nil {
		return fmt.Errorf("put backup: %w", putErr)
	}
	if info.Size == 0 || info.Key == "" {
		return fmt.Errorf("empty backup object")
	}
	return nil
}

func openObjectStore(root string) datastore.ObjectStore {
	if root == "" {
		root = os.TempDir() + string(os.PathSeparator) + "pfaudit-objects"
	}
	obj, err := objstore.NewLocalStore(root, 1<<34)
	if err != nil {
		fail("object store: %v", err)
	}
	return obj
}

func deref(t *time.Time) string {
	if t == nil {
		return "-"
	}
	return t.Format("2006-01-02")
}

func usage() {
	fmt.Fprintln(os.Stderr, "usage: pfaudit-swap <plan|status|backup|prestage|verify|swap|close|down> [flags]")
	os.Exit(2)
}

func fail(format string, args ...any) {
	fmt.Fprintf(os.Stderr, "pfaudit-swap: "+format+"\n", args...)
	os.Exit(1)
}
