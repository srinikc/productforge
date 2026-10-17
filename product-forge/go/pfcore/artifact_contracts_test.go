package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func writeACDir(t *testing.T) string {
	t.Helper()
	d := t.TempDir()
	idx := map[string]any{
		"contracts": map[string]any{
			"requirements.srs": map[string]any{
				"title": "SRS", "tier": "universal", "applies_to": []string{"*"},
				"source":         map[string]any{"canonical_url": "https://example.com/29148"},
				"license":        map[string]any{"spdx": "NOASSERTION"},
				"format_version": "1.0.0", "status": "standard",
				"sections":          []string{"Functional Requirements", "Non-Functional Requirements"},
				"required_sections": []string{"Functional Requirements"},
				"format":            "markdown",
				"limits":            []any{map[string]any{"id": "FR", "pattern": `FR-\d+`, "max": 3}},
				"budget":            map[string]any{"max_tokens": 5000},
				"size":              map[string]any{"max_lines": 100, "target_lines": 100},
			},
			"api.spec": map[string]any{
				"title": "API", "tier": "universal", "applies_to": []string{"*"},
				"source":         map[string]any{"canonical_url": "https://example.com/openapi"},
				"license":        map[string]any{"spdx": "Apache-2.0"},
				"format_version": "1.0.0", "status": "standard",
				"format":            "json",
				"sections":          []string{"openapi", "paths"},
				"required_sections": []string{"openapi"},
				"schema_required":   []string{"openapi", "paths"},
				"budget":            map[string]any{"max_tokens": 4000},
				"size":              map[string]any{"max_lines": 0, "target_lines": 0},
			},
			"media.video": map[string]any{
				"title": "Video", "tier": "modality", "applies_to": []string{"video"},
				"source":         map[string]any{"canonical_url": "https://example.com/imf"},
				"license":        map[string]any{"spdx": "Apache-2.0"},
				"format_version": "1.0.0", "status": "standard",
				"sections": []string{"Timeline", "Tracks"},
				"size":     map[string]any{"max_lines": 0},
			},
		},
	}
	am := map[string]any{
		"by_agent": map[string]any{"design": []string{"requirements.srs"}, "media-generator": []string{"modality"}},
		"by_stage": map[string]any{"1": []string{"requirements.srs"}},
	}
	b, _ := json.Marshal(idx)
	_ = os.WriteFile(filepath.Join(d, "index.json"), b, 0o600)
	b2, _ := json.Marshal(am)
	_ = os.WriteFile(filepath.Join(d, "agents.json"), b2, 0o600)
	prof := map[string]any{"default": "medium", "profiles": map[string]any{
		"small":  map[string]any{"size_multiplier": 0.5},
		"medium": map[string]any{"size_multiplier": 1.0},
		"large":  map[string]any{"size_multiplier": 2.0},
	}}
	b3, _ := json.Marshal(prof)
	_ = os.WriteFile(filepath.Join(d, "profiles.json"), b3, 0o600)
	return d
}

func TestACKindAndBudgetAndSlider(t *testing.T) {
	d := writeACDir(t)

	k, _ := ACContractKindOp(map[string]any{"idea": "an app to edit video clips and export a timeline"})
	if k["kind"] != "video" {
		t.Fatalf("expected video kind, got %v", k["kind"])
	}
	k2, _ := ACContractKindOp(map[string]any{"idea": "a simple todo list"})
	if k2["kind"] != "text" {
		t.Fatalf("expected text kind, got %v", k2["kind"])
	}

	// budget sums resolved contract budgets
	b, _ := ACContractBudgetOp(map[string]any{"dir": d, "agent": "design", "stage": "1", "kind": "text"})
	if b["total_max_tokens"].(int) != 5000 {
		t.Fatalf("expected 5000 budget, got %v", b["total_max_tokens"])
	}

	// slider: small halves the size budget
	r, _ := ACContractResolveOp(map[string]any{"dir": d, "agent": "design", "kind": "text", "profile": "small"})
	if r["size_multiplier"].(float64) != 0.5 {
		t.Fatalf("expected 0.5 multiplier, got %v", r["size_multiplier"])
	}
	cs := r["contracts"].([]map[string]any)
	sz := cs[0]["size"].(map[string]any)
	if sz["max_lines"].(int) != 50 {
		t.Fatalf("expected scaled max_lines 50, got %v", sz["max_lines"])
	}
}

func TestACFormatAndLimits(t *testing.T) {
	d := writeACDir(t)

	// json contract: invalid JSON -> fail
	v, _ := ACContractValidateOp(map[string]any{"dir": d, "artifact_id": "api.spec", "text": "not json"})
	if v["ok"] != false {
		t.Fatalf("invalid JSON must fail")
	}
	// valid JSON but missing a required key -> fail
	v2, _ := ACContractValidateOp(map[string]any{"dir": d, "artifact_id": "api.spec", "text": `{"openapi":"3.1"}`})
	if v2["ok"] != false {
		t.Fatalf("missing json key must fail: %v", v2["reasons"])
	}
	// valid JSON with required keys + required section -> pass
	v3, _ := ACContractValidateOp(map[string]any{"dir": d, "artifact_id": "api.spec",
		"text": `{"openapi":"3.1","paths":{}}`})
	if v3["ok"] != true {
		t.Fatalf("valid JSON should pass: %v", v3["reasons"])
	}

	// limits: 4 FRs > max 3 -> fail
	v4, _ := ACContractValidateOp(map[string]any{"dir": d, "artifact_id": "requirements.srs",
		"text": "Functional Requirements\nFR-1\nFR-2\nFR-3\nFR-4"})
	if v4["ok"] != false {
		t.Fatalf("FR limit exceeded must fail: %v", v4["reasons"])
	}
	// within limit -> pass
	v5, _ := ACContractValidateOp(map[string]any{"dir": d, "artifact_id": "requirements.srs",
		"text": "Functional Requirements\nFR-1\nFR-2"})
	if v5["ok"] != true {
		t.Fatalf("within-limit FRs should pass: %v", v5["reasons"])
	}
}

func TestACResolveAndValidate(t *testing.T) {
	d := writeACDir(t)
	res, e := ACContractResolveOp(map[string]any{"dir": d, "agent": "design", "stage": "1", "kind": "text"})
	if e != "" {
		t.Fatalf("resolve error: %s", e)
	}
	if res["covered"] != true {
		t.Fatalf("design should be covered")
	}
	if res["count"].(int) != 1 {
		t.Fatalf("expected 1 contract, got %v", res["count"])
	}

	// modality resolves by kind
	mr, _ := ACContractResolveOp(map[string]any{"dir": d, "agent": "media-generator", "kind": "video"})
	if mr["count"].(int) != 1 {
		t.Fatalf("video kind should resolve media.video")
	}

	// validate: missing sections -> fail
	v, _ := ACContractValidateOp(map[string]any{"dir": d, "artifact_id": "requirements.srs", "text": "short"})
	if v["ok"] != false {
		t.Fatalf("expected validation failure for missing sections")
	}

	// validate: all sections present, within size -> pass
	good := "Functional Requirements\nNon-Functional Requirements"
	v2, _ := ACContractValidateOp(map[string]any{"dir": d, "artifact_id": "requirements.srs", "text": good})
	if v2["ok"] != true {
		t.Fatalf("expected validation pass, got %v", v2["reasons"])
	}

	// unknown agent -> not covered
	u, _ := ACContractResolveOp(map[string]any{"dir": d, "agent": "brand-new"})
	if u["covered"] != false {
		t.Fatalf("unknown agent must not be covered")
	}
}

func TestACReconcile(t *testing.T) {
	d := writeACDir(t)

	// run-level (no agent/stage): universal contracts only for kind=text -> 5000+4000 tokens
	r, e := ACContractReconcileOp(map[string]any{"dir": d, "kind": "text",
		"run_budget_seconds": 600.0, "work_estimate_seconds": 300.0})
	if e != "" {
		t.Fatalf("reconcile error: %s", e)
	}
	ab := r["artifact_budget"].(map[string]any)
	if ab["max_tokens"].(int) != 9000 {
		t.Fatalf("expected 9000 run-level token budget, got %v", ab["max_tokens"])
	}
	if r["verdict"] != "under" {
		t.Fatalf("expected under, got %v", r["verdict"])
	}
	if r["delta_seconds"].(float64) != 300.0 {
		t.Fatalf("expected +300s spare, got %v", r["delta_seconds"])
	}

	// over budget -> verdict over + negative delta
	r2, _ := ACContractReconcileOp(map[string]any{"dir": d, "kind": "text",
		"run_budget_seconds": 60.0, "work_estimate_seconds": 600.0})
	if r2["verdict"] != "over" || r2["delta_seconds"].(float64) >= 0 {
		t.Fatalf("expected over with negative delta, got %v / %v", r2["verdict"], r2["delta_seconds"])
	}

	// within band (>=90% but not over)
	r3, _ := ACContractReconcileOp(map[string]any{"dir": d, "kind": "text",
		"run_budget_seconds": 100.0, "work_estimate_seconds": 95.0})
	if r3["verdict"] != "within" {
		t.Fatalf("expected within, got %v", r3["verdict"])
	}

	// 0 budget = unlimited (never gates)
	r4, _ := ACContractReconcileOp(map[string]any{"dir": d, "kind": "text",
		"run_budget_seconds": 0.0, "work_estimate_seconds": 9999.0})
	if r4["verdict"] != "unlimited" {
		t.Fatalf("expected unlimited, got %v", r4["verdict"])
	}

	// explicit agent set reconciles that agent's contracts only
	r5, _ := ACContractReconcileOp(map[string]any{"dir": d, "agent": "design", "kind": "text",
		"run_budget_seconds": 100.0, "work_estimate_seconds": 10.0})
	ab5 := r5["artifact_budget"].(map[string]any)
	if ab5["max_tokens"].(int) != 5000 {
		t.Fatalf("expected 5000 for design, got %v", ab5["max_tokens"])
	}
}

func TestACOutline(t *testing.T) {
	d := writeACDir(t)

	// required section present, projected within budget -> under
	u, e := ACContractOutlineOp(map[string]any{"dir": d, "agent": "design", "kind": "text",
		"lines_per_item": 3, "outline": []any{map[string]any{"section": "Functional Requirements", "count": 10}}})
	if e != "" {
		t.Fatalf("outline error: %s", e)
	}
	if u["verdict"] != "under" || u["over"] != false {
		t.Fatalf("expected under, got %v/%v", u["verdict"], u["over"])
	}
	if u["budget_lines"].(int) != 100 {
		t.Fatalf("expected 100 budget lines, got %v", u["budget_lines"])
	}

	// over budget -> compressed outline fits (min 1 per section)
	o, _ := ACContractOutlineOp(map[string]any{"dir": d, "agent": "design", "kind": "text",
		"lines_per_item": 3, "outline": []any{map[string]any{"section": "Functional Requirements", "count": 50}}})
	if o["verdict"] != "over" || o["over"] != true {
		t.Fatalf("expected over, got %v", o["verdict"])
	}
	if o["compressed_lines"].(int) > o["budget_lines"].(int) {
		t.Fatalf("compressed %v should fit budget %v", o["compressed_lines"], o["budget_lines"])
	}
	comp := o["compressed"].([]map[string]any)
	if comp[0]["count"].(int) < 1 {
		t.Fatalf("compressed count must be >= 1")
	}

	// missing required section -> reported
	m, _ := ACContractOutlineOp(map[string]any{"dir": d, "agent": "design", "kind": "text",
		"outline": []any{map[string]any{"section": "Something Else", "count": 1}}})
	if len(m["missing_sections"].([]string)) == 0 {
		t.Fatalf("expected a missing required section")
	}
}

func TestACDryCheck(t *testing.T) {
	// F-2 restates the product-wide section -> violation; F-1 (reference only) is clean
	v, e := ACContractDryCheckOp(map[string]any{
		"product_wide": []any{"non_functional_requirements"},
		"fragments": []any{
			map[string]any{"id": "F-1", "text": "## F-1\nNFRs referenced (see NFR-1..15)"},
			map[string]any{"id": "F-2", "text": "## F-2\n## Non-Functional Requirements\nNFR-1 latency"},
		}})
	if e != "" {
		t.Fatalf("dry_check error: %s", e)
	}
	if v["ok"] != false {
		t.Fatalf("expected a violation")
	}
	vv := v["violations"].([]map[string]any)
	if len(vv) != 1 || vv[0]["id"] != "F-2" {
		t.Fatalf("expected only F-2 flagged, got %v", vv)
	}
	// clean
	c, _ := ACContractDryCheckOp(map[string]any{
		"product_wide": []any{"non_functional_requirements"},
		"fragments":    []any{map[string]any{"id": "F-1", "text": "## F-1\nNFRs referenced"}}})
	if c["ok"] != true {
		t.Fatalf("clean fragments should pass: %v", c["violations"])
	}
}

func TestACCoverage(t *testing.T) {
	d := writeACDir(t)
	cov, _ := ACContractCoverageOp(map[string]any{"dir": d, "agents": []any{"design", "ghost"}, "stages": []any{"1"}})
	if cov["ok"] != false {
		t.Fatalf("coverage should fail with a missing agent")
	}
	ma := cov["missing_agents"].([]string)
	if len(ma) != 1 || ma[0] != "ghost" {
		t.Fatalf("expected ghost missing, got %v", ma)
	}
}
