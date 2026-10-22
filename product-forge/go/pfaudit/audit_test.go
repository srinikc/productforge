package pfaudit

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestArchiveKeyLayout(t *testing.T) {
	if got := ArchiveKey("audit_202601"); got != "audit/cold/audit_202601/part-000.ndjson" {
		t.Fatalf("ArchiveKey = %q", got)
	}
}

func TestMonthBounds(t *testing.T) {
	from, to := monthBounds("audit_202412")
	if from != "2024-12-01" || to != "2025-01-01" {
		t.Fatalf("monthBounds = %q..%q", from, to)
	}
}

func TestValidTable(t *testing.T) {
	for _, ok := range []string{"audit", "audit_202601", "audit_late_202401"} {
		if !validTable(ok) {
			t.Fatalf("validTable(%q) = false", ok)
		}
	}
	for _, bad := range []string{"", "audit; DROP TABLE x", "Audit", "audit-2026"} {
		if validTable(bad) {
			t.Fatalf("validTable(%q) = true", bad)
		}
	}
}

func TestSHA256(t *testing.T) {
	h, n, err := SHA256(bytes.NewReader([]byte("abc")))
	if err != nil {
		t.Fatal(err)
	}
	if n != 3 || h != "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad" {
		t.Fatalf("sha256 = %s (%d)", h, n)
	}
}

// TestLockConstantsMatchSQL guards the AC that Go and SQL advisory-lock namespaces cannot drift.
func TestLockConstantsMatchSQL(t *testing.T) {
	b, err := os.ReadFile(filepath.Join("..", "..", "migrations", "0014_audit_partitioning.up.sql"))
	if err != nil {
		t.Fatal(err)
	}
	sql := string(b)
	for _, k := range []string{LockProvision, LockSwap, LockRetention} {
		if !strings.Contains(sql, "'"+k+"'") {
			t.Fatalf("migration does not contain advisory namespace %q", k)
		}
	}
}

func TestStateNames(t *testing.T) {
	want := map[State]string{
		StateNotPrepared: "not_prepared", StatePrestage: "prestage",
		StateSwapped: "swapped", StateDone: "done",
	}
	for s, w := range want {
		if string(s) != w {
			t.Fatalf("%v != %s", s, w)
		}
	}
}
