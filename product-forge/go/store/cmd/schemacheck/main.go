// Command schemacheck verifies the live PostgreSQL schema contains the tables and indexes declared by
// migrations/*.up.sql (the single source of truth). Exit 1 when a declared table/index is missing.
//
// EDP-17 / BI-PF-1309. Deploy-time admin check; also reachable via the migrations-admin API (BI-PF-1402).
package main

import (
	"context"
	"fmt"
	"os"
	"path/filepath"

	"productforge/datastore"
	"productforge/store"
)

func main() {
	dsn := os.Getenv("PF_DB_DSN")
	if dsn == "" {
		fmt.Fprintln(os.Stderr, "PF_DB_DSN is not set")
		os.Exit(2)
	}
	dir := ""
	if len(os.Args) > 1 {
		dir = os.Args[1]
	}
	if dir == "" {
		d, err := findMigrations()
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
		dir = d
	}
	expected, err := store.ExpectedFromDir(dir)
	if err != nil {
		fmt.Fprintln(os.Stderr, "read migrations:", err)
		os.Exit(1)
	}

	ctx := context.Background()
	st, err := store.Open(ctx, dsn)
	if err != nil {
		fmt.Fprintln(os.Stderr, "open:", err)
		os.Exit(1)
	}
	defer st.Close()

	tables, err := queryNames(ctx, st, "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()")
	if err != nil {
		fmt.Fprintln(os.Stderr, "query tables:", err)
		os.Exit(1)
	}
	indexes, err := queryNames(ctx, st, "SELECT indexname FROM pg_indexes WHERE schemaname = current_schema()")
	if err != nil {
		fmt.Fprintln(os.Stderr, "query indexes:", err)
		os.Exit(1)
	}

	missingTables := store.Missing(expected.Tables, tables)
	missingIndexes := store.Missing(expected.Indexes, indexes)
	fmt.Printf("schema-check: expected %d tables / %d indexes; live %d / %d\n",
		len(expected.Tables), len(expected.Indexes), len(tables), len(indexes))
	if len(missingTables) > 0 || len(missingIndexes) > 0 {
		fmt.Printf("  MISSING tables:  %v\n", missingTables)
		fmt.Printf("  MISSING indexes: %v\n", missingIndexes)
		fmt.Println("schema-check: FAIL")
		os.Exit(1)
	}
	fmt.Println("schema-check: OK (all declared tables/indexes present)")
}

func queryNames(ctx context.Context, st *store.PgStore, sql string) ([]string, error) {
	var out []string
	err := st.WithTx(ctx, func(tx datastore.Tx) error {
		rows, err := tx.Query(ctx, sql)
		if err != nil {
			return err
		}
		defer rows.Close()
		for rows.Next() {
			var name string
			if err := rows.Scan(&name); err != nil {
				return err
			}
			out = append(out, name)
		}
		return rows.Err()
	})
	return out, err
}

func findMigrations() (string, error) {
	d, err := os.Getwd()
	if err != nil {
		return "", err
	}
	for {
		cand := filepath.Join(d, "migrations")
		if st, e := os.Stat(cand); e == nil && st.IsDir() {
			return cand, nil
		}
		parent := filepath.Dir(d)
		if parent == d {
			return "", fmt.Errorf("could not locate a 'migrations' directory; pass it as an argument")
		}
		d = parent
	}
}
