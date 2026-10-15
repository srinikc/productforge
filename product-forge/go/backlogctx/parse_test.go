package backlogctx

import "testing"

const doc = `# Plan

## BI-PF-1309 - EDP-17 canonical schema
objective: canonical PostgreSQL schema
affected_files:
- migrations/0002_core_schema.up.sql
- go/store/pg.go
risks: migration drift, data loss
type: feature

## BI-PF-1301 - EDP-09
objective: tenant RLS
`

func TestParse(t *testing.T) {
	s := Parse(doc)
	if len(s) != 2 {
		t.Fatalf("want 2 sections, got %d", len(s))
	}
	a := s["BI-PF-1309"]
	if a["objective"] != "canonical PostgreSQL schema" {
		t.Errorf("objective = %v", a["objective"])
	}
	files, _ := a["affected_files"].([]string)
	if len(files) != 2 || files[0] != "migrations/0002_core_schema.up.sql" {
		t.Errorf("affected_files = %v", a["affected_files"])
	}
	risks, _ := a["risks"].([]string)
	if len(risks) != 2 {
		t.Errorf("risks = %v", a["risks"])
	}
	if a["type"] != "feature" {
		t.Errorf("type = %v", a["type"])
	}
	if a["title"] != "EDP-17 canonical schema" {
		t.Errorf("title = %v", a["title"])
	}
}

func TestChangesFillMissing(t *testing.T) {
	cur := map[string]any{"objective": "here", "owner": ""}
	des := map[string]any{"objective": "new", "owner": "alice", "approach": "x"}
	c := Changes(cur, des, false)
	if len(c) != 2 || c["owner"] != "alice" || c["approach"] != "x" {
		t.Errorf("changes = %v", c)
	}
	if _, ok := c["objective"]; ok {
		t.Errorf("objective should be untouched")
	}
}

func TestChangesOverwrite(t *testing.T) {
	c := Changes(map[string]any{"objective": "old"}, map[string]any{"objective": "new"}, true)
	if c["objective"] != "new" {
		t.Errorf("overwrite failed: %v", c)
	}
}

func TestRoute(t *testing.T) {
	ctx, edit, deps := Route(map[string]any{"objective": "o", "type": "bug", "blocked_by": []string{"BI-PF-1293"}})
	if ctx["objective"] != "o" || edit["type"] != "bug" || len(deps) != 1 {
		t.Errorf("route mismatch: %v %v %v", ctx, edit, deps)
	}
}
