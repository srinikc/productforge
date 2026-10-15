package store

import (
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
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
