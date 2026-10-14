package migrate

import (
	"context"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"

	"productforge/datastore"
)

type fakeRows struct {
	vs []int
	i  int
}

func (r *fakeRows) Next() bool {
	if r.i >= len(r.vs) {
		return false
	}
	r.i++
	return true
}
func (r *fakeRows) Scan(dest ...any) error {
	*(dest[0].(*int64)) = int64(r.vs[r.i-1])
	return nil
}
func (r *fakeRows) Err() error   { return nil }
func (r *fakeRows) Close() error { return nil }

type fakeTx struct {
	applied map[int]bool
	execs   []string
}

func (t *fakeTx) Exec(_ context.Context, sql string, args ...any) (int64, error) {
	t.execs = append(t.execs, sql)
	if len(args) == 2 {
		if v, ok := args[0].(int); ok {
			t.applied[v] = true
		}
	}
	if len(args) == 1 && strings.HasPrefix(strings.ToUpper(strings.TrimSpace(sql)), "DELETE") {
		if v, ok := args[0].(int); ok {
			delete(t.applied, v)
		}
	}
	return 1, nil
}
func (t *fakeTx) Query(_ context.Context, _ string, _ ...any) (datastore.Rows, error) {
	var vs []int
	for v := range t.applied {
		vs = append(vs, v)
	}
	sort.Ints(vs)
	return &fakeRows{vs: vs}, nil
}
func (t *fakeTx) Commit(context.Context) error   { return nil }
func (t *fakeTx) Rollback(context.Context) error { return nil }

type fakeStore struct{ applied map[int]bool }

func (s *fakeStore) Ping(context.Context) error { return nil }
func (s *fakeStore) Capabilities() datastore.Capabilities {
	return datastore.Capabilities{Transactions: true}
}
func (s *fakeStore) WithTx(ctx context.Context, fn func(datastore.Tx) error) error {
	return fn(&fakeTx{applied: s.applied})
}

func TestPlanIsOrderedAndSkipsApplied(t *testing.T) {
	all := []Migration{{Version: 3}, {Version: 1}, {Version: 2}}
	p := Plan(all, map[int]bool{1: true, 3: true})
	if len(p) != 1 || p[0].Version != 2 {
		t.Fatalf("want [2], got %+v", p)
	}
}

func TestUpAppliesOnlyPending(t *testing.T) {
	s := &fakeStore{applied: map[int]bool{1: true}}
	all := []Migration{
		{Version: 1, Name: "one", Up: "SELECT 1"},
		{Version: 2, Name: "two", Up: "CREATE TABLE x(id int)"},
	}
	n, err := Up(context.Background(), s, all)
	if err != nil || n != 1 {
		t.Fatalf("n=%d err=%v", n, err)
	}
	if !s.applied[2] {
		t.Fatal("version 2 should be applied")
	}
	if s.applied[1] != true {
		t.Fatal("version 1 should remain applied")
	}
}

func TestDownRollsBackHighest(t *testing.T) {
	s := &fakeStore{applied: map[int]bool{1: true, 2: true}}
	all := []Migration{
		{Version: 1, Name: "one", Down: "DROP TABLE a"},
		{Version: 2, Name: "two", Down: "DROP TABLE b"},
	}
	if err := Down(context.Background(), s, all); err != nil {
		t.Fatal(err)
	}
	if s.applied[2] {
		t.Fatal("version 2 should be rolled back")
	}
}

func TestLoadDirOrderedAndPaired(t *testing.T) {
	dir := t.TempDir()
	write := func(n, s string) {
		if err := os.WriteFile(filepath.Join(dir, n), []byte(s), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	write("0002_b.up.sql", "SELECT 2")
	write("0002_b.down.sql", "SELECT -2")
	write("0001_a.up.sql", "SELECT 1")
	ms, err := LoadDir(dir)
	if err != nil {
		t.Fatal(err)
	}
	if len(ms) != 2 || ms[0].Version != 1 || ms[1].Version != 2 {
		t.Fatalf("got %+v", ms)
	}
	if ms[1].Down == "" {
		t.Fatal("paired down should be loaded")
	}
	if ms[0].Down != "" {
		t.Fatal("missing down should be empty")
	}
}

func TestShippedMigrationsLoadAndPair(t *testing.T) {
	ms, err := LoadDir(filepath.Join("..", "..", "migrations"))
	if err != nil {
		t.Fatal(err)
	}
	if len(ms) == 0 {
		t.Fatal("expected shipped migrations")
	}
	for _, m := range ms {
		if m.Up == "" || m.Down == "" {
			t.Fatalf("migration %d must have up+down", m.Version)
		}
	}
}
