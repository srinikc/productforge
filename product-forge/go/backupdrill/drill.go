package backupdrill

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
)

// DrillReport is the outcome of a restore rehearsal.
type DrillReport struct {
	Scope       string        `json:"scope"`
	Scratch     string        `json:"scratch"`
	Tables      int           `json:"tables"`
	Rows        int64         `json:"rows"`
	Mismatches  []string      `json:"mismatches"`
	Elapsed     time.Duration `json:"elapsed"`
	RTOSeconds  float64       `json:"rto_seconds"`
	RTOOK       bool          `json:"rto_ok"`
	IsolationOK bool          `json:"isolation_ok"`
}

func dsnEnv(dsn string) (string, []string) {
	pw := ""
	safe := dsn
	if i := strings.Index(dsn, "://"); i >= 0 {
		if at := strings.Index(dsn[i+3:], "@"); at >= 0 {
			head := dsn[i+3 : i+3+at]
			if c := strings.LastIndex(head, ":"); c >= 0 {
				pw = head[c+1:]
				safe = dsn[:i+3] + head[:c] + dsn[i+3+at:]
			}
		}
	}
	env := os.Environ()
	if pw != "" {
		env = append(env, "PGPASSWORD="+pw)
	}
	return safe, env
}

func withDB(dsn, db string) string {
	base := dsn
	if i := strings.Index(base, "?"); i >= 0 {
		base = base[:i]
	}
	slash := strings.LastIndex(base, "/")
	return base[:slash+1] + db
}

func run(ctx context.Context, stdin []byte, name string, args ...string) error {
	cmd := exec.CommandContext(ctx, name, args...)
	if stdin != nil {
		cmd.Stdin = strings.NewReader(string(stdin))
	}
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("%s: %v: %s", name, err, strings.TrimSpace(string(out)))
	}
	return nil
}

// GuardScratch refuses anything that does not look like a disposable drill database.
func GuardScratch(name string) error {
	if !strings.HasPrefix(name, "pf_scratch_") {
		return fmt.Errorf("backupdrill: scratch database %q must start with pf_scratch_", name)
	}
	if os.Getenv("PF_ALLOW_DESTRUCTIVE_DRILL") != "1" {
		return fmt.Errorf("backupdrill: set PF_ALLOW_DESTRUCTIVE_DRILL=1 to run a destructive drill")
	}
	return nil
}

// FullRestore dumps the database into a scratch DB, verifies table counts, and drops the scratch.
func FullRestore(ctx context.Context, dsn, scratch string, rtoBudget time.Duration) (DrillReport, error) {
	if err := GuardScratch(scratch); err != nil {
		return DrillReport{}, err
	}
	start := time.Now()
	rep := DrillReport{Scope: "full", Scratch: scratch, RTOOK: true, IsolationOK: true}
	safe, env := dsnEnv(dsn)
	admin := withDB(safe, "postgres")
	defer func() {
		_ = run(ctx, nil, "psql", admin, "-v", "ON_ERROR_STOP=1", "-c", "DROP DATABASE IF EXISTS "+scratch)
	}()
	if err := run(ctx, nil, "psql", admin, "-v", "ON_ERROR_STOP=1", "-c", "DROP DATABASE IF EXISTS "+scratch); err != nil {
		return rep, err
	}
	if err := run(ctx, nil, "psql", admin, "-v", "ON_ERROR_STOP=1", "-c", "CREATE DATABASE "+scratch); err != nil {
		return rep, err
	}
	dump, err := exec.CommandContext(ctx, "pg_dump", "-Fc", safe).Output()
	if err != nil {
		return rep, fmt.Errorf("pg_dump: %w", err)
	}
	restore := exec.CommandContext(ctx, "pg_restore", "--no-owner", "--no-privileges", "-d", withDB(safe, scratch))
	restore.Stdin = strings.NewReader(string(dump))
	restore.Env = env
	if out, err := restore.CombinedOutput(); err != nil {
		return rep, fmt.Errorf("pg_restore: %v: %s", err, strings.TrimSpace(string(out)))
	}
	src, err := pgx.Connect(ctx, dsn)
	if err != nil {
		return rep, err
	}
	defer src.Close(ctx)
	dst, err := pgx.Connect(ctx, withDB(dsn, scratch))
	if err != nil {
		return rep, err
	}
	defer dst.Close(ctx)
	tables, err := listTables(ctx, src)
	if err != nil {
		return rep, err
	}
	rep.Tables = len(tables)
	for _, t := range tables {
		var a, b int64
		if err := src.QueryRow(ctx, "SELECT count(*) FROM "+pgIdent(t)).Scan(&a); err != nil {
			return rep, err
		}
		if err := dst.QueryRow(ctx, "SELECT count(*) FROM "+pgIdent(t)).Scan(&b); err != nil {
			rep.Mismatches = append(rep.Mismatches, t+": missing in scratch")
			continue
		}
		rep.Rows += a
		if a != b {
			rep.Mismatches = append(rep.Mismatches, fmt.Sprintf("%s: %d != %d", t, a, b))
		}
	}
	rep.Elapsed = time.Since(start)
	rep.RTOSeconds = rep.Elapsed.Seconds()
	if rtoBudget > 0 && rep.Elapsed > rtoBudget {
		rep.RTOOK = false
	}
	if len(rep.Mismatches) > 0 {
		return rep, fmt.Errorf("backupdrill: %d table mismatch(es)", len(rep.Mismatches))
	}
	return rep, nil
}

func listTables(ctx context.Context, conn *pgx.Conn) ([]string, error) {
	rows, err := conn.Query(ctx, `SELECT table_name FROM information_schema.tables
		WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []string
	for rows.Next() {
		var t string
		if err := rows.Scan(&t); err != nil {
			return nil, err
		}
		out = append(out, t)
	}
	return out, rows.Err()
}

func pgIdent(s string) string { return `"` + strings.ReplaceAll(s, `"`, `""`) + `"` }

// TenantRestore restores only one tenant's rows into a scratch DB and proves isolation.
func TenantRestore(ctx context.Context, dsn, tenant, scratch string) (DrillReport, error) {
	if err := GuardScratch(scratch); err != nil {
		return DrillReport{}, err
	}
	start := time.Now()
	rep := DrillReport{Scope: "tenant", Scratch: scratch, RTOOK: true}
	safe, _ := dsnEnv(dsn)
	admin := withDB(safe, "postgres")
	if err := run(ctx, nil, "psql", admin, "-v", "ON_ERROR_STOP=1", "-c", "DROP DATABASE IF EXISTS "+scratch); err != nil {
		return rep, err
	}
	if err := run(ctx, nil, "psql", admin, "-v", "ON_ERROR_STOP=1", "-c", "CREATE DATABASE "+scratch); err != nil {
		return rep, err
	}
	schema, err := exec.CommandContext(ctx, "pg_dump", "--schema-only", safe).Output()
	if err != nil {
		return rep, fmt.Errorf("pg_dump --schema-only: %w", err)
	}
	if err := run(ctx, schema, "psql", withDB(safe, scratch), "-v", "ON_ERROR_STOP=1"); err != nil {
		return rep, err
	}
	src, err := pgx.Connect(ctx, dsn)
	if err != nil {
		return rep, err
	}
	defer src.Close(ctx)
	dst, err := pgx.Connect(ctx, withDB(dsn, scratch))
	if err != nil {
		return rep, err
	}
	defer dst.Close(ctx)
	tables, err := listTenantTables(ctx, src)
	if err != nil {
		return rep, err
	}
	rep.Tables = len(tables)
	for _, t := range tables {
		// pg_dump cannot filter rows; stream a filtered COPY through psql for the tenant slice.
		source := fmt.Sprintf(`COPY (SELECT * FROM %s WHERE tenant_id = '%s') TO STDOUT`,
			pgIdent(t), strings.ReplaceAll(tenant, "'", "''"))
		load := fmt.Sprintf(`\copy %s FROM STDIN`, pgIdent(t))
		out, err := exec.CommandContext(ctx, "psql", safe, "-v", "ON_ERROR_STOP=1", "-c", source).Output()
		if err != nil {
			return rep, fmt.Errorf("export %s: %w", t, err)
		}
		if err := run(ctx, out, "psql", withDB(safe, scratch), "-v", "ON_ERROR_STOP=1", "-c", load); err != nil {
			return rep, fmt.Errorf("load %s: %w", t, err)
		}
	}
	for _, t := range tables {
		var srcN, dstN, cross int64
		q := "SELECT count(*) FROM " + pgIdent(t) + " WHERE tenant_id = $1"
		if err := src.QueryRow(ctx, q, tenant).Scan(&srcN); err != nil {
			return rep, err
		}
		if err := dst.QueryRow(ctx, q, tenant).Scan(&dstN); err != nil {
			return rep, err
		}
		if err := dst.QueryRow(ctx, "SELECT count(*) FROM "+pgIdent(t)+" WHERE tenant_id <> $1", tenant).Scan(&cross); err != nil {
			return rep, err
		}
		rep.Rows += srcN
		if srcN != dstN {
			rep.Mismatches = append(rep.Mismatches, fmt.Sprintf("%s: %d != %d", t, srcN, dstN))
		}
		if cross != 0 {
			rep.Mismatches = append(rep.Mismatches, fmt.Sprintf("%s: %d cross-tenant row(s)", t, cross))
		}
	}
	rep.IsolationOK = len(rep.Mismatches) == 0
	rep.Elapsed = time.Since(start)
	rep.RTOSeconds = rep.Elapsed.Seconds()
	return rep, nil
}

func listTenantTables(ctx context.Context, conn *pgx.Conn) ([]string, error) {
	rows, err := conn.Query(ctx, `SELECT c.table_name FROM information_schema.columns c
		JOIN information_schema.tables t ON t.table_schema=c.table_schema AND t.table_name=c.table_name
		WHERE c.table_schema='public' AND c.column_name='tenant_id' AND t.table_type='BASE TABLE'
		ORDER BY c.table_name`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []string
	for rows.Next() {
		var t string
		if err := rows.Scan(&t); err != nil {
			return nil, err
		}
		out = append(out, t)
	}
	return out, rows.Err()
}
