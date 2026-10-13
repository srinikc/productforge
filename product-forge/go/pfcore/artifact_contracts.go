// artifact_contracts.go — the Artifact Contract Registry ENGINE (Go-first for new work,
// ADR BI-PF-0388 / BI-PF-0387). Owns the logic that gives each agent/stage the GIVEN
// artifact format/semantics (sections + counts + size budget) and validates output against
// it. Data (index.json + agents.json) stays in config/artifact-contracts/ (tooling); this
// engine is invoked from the PF runtime through the pfcore-host wire seam (core/go_host.py).
// Stdlib only so `go build` always succeeds.
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// ACContract mirrors one entry in config/artifact-contracts/index.json.
type ACContract struct {
	Title           string         `json:"title"`
	Tier            string         `json:"tier"`
	AppliesTo       []string       `json:"applies_to"`
	Standard        string         `json:"standard"`
	StandardVersion string         `json:"standard_version"`
	Source          map[string]any `json:"source"`
	License         map[string]any `json:"license"`
	FormatVersion   string         `json:"format_version"`
	Status          string         `json:"status"`
	Sections        []string       `json:"sections"`
	Counts          map[string]any `json:"counts"`
	Size            map[string]any `json:"size"`
	Refresh         map[string]any `json:"refresh"`
}

type acIndex struct {
	Contracts map[string]ACContract `json:"contracts"`
}

type acMap struct {
	ByAgent map[string][]string `json:"by_agent"`
	ByStage map[string][]string `json:"by_stage"`
}

// acOp adapts an artifact-contract op to the standard seam wire response.
func acOp(req WireRequest, fn func(map[string]any) (map[string]any, string)) WireResponse {
	res, e := fn(req.Payload)
	if e != "" {
		return response(req, false, "error", nil, e)
	}
	return response(req, true, "ok", res, "")
}

func acLoad(dir string) (map[string]ACContract, acMap, string) {
	idx := acIndex{}
	raw, err := os.ReadFile(filepath.Join(dir, "index.json"))
	if err != nil {
		return nil, acMap{}, "read index.json: " + err.Error()
	}
	if err := json.Unmarshal(raw, &idx); err != nil {
		return nil, acMap{}, "parse index.json: " + err.Error()
	}
	am := acMap{ByAgent: map[string][]string{}, ByStage: map[string][]string{}}
	if raw2, err2 := os.ReadFile(filepath.Join(dir, "agents.json")); err2 == nil {
		_ = json.Unmarshal(raw2, &am)
		if am.ByAgent == nil {
			am.ByAgent = map[string][]string{}
		}
		if am.ByStage == nil {
			am.ByStage = map[string][]string{}
		}
	}
	return idx.Contracts, am, ""
}

func acToInt(v any) (int, bool) {
	switch n := v.(type) {
	case float64:
		return int(n), true
	case int:
		return n, true
	case json.Number:
		i, err := n.Int64()
		return int(i), err == nil
	}
	return 0, false
}

func acStrings(v any) []string {
	out := []string{}
	if arr, ok := v.([]any); ok {
		for _, x := range arr {
			if s, ok2 := x.(string); ok2 {
				out = append(out, s)
			}
		}
	}
	return out
}

func acModalityFor(reg map[string]ACContract, kind string) []string {
	k := strings.ToLower(strings.TrimSpace(kind))
	out := []string{}
	for id, c := range reg {
		if strings.ToLower(c.Tier) != "modality" {
			continue
		}
		for _, a := range c.AppliesTo {
			if a == "*" || strings.ToLower(a) == k {
				out = append(out, id)
				break
			}
		}
	}
	sort.Strings(out)
	return out
}

func acContractsFor(reg map[string]ACContract, am acMap, agent, stage, kind string) []string {
	var ids []string
	if agent != "" {
		ids = am.ByAgent[agent]
	}
	if len(ids) == 0 && stage != "" {
		ids = am.ByStage[stage]
	}
	set := map[string]bool{}
	for _, aid := range ids {
		switch aid {
		case "none":
			continue
		case "modality":
			for _, m := range acModalityFor(reg, kind) {
				set[m] = true
			}
		default:
			if _, ok := reg[aid]; ok {
				set[aid] = true
			}
		}
	}
	out := make([]string, 0, len(set))
	for k := range set {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}

// ACContractRegistryOp returns the full registry (ids + contracts).
func ACContractRegistryOp(payload map[string]any) (map[string]any, string) {
	dir, _ := payload["dir"].(string)
	reg, _, e := acLoad(dir)
	if e != "" {
		return nil, e
	}
	contracts := map[string]any{}
	ids := []string{}
	for id, c := range reg {
		contracts[id] = c
		ids = append(ids, id)
	}
	sort.Strings(ids)
	return map[string]any{"ids": ids, "contracts": contracts, "count": len(ids)}, ""
}

// ACContractResolveOp resolves the artifact contract(s) an agent/stage must produce.
func ACContractResolveOp(payload map[string]any) (map[string]any, string) {
	dir, _ := payload["dir"].(string)
	agent, _ := payload["agent"].(string)
	stage, _ := payload["stage"].(string)
	kind, _ := payload["kind"].(string)
	if kind == "" {
		kind = "*"
	}
	reg, am, e := acLoad(dir)
	if e != "" {
		return nil, e
	}
	covered := false
	if agent != "" {
		if _, ok := am.ByAgent[agent]; ok {
			covered = true
		}
	}
	if stage != "" {
		if _, ok := am.ByStage[stage]; ok {
			covered = true
		}
	}
	ids := acContractsFor(reg, am, agent, stage, kind)
	items := []map[string]any{}
	for _, id := range ids {
		items = append(items, map[string]any{"artifact_id": id, "title": reg[id].Title, "tier": reg[id].Tier})
	}
	return map[string]any{"agent": agent, "stage": stage, "kind": kind, "covered": covered,
		"none": len(ids) == 0 && covered, "contracts": items, "count": len(items)}, ""
}

// ACContractValidateOp validates produced text against a contract (fail-closed).
func ACContractValidateOp(payload map[string]any) (map[string]any, string) {
	dir, _ := payload["dir"].(string)
	aid, _ := payload["artifact_id"].(string)
	text, _ := payload["text"].(string)
	reg, _, e := acLoad(dir)
	if e != "" {
		return nil, e
	}
	c, ok := reg[aid]
	if !ok {
		return map[string]any{"ok": false, "artifact_id": aid,
			"reasons": []string{"unknown artifact contract " + aid}}, ""
	}
	low := strings.ToLower(text)
	missing := []string{}
	for _, s := range c.Sections {
		if !strings.Contains(low, strings.ToLower(s)) {
			missing = append(missing, s)
		}
	}
	maxLines := 0
	if v, ok := c.Size["max_lines"]; ok {
		if n, ok2 := acToInt(v); ok2 {
			maxLines = n
		}
	}
	lines := 0
	if text != "" {
		lines = strings.Count(text, "\n") + 1
	}
	over := maxLines > 0 && lines > maxLines
	reasons := []string{}
	if len(missing) > 0 {
		reasons = append(reasons, "missing sections: "+strings.Join(missing, ", "))
	}
	if over {
		reasons = append(reasons, fmt.Sprintf("over size budget: %d lines > max %d", lines, maxLines))
	}
	return map[string]any{"ok": len(reasons) == 0, "artifact_id": aid, "missing_sections": missing,
		"lines": lines, "max_lines": maxLines, "over_size": over, "reasons": reasons}, ""
}

// ACContractCoverageOp checks that every supplied agent/stage is covered and the registry
// metadata is complete (so a NEW/dynamic agent/stage cannot ship without a contract).
func ACContractCoverageOp(payload map[string]any) (map[string]any, string) {
	dir, _ := payload["dir"].(string)
	reg, am, e := acLoad(dir)
	if e != "" {
		return nil, e
	}
	agents := acStrings(payload["agents"])
	stages := acStrings(payload["stages"])
	missingAgents := []string{}
	missingStages := []string{}
	bad := []string{}
	for _, a := range agents {
		if _, ok := am.ByAgent[a]; !ok {
			missingAgents = append(missingAgents, a)
		}
	}
	for _, s := range stages {
		if _, ok := am.ByStage[s]; !ok {
			missingStages = append(missingStages, s)
		}
	}
	for id, c := range reg {
		if c.Title == "" || c.Tier == "" || len(c.Sections) == 0 || c.FormatVersion == "" {
			bad = append(bad, id+": missing metadata")
		}
		if _, ok := c.Source["canonical_url"]; !ok {
			bad = append(bad, id+": no source.canonical_url")
		}
	}
	refCheck := func(m map[string][]string) {
		for k, ids := range m {
			for _, aid := range ids {
				if aid == "none" || aid == "modality" {
					continue
				}
				if _, ok := reg[aid]; !ok {
					bad = append(bad, k+": unknown artifact "+aid)
				}
			}
		}
	}
	refCheck(am.ByAgent)
	refCheck(am.ByStage)
	sort.Strings(missingAgents)
	sort.Strings(missingStages)
	sort.Strings(bad)
	ok := len(missingAgents) == 0 && len(missingStages) == 0 && len(bad) == 0
	return map[string]any{"ok": ok, "missing_agents": missingAgents, "missing_stages": missingStages,
		"bad_contracts": bad}, ""
}
