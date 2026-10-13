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
				"source":        map[string]any{"canonical_url": "https://example.com/29148"},
				"license":       map[string]any{"spdx": "NOASSERTION"},
				"format_version": "1.0.0", "status": "standard",
				"sections": []string{"Functional Requirements", "Non-Functional Requirements"},
				"size":     map[string]any{"max_lines": 5},
			},
			"media.video": map[string]any{
				"title": "Video", "tier": "modality", "applies_to": []string{"video"},
				"source":        map[string]any{"canonical_url": "https://example.com/imf"},
				"license":       map[string]any{"spdx": "Apache-2.0"},
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
	return d
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
