package store

import (
	"context"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"

	"productforge/datastore"
)

var (
	createTableRE = regexp.MustCompile(`(?i)\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-z_][a-z0-9_]*)`)
	createIndexRE = regexp.MustCompile(`(?i)\bCREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-z_][a-z0-9_]*)`)
)

// ExpectedSchema is the set of tables and indexes declared by the migration files (the single source of truth).
type ExpectedSchema struct {
	Tables  []string
	Indexes []string
}

// ExpectedFromDir extracts declared tables and indexes from *.up.sql files in dir.
func ExpectedFromDir(dir string) (ExpectedSchema, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return ExpectedSchema{}, err
	}
	tables := map[string]bool{}
	indexes := map[string]bool{}
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".up.sql") {
			continue
		}
		b, err := os.ReadFile(filepath.Join(dir, e.Name()))
		if err != nil {
			return ExpectedSchema{}, err
		}
		for _, m := range createTableRE.FindAllStringSubmatch(string(b), -1) {
			tables[strings.ToLower(m[1])] = true
		}
		for _, m := range createIndexRE.FindAllStringSubmatch(string(b), -1) {
			indexes[strings.ToLower(m[1])] = true
		}
	}
	return ExpectedSchema{Tables: sortedKeys(tables), Indexes: sortedKeys(indexes)}, nil
}

// LiveSchema returns the tables and indexes present in the current schema.
func LiveSchema(ctx context.Context, st *PgStore) (tables, indexes []string, err error) {
	tables, err = listNames(ctx, st, "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()")
	if err != nil {
		return nil, nil, err
	}
	indexes, err = listNames(ctx, st, "SELECT indexname FROM pg_indexes WHERE schemaname = current_schema()")
	if err != nil {
		return nil, nil, err
	}
	return tables, indexes, nil
}

func listNames(ctx context.Context, st *PgStore, sql string) ([]string, error) {
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

// Missing returns the expected names not present in live (case-insensitive).
func Missing(expected, live []string) []string {
	have := make(map[string]bool, len(live))
	for _, l := range live {
		have[strings.ToLower(l)] = true
	}
	var out []string
	for _, e := range expected {
		if !have[strings.ToLower(e)] {
			out = append(out, e)
		}
	}
	return out
}

func sortedKeys(m map[string]bool) []string {
	out := make([]string, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}
