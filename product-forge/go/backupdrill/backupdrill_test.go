package backupdrill

import (
	"testing"

	"productforge/datastore"
)

func TestPITRProblems(t *testing.T) {
	if len(pitrProblems("replica", "on", "archive_command")) != 0 {
		t.Fatal("valid settings flagged")
	}
	if len(pitrProblems("minimal", "off", "")) != 3 {
		t.Fatal("invalid settings not flagged")
	}
}

func TestRegionGuard(t *testing.T) {
	p := RegionPolicy{Cells: map[string]string{"t1": "eu"}, Default: "us"}
	if err := GuardRestore("t1", "EU", p, false, ""); err != nil {
		t.Fatalf("same region rejected: %v", err)
	}
	if err := GuardRestore("t1", "us", p, false, ""); err == nil {
		t.Fatal("cross-region allowed without override")
	}
	if err := GuardRestore("t1", "us", p, true, "drill"); err != nil {
		t.Fatalf("explicit cross-region rejected: %v", err)
	}
	if err := GuardRestore("t2", "us", p, false, ""); err != nil {
		t.Fatalf("default region rejected: %v", err)
	}
}

func TestClassify(t *testing.T) {
	rows := map[string]ObjectRow{"a": {Table: "artifacts", Ref: "a"}, "b": {Table: "artifacts", Ref: "b"}}
	objs := []datastore.ObjectInfo{{Key: "a"}, {Key: "c"}}
	d := Classify(rows, objs, "")
	if len(d.Missing) != 1 || d.Missing[0] != "b" || len(d.Orphaned) != 1 || d.Orphaned[0] != "c" {
		t.Fatalf("drift = %+v", d)
	}
}
