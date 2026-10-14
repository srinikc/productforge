// Package migrate is the versioned, reviewed schema-migration framework for Product Forge's PostgreSQL system
// of record (EDP-08 / BI-PF-1300, ADR-0006).
//
// Rules it enforces/supports:
//   - migrations are ordered, versioned, reviewed SQL files; the runner records applied versions in
//     “schema_migrations“ (never applied implicitly on application startup - the caller invokes it as an
//     explicit deploy step);
//   - each migration runs in its own transaction; a failure leaves the DB at the last applied version;
//   - “Down“ rolls back the highest applied migration (expand/contract discipline is the caller's).
//
// It operates through the provider-neutral “datastore.RelationalStore“ (ADR-0006/EDP-07); no provider-specific
// code lives here. Reuse: apply via the deploy step, validate reversibility on a disposable DB in precheck.
package migrate

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"

	"productforge/datastore"
)

// Migration is one versioned schema change. “Version“ is monotonic and unique; “Up“/“Down“ are SQL.
type Migration struct {
	Version int
	Name    string
	Up      string
	Down    string
}

// LoadDir reads migrations from “dir“ using the “NNNN_<slug>.up.sql“ / “NNNN_<slug>.down.sql“
// convention (see migrations/README.md). Files are the source of truth; the version is the leading
// integer. Returns an error on a bad version or a duplicate version.
func LoadDir(dir string) ([]Migration, error) {
	ups, err := filepath.Glob(filepath.Join(dir, "*.up.sql"))
	if err != nil {
		return nil, err
	}
	var out []Migration
	for _, up := range ups {
		base := strings.TrimSuffix(filepath.Base(up), ".up.sql")
		parts := strings.SplitN(base, "_", 2)
		v, err := strconv.Atoi(parts[0])
		if err != nil {
			return nil, fmt.Errorf("migration %s: bad version: %w", base, err)
		}
		name := base
		if len(parts) == 2 {
			name = parts[1]
		}
		upSQL, err := os.ReadFile(up)
		if err != nil {
			return nil, err
		}
		downPath := filepath.Join(dir, base+".down.sql")
		var downSQL []byte
		if _, statErr := os.Stat(downPath); statErr == nil {
			if downSQL, err = os.ReadFile(downPath); err != nil {
				return nil, err
			}
		}
		out = append(out, Migration{Version: v, Name: name, Up: string(upSQL), Down: string(downSQL)})
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Version < out[j].Version })
	for i := 1; i < len(out); i++ {
		if out[i].Version == out[i-1].Version {
			return nil, fmt.Errorf("duplicate migration version %d", out[i].Version)
		}
	}
	return out, nil
}

const _ensureTableSQL = `CREATE TABLE IF NOT EXISTS schema_migrations (
    version    BIGINT PRIMARY KEY,
    name       TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
)`

// EnsureTable creates the migration bookkeeping table (idempotent).
func EnsureTable(ctx context.Context, s datastore.RelationalStore) error {
	return s.WithTx(ctx, func(tx datastore.Tx) error {
		_, err := tx.Exec(ctx, _ensureTableSQL)
		return err
	})
}

// Applied returns the set of applied migration versions.
func Applied(ctx context.Context, s datastore.RelationalStore) (map[int]bool, error) {
	applied := map[int]bool{}
	err := s.WithTx(ctx, func(tx datastore.Tx) error {
		rows, err := tx.Query(ctx, `SELECT version FROM schema_migrations ORDER BY version`)
		if err != nil {
			return err
		}
		defer rows.Close()
		for rows.Next() {
			var v int64
			if err := rows.Scan(&v); err != nil {
				return err
			}
			applied[int(v)] = true
		}
		return rows.Err()
	})
	return applied, err
}

// Plan returns the not-yet-applied migrations in ascending version order (pure; unit-testable).
func Plan(all []Migration, applied map[int]bool) []Migration {
	var pending []Migration
	for _, m := range all {
		if !applied[m.Version] {
			pending = append(pending, m)
		}
	}
	sort.Slice(pending, func(i, j int) bool { return pending[i].Version < pending[j].Version })
	return pending
}

// Up applies all pending migrations (each in its own transaction) and returns how many were applied.
func Up(ctx context.Context, s datastore.RelationalStore, all []Migration) (int, error) {
	if err := EnsureTable(ctx, s); err != nil {
		return 0, err
	}
	applied, err := Applied(ctx, s)
	if err != nil {
		return 0, err
	}
	n := 0
	for _, m := range Plan(all, applied) {
		if err := s.WithTx(ctx, func(tx datastore.Tx) error {
			if _, err := tx.Exec(ctx, m.Up); err != nil {
				return err
			}
			_, err := tx.Exec(ctx, `INSERT INTO schema_migrations(version, name) VALUES ($1, $2)`, m.Version, m.Name)
			return err
		}); err != nil {
			return n, fmt.Errorf("migration %d %s failed: %w", m.Version, m.Name, err)
		}
		n++
	}
	return n, nil
}

// Down rolls back the highest applied migration (its “Down“ SQL + the bookkeeping row).
func Down(ctx context.Context, s datastore.RelationalStore, all []Migration) error {
	applied, err := Applied(ctx, s)
	if err != nil {
		return err
	}
	var target *Migration
	for i := range all {
		if applied[all[i].Version] && (target == nil || all[i].Version > target.Version) {
			target = &all[i]
		}
	}
	if target == nil {
		return nil
	}
	return s.WithTx(ctx, func(tx datastore.Tx) error {
		if _, err := tx.Exec(ctx, target.Down); err != nil {
			return err
		}
		_, err := tx.Exec(ctx, `DELETE FROM schema_migrations WHERE version = $1`, target.Version)
		return err
	})
}
