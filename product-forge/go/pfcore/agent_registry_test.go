package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

// writeAgentDir builds a minimal config dir with artifact-contracts/ + agent-registry/.
func writeAgentDir(t *testing.T) string {
	t.Helper()
	d := t.TempDir()
	ac := filepath.Join(d, "artifact-contracts")
	if err := os.MkdirAll(ac, 0o755); err != nil {
		t.Fatal(err)
	}
	idx := map[string]any{"contracts": map[string]any{
		"requirements.srs": map[string]any{
			"title": "SRS", "tier": "universal", "applies_to": []string{"*"},
			"source": map[string]any{"canonical_url": "https://x"}, "license": map[string]any{"spdx": "x"},
			"format_version": "1.0.0", "status": "standard", "format": "markdown",
			"sections": []string{"A"}, "required_sections": []string{"A"},
			"budget": map[string]any{"max_tokens": 1000}, "size": map[string]any{"max_lines": 10},
		},
	}}
	b, _ := json.Marshal(idx)
	_ = os.WriteFile(filepath.Join(ac, "index.json"), b, 0o600)

	ar := map[string]any{"agents": map[string]any{
		"design": map[string]any{"title": "Design", "outputs": []string{"requirements.srs"}},
	}}
	b2, _ := json.Marshal(ar)
	_ = os.MkdirAll(filepath.Join(d, "agent-registry"), 0o755)
	_ = os.WriteFile(filepath.Join(d, "agent-registry", "index.json"), b2, 0o600)
	return ac
}

func TestAgentRegistryResolveCoverage(t *testing.T) {
	ac := writeAgentDir(t)

	r, e := ARAgentRegistryOp(map[string]any{"dir": ac})
	if e != "" {
		t.Fatal(e)
	}
	if r["count"].(int) != 1 {
		t.Fatalf("count=%v", r["count"])
	}

	rr, _ := ARAgentResolveOp(map[string]any{"dir": ac, "agent": "design"})
	if rr["covered"] != true {
		t.Fatal("design should be covered")
	}

	// coverage: a missing agent fails
	cv, _ := ARAgentCoverageOp(map[string]any{"dir": ac, "agents": []any{"design", "ghost"}})
	if cv["ok"] != false {
		t.Fatalf("coverage should fail on a missing agent")
	}

	// the artifact engine resolves the agent's outputs FROM the agent registry
	res, _ := ACContractResolveOp(map[string]any{"dir": ac, "agent": "design"})
	if res["count"].(int) != 1 {
		t.Fatalf("expected 1 contract from agent registry, got %v", res["count"])
	}
	cs := res["contracts"].([]map[string]any)
	if cs[0]["artifact_id"].(string) != "requirements.srs" {
		t.Fatalf("expected requirements.srs, got %v", cs[0]["artifact_id"])
	}
}
