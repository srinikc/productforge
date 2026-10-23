// pfaudit-swap is the out-of-transaction audit partitioning swap (EDP-20 / BI-PF-1312).
//
//	plan | status | backup | prestage | verify | swap | close | down
//
// It is idempotent and crash-safe: every run re-derives its phase from the catalog, so a kill after the
// rename simply resumes at post-swap verification.
package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net/url"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgconn"
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
	batch := fs.Int("batch", pfaudit.DefaultBatchRows, "rows per copy batch")
	maxDelta := fs.Int("max-delta", pfaudit.DefaultMaxDeltaRows, "maximum delta rows to drain under the lock")
	metricsOut := fs.Bool("metrics", true, "emit one structured metrics line on exit")
	backupKey := fs.String("backup-key", os.Getenv("PF_AUDIT_BACKUP_KEY"), "object key of the encrypted pre-swap dump")
	recipient := fs.String("age-recipient", os.Getenv("PF_AGE_RECIPIENT"), "age recipient for the encrypted dump")
	force := fs.Bool("force-with-reason", false, "down: proceed even with archives/holds (audited)")
	dryRun := fs.Bool("dry-run", false, "down: report the plan and exit without changing data")
	reason := fs.String("reason", "", "down: mandatory reason when forcing")
	_ = fs.Parse(os.Args[2:])
	batchSet, deltaSet := false, false
	fs.Visit(func(f *flag.Flag) {
		switch f.Name {
		case "batch":
			batchSet = true
		case "max-delta":
			deltaSet = true
		}
	})

	if *dsn == "" {
		fail("PF_DB_DSN (or --dsn) is required")
	}
	pool, err := pgxpool.New(ctx, *dsn)
	if err != nil {
		fail("connect: %v", err)
	}
	defer pool.Close()
	m := pfaudit.NewMetrics()
	activeMetrics = m
	if cmd == "prestage" || cmd == "swap" {
		// The DB config is the source of truth unless the operator explicitly overrides it.
		cfgBatch, cfgMax, cerr := pfaudit.CheckConfig(ctx, pool)
		if cerr != nil {
			fail("%v", cerr)
		}
		if !batchSet {
			*batch = cfgBatch
		}
		if !deltaSet {
			*maxDelta = cfgMax
		}
	}

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
			m.Gauge(pfaudit.MetricMonthsAhead, float64(cov.MonthsAhead))
			if cov.MonthsAhead < 2 {
				m.Inc(pfaudit.MetricLowCoverage)
			}
		}
	case "backup":
		if *recipient == "" {
			fail("--age-recipient (or PF_AGE_RECIPIENT) is required: the dump must be encrypted at rest")
		}
		if *backupKey == "" {
			*backupKey = fmt.Sprintf("audit-backup/%s/audit.dump.age", time.Now().UTC().Format("20060102T150405"))
		}
		var rollbackDays int
		if err := pool.QueryRow(ctx, `SELECT rollback_days FROM audit_partition_config WHERE id`).Scan(&rollbackDays); err != nil {
			fail("backup: read rollback_days: %v", err)
		}
		obj := openObjectStore(ctx)
		if err := backup(ctx, pool, *dsn, obj, *backupKey, *recipient, rollbackDays); err != nil {
			fail("%v", err)
		}
		if err := rehearsal(ctx, obj, *backupKey); err != nil {
			fail("restore rehearsal: %v", err)
		}
		fmt.Printf("backup written + rehearsal OK: %s (pass --backup-key %s to close)\n", *backupKey, *backupKey)
	case "prestage":
		runPrestage(ctx, pool, *batch, m)
	case "verify":
		problems, err := pfaudit.Verify(ctx, pool)
		for t, p := range problems {
			fmt.Printf("MISMATCH %s: %s\n", t, p)
		}
		if err != nil {
			fail("%v", err)
		}
		if err := pfaudit.RecordState(ctx, pool, "verified", "{}"); err != nil {
			fail("record verify: %v", err)
		}
		fmt.Println("verify: OK (per-tenant count + sha256 match)")
	case "swap":
		runSwap(ctx, pool, *maxDelta, m)
	case "close":
		if *backupKey == "" {
			fail("--backup-key is required to close: the dump must survive until sign-off")
		}
		var elapsed float64
		if err := pool.QueryRow(ctx, `SELECT COALESCE(EXTRACT(EPOCH FROM (now() - max(at)))/86400, -1)
			FROM audit_migration_state_events WHERE to_state = 'swapped'`).Scan(&elapsed); err != nil || elapsed < 0 {
			fail("close: no recorded swap (elapsed=%v err=%v)", elapsed, err)
		}
		var window int
		if err := pool.QueryRow(ctx, `SELECT rollback_days FROM audit_partition_config WHERE id`).Scan(&window); err != nil {
			fail("close: read rollback_days: %v", err)
		}
		if elapsed < float64(window) && !(*force && *reason != "") {
			fail("close: rollback window is %dd, only %.1fd elapsed (use --force-with-reason --reason)", window, elapsed)
		}
		// Record the sign-off FIRST: if the delete then fails we keep an auditable trail and an orphan
		// backup (recoverable), never an untracked destruction.
		if err := pfaudit.RecordState(ctx, pool, "swap_closed", fmt.Sprintf(`{"backup":%q}`, *backupKey)); err != nil {
			fail("record close: %v", err)
		}
		obj := openObjectStore(ctx)
		if err := obj.Delete(ctx, *backupKey, ""); err != nil {
			fail("delete backup after sign-off: %v", err)
		}
		fmt.Println("closed: sign-off recorded, encrypted dump destroyed")
	case "down":
		if *dryRun {
			st, archived, holds, err := pfaudit.DownPlan(ctx, pool)
			if err != nil {
				fail("%v", err)
			}
			fmt.Printf("down plan: state=%s archived_months=%d active_holds=%d force_required=%v\n",
				st, archived, holds, archived > 0 || holds > 0)
			if st != pfaudit.StateSwapped {
				fail("down requires the swapped state, got %s", st)
			}
			return
		}
		if err := pfaudit.Down(ctx, pool, *force, *reason); err != nil {
			fail("%v", err)
		}
		fmt.Println("down: reverted to the flat audit table")
	default:
		usage()
	}
	if *metricsOut {
		emitMetrics(m)
	}
}

func emitMetrics(m *pfaudit.Metrics) {
	metricsEmitted = true
	c, g := m.Snapshot()
	if len(c) == 0 && len(g) == 0 {
		return
	}
	b, _ := json.Marshal(map[string]any{"metrics": c, "gauges": g})
	fmt.Fprintln(os.Stderr, string(b))
}

func runPrestage(ctx context.Context, pool *pgxpool.Pool, batch int, m *pfaudit.Metrics) {
	var cursor int64
	if err := pool.QueryRow(ctx, `SELECT COALESCE((value->>'last_id')::bigint, 0) FROM audit_migration_state WHERE key = 'copy'`).
		Scan(&cursor); err != nil {
		cursor = 0
	}
	if cursor > 0 {
		m.Inc(pfaudit.MetricCopyResumed)
	}
	total := 0
	for {
		r, err := pfaudit.CopyBatch(ctx, pool, cursor, batch)
		if err != nil {
			fail("prestage: %v", err)
		}
		cursor = r.LastID
		total += int(r.Inserted)
		if err := pfaudit.SaveCursor(ctx, pool, cursor); err != nil {
			fail("persist cursor: %v", err)
		}
		fmt.Printf("prestage: read=%d inserted=%d cursor=%d\n", r.Read, r.Inserted, r.LastID)
		if r.Done {
			break
		}
	}
	if err := pfaudit.RecordState(ctx, pool, "prestaged", fmt.Sprintf(`{"inserted":%d}`, total)); err != nil {
		fail("record prestage: %v", err)
	}
	fmt.Printf("prestage complete: %d row(s) newly staged\n", total)
}

func runSwap(ctx context.Context, pool *pgxpool.Pool, maxDelta int, m *pfaudit.Metrics) {
	st, err := pfaudit.DetectState(ctx, pool)
	if err != nil {
		fail("swap: detect state: %v", err)
	}
	if st == pfaudit.StateSwapped {
		// Crash after the rename: the data is already live - finish verification instead of re-swapping.
		if err := pfaudit.PostVerify(ctx, pool); err != nil {
			if recErr := pfaudit.RecordState(ctx, pool, "swap_verify_failed", fmt.Sprintf(`{"error":%q}`, err.Error())); recErr != nil {
				fmt.Printf("WARN swap: record verification failure: %v\n", recErr)
			}
			fail("swap: resume verification failed: %v", err)
		}
		// Record the commit even on resume: `close` keys off this event and must not be blocked by a crash.
		if err := pfaudit.RecordState(ctx, pool, "swapped", `{"resumed":true}`); err != nil {
			fail("swap: record resumed swap: %v", err)
		}
		fmt.Println("swap: already committed; post-swap verification OK")
		return
	}
	if st != pfaudit.StatePrestage {
		fail("swap: requires pre-staged state, got %s (run backup + prestage first)", st)
	}
	if problems, err := pfaudit.Verify(ctx, pool); err != nil {
		fail("swap: pre-swap verify: %v", err)
	} else if len(problems) != 0 {
		for t, p := range problems {
			fmt.Printf("MISMATCH %s: %s\n", t, p)
		}
		fail("swap: refusing to swap with %d mismatch(es)", len(problems))
	}
	backoff := time.Second
	for attempt := 1; attempt <= pfaudit.MaxSwapAttempts; attempt++ {
		start := time.Now()
		n, err := pfaudit.Swap(ctx, pool, maxDelta)
		if err == nil {
			// Freeze ends when the rename transaction commits; verification happens after the writers resume.
			frozen := time.Since(start)
			m.Gauge(pfaudit.MetricSwapFreeze, frozen.Seconds())
			if err := pfaudit.PostVerify(ctx, pool); err != nil {
				if strings.Contains(err.Error(), "hardening") {
					m.Inc(pfaudit.MetricAttachUnhardened)
				}
				fail("swap: committed but post-verification failed: %v", err)
			}
			if budget := os.Getenv("PF_AUDIT_FREEZE_BUDGET_SECONDS"); budget != "" {
				if secs, convErr := strconv.ParseFloat(budget, 64); convErr == nil && frozen.Seconds() > secs {
					fail("swap: freeze %.1fs exceeds budget %.1fs (committed; investigate before close)",
						frozen.Seconds(), secs)
				}
			}
			if err := pfaudit.RecordState(ctx, pool, "swapped",
				fmt.Sprintf(`{"drained":%d,"freeze_seconds":%.3f}`, n, frozen.Seconds())); err != nil {
				fail("record swap: %v", err)
			}
			fmt.Printf("swap: committed (drained %d row(s), freeze %.1fs)\n", n, frozen.Seconds())
			return
		}
		retryable := errors.Is(err, pfaudit.ErrDeltaTooLarge) || errors.Is(err, pfaudit.ErrLockTimeout)
		var pgErr *pgconn.PgError
		if errors.As(err, &pgErr) && pgErr.Code == "55P03" {
			retryable = true
		}
		if !retryable {
			fail("swap: %v", err)
		}
		m.Inc(pfaudit.MetricSwapRetry)
		fmt.Printf("swap attempt %d/%d deferred: %v\n", attempt, pfaudit.MaxSwapAttempts, err)
		if attempt == pfaudit.MaxSwapAttempts {
			break
		}
		time.Sleep(backoff)
		backoff *= 2
	}
	m.Inc(pfaudit.MetricSwapRetryExhaust)
	_ = pfaudit.RecordState(ctx, pool, "retry_exhausted", "{}")
	fail("swap: retry budget exhausted; re-run prestage and retry")
}

// rehearsal proves the encrypted dump is readable and contains the table, its sequence and RLS policies.
func rehearsal(ctx context.Context, obj datastore.ObjectStore, key string) error {
	rc, _, err := obj.Get(ctx, key, "")
	if err != nil {
		return err
	}
	defer rc.Close()
	tmp, err := os.CreateTemp("", "pfaudit-backup-*.age")
	if err != nil {
		return err
	}
	defer os.Remove(tmp.Name())
	if _, err := io.Copy(tmp, rc); err != nil {
		return err
	}
	tmp.Close()
	// age is required to reach plaintext; a missing key is a hard failure, not a skip.
	dec := exec.CommandContext(ctx, "age", "-d", "-i", os.Getenv("PF_AGE_IDENTITY"), tmp.Name())
	list := exec.CommandContext(ctx, "pg_restore", "-l")
	pr, pw := io.Pipe()
	dec.Stdout = pw
	dec.Stderr = os.Stderr
	list.Stdin = pr
	if startErr := dec.Start(); startErr != nil {
		pr.Close()
		return fmt.Errorf("age -d: %w", startErr)
	}
	go func() { pw.CloseWithError(dec.Wait()) }()
	out, err := list.Output()
	if err != nil {
		return fmt.Errorf("pg_restore -l: %w", err)
	}
	for _, want := range []string{"TABLE public audit", "SEQUENCE public audit_legacy_id_seq"} {
		if !strings.Contains(string(out), want) {
			return fmt.Errorf("dump is missing %q", want)
		}
	}
	return nil
}

func backup(ctx context.Context, pool *pgxpool.Pool, dsn string, obj datastore.ObjectStore, key, recipient string, rollbackDays int) error {
	safeDSN, password := splitDSN(dsn)
	dump := exec.CommandContext(ctx, "pg_dump", "-Fc", "-t", "audit", "-t", "audit_legacy_id_seq",
		"-t", "audit_id_seq", "-f", "-", safeDSN)
	if password != "" {
		dump.Env = append(os.Environ(), "PGPASSWORD="+password)
	}
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
	h := sha256.New()
	info, putErr := obj.Put(ctx, key, io.TeeReader(pr, h), -1, datastore.PutOptions{
		ContentType: "application/octet-stream", Immutable: true, Retention: backupRetention(rollbackDays),
		ServerSideEncryption: pfaudit.DefaultSSE(),
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
	digest := hex.EncodeToString(h.Sum(nil))
	if err := pfaudit.RecordState(ctx, pool, "backup", fmt.Sprintf(`{"key":%q,"sha256":%q}`, key, digest)); err != nil {
		return fmt.Errorf("record backup digest: %w", err)
	}
	if info.Checksum != "" && info.Checksum != digest {
		return fmt.Errorf("backup checksum mismatch: store=%s local=%s", info.Checksum, digest)
	}
	return nil
}

// splitDSN removes the password from the argv-visible DSN and returns it for PGPASSWORD instead.
func splitDSN(dsn string) (string, string) {
	u, err := url.Parse(dsn)
	if err != nil || u.User == nil {
		return dsn, ""
	}
	pw, has := u.User.Password()
	if !has {
		return dsn, ""
	}
	u.User = url.User(u.User.Username())
	return u.String(), pw
}

func openObjectStore(ctx context.Context) datastore.ObjectStore {
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

func deref(t *time.Time) string { return pfaudit.MonthLabel(t) }

func usage() {
	fmt.Fprintln(os.Stderr, "usage: pfaudit-swap <plan|status|backup|prestage|verify|swap|close|down> [flags]")
	os.Exit(2)
}

var (
	activeMetrics  *pfaudit.Metrics
	metricsEmitted bool
)

// backupRetention keeps the encrypted dump at least as long as the rollback window unless overridden.
func backupRetention(rollbackDays int) time.Duration {
	if v := os.Getenv("PF_AUDIT_BACKUP_RETENTION_DAYS"); v != "" {
		if d, err := strconv.Atoi(v); err == nil && d > 0 {
			return time.Duration(d) * 24 * time.Hour
		}
	}
	// Never expire the dump before the rollback window closes (plus a week of slack).
	if days := rollbackDays + 7; days > 30 {
		return time.Duration(days) * 24 * time.Hour
	}
	return 30 * 24 * time.Hour
}

func fail(format string, args ...any) {
	// Emit metrics before exiting: failure paths (retry exhaustion, budget) are exactly when they matter.
	if activeMetrics != nil && !metricsEmitted {
		metricsEmitted = true
		emitMetrics(activeMetrics)
	}
	fmt.Fprintf(os.Stderr, "pfaudit-swap: "+format+"\n", args...)
	os.Exit(1)
}
