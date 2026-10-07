// Stage 3b (BI-PF-0414): SQL dialect support for the coordination store.
//
// The store is backend-pluggable: SQLite (default, single-node) or PostgreSQL
// (multi-node - several coordinator processes sharing one store). The two
// dialects differ in three mechanical ways: the driver name, `?` vs `$n`
// placeholders, and the float column type. Everything else (UPSERT + RETURNING,
// which the atomic claim relies on) is shared.
package store

import (
	"fmt"
	"strings"
)

// dialect is a supported store backend.
type dialect string

const (
	dialectSQLite   dialect = "sqlite"
	dialectPostgres dialect = "postgres"
)

// normalizeDialect maps config/env spellings to a dialect ("" = sqlite).
func normalizeDialect(s string) (dialect, error) {
	switch strings.ToLower(strings.TrimSpace(s)) {
	case "", "sqlite", "sqlite3":
		return dialectSQLite, nil
	case "postgres", "postgresql", "pg", "pgx":
		return dialectPostgres, nil
	default:
		return "", fmt.Errorf("unknown store driver %q (want sqlite|postgres)", s)
	}
}

// driverName is the database/sql driver to open for the dialect.
func driverName(d dialect) string {
	if d == dialectPostgres {
		return "pgx" // github.com/jackc/pgx/v5/stdlib
	}
	return "sqlite" // modernc.org/sqlite (pure Go)
}

// rebind converts `?` placeholders to `$1..$n` for PostgreSQL; SQLite keeps `?`.
func rebind(q string, d dialect) string {
	if d != dialectPostgres {
		return q
	}
	var b strings.Builder
	n := 0
	for _, r := range q {
		if r == '?' {
			n++
			fmt.Fprintf(&b, "$%d", n)
			continue
		}
		b.WriteRune(r)
	}
	return b.String()
}

const sqliteSchema = `
CREATE TABLE IF NOT EXISTS workers (
  worker_id TEXT PRIMARY KEY,
  runtime TEXT,
  capabilities TEXT,
  role TEXT,
  status TEXT,
  registered_at REAL,
  last_heartbeat REAL,
  current_assignment TEXT
);
CREATE TABLE IF NOT EXISTS leases (
  item_id TEXT PRIMARY KEY,
  worker_id TEXT,
  runtime TEXT,
  assignment_id TEXT,
  expires_at REAL,
  created_at REAL
);`

// PostgreSQL schema: same tables; `double precision` keeps float64 precision
// (PG REAL would be float4).
const postgresSchema = `
CREATE TABLE IF NOT EXISTS workers (
  worker_id TEXT PRIMARY KEY,
  runtime TEXT,
  capabilities TEXT,
  role TEXT,
  status TEXT,
  registered_at DOUBLE PRECISION,
  last_heartbeat DOUBLE PRECISION,
  current_assignment TEXT
);
CREATE TABLE IF NOT EXISTS leases (
  item_id TEXT PRIMARY KEY,
  worker_id TEXT,
  runtime TEXT,
  assignment_id TEXT,
  expires_at DOUBLE PRECISION,
  created_at DOUBLE PRECISION
);`

// schemaFor returns the idempotent DDL for the dialect.
func schemaFor(d dialect) string {
	if d == dialectPostgres {
		return postgresSchema
	}
	return sqliteSchema
}
