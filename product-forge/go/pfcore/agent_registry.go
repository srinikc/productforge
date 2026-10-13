// agent_registry.go — the AGENT REGISTRY engine (Go-first for new work, ADR BI-PF-0388).
// Declarative agent spec: inputs / outputs(artifact ids) / stages / kind_scope. It is the
// SINGLE SOURCE for the agent -> artifact mapping; the artifact-contract engine resolves an
// agent's artifacts from here (falling back to the legacy agents.json by_agent). Invoked via
// the pfcore-host wire seam (core/go_host.py). Stdlib only.
package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
)

// AgentSpec mirrors one entry in config/agent-registry/index.json.
type AgentSpec struct {
	Title     string   `json:"title"`
	Stages    []string `json:"stages"`
	Inputs    []string `json:"inputs"`
	Outputs   []string `json:"outputs"`
	KindScope string   `json:"kind_scope"`
}

type agentRegistry struct {
	Agents map[string]AgentSpec `json:"agents"`
}

// arLoad loads the agent registry. ``acDir`` is config/artifact-contracts; the registry
// lives beside it at config/agent-registry/index.json.
func arLoad(acDir string) (map[string]AgentSpec, string) {
	path := filepath.Join(filepath.Dir(acDir), "agent-registry", "index.json")
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, "read agent-registry/index.json: " + err.Error()
	}
	reg := agentRegistry{}
	if err := json.Unmarshal(raw, &reg); err != nil {
		return nil, "parse agent-registry/index.json: " + err.Error()
	}
	if reg.Agents == nil {
		reg.Agents = map[string]AgentSpec{}
	}
	return reg.Agents, ""
}

// ARAgentRegistryOp returns the full agent registry.
func ARAgentRegistryOp(payload map[string]any) (map[string]any, string) {
	dir, _ := payload["dir"].(string)
	agents, e := arLoad(dir)
	if e != "" {
		return nil, e
	}
	ids := make([]string, 0, len(agents))
	for id := range agents {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	return map[string]any{"ids": ids, "agents": agents, "count": len(ids)}, ""
}

// ARAgentResolveOp resolves one agent's spec.
func ARAgentResolveOp(payload map[string]any) (map[string]any, string) {
	dir, _ := payload["dir"].(string)
	agent, _ := payload["agent"].(string)
	agents, e := arLoad(dir)
	if e != "" {
		return nil, e
	}
	sp, ok := agents[agent]
	return map[string]any{"agent": agent, "covered": ok, "spec": sp}, ""
}

// ARAgentRegisterOp validates a candidate agent spec (its outputs must reference known
// artifact contracts). Does NOT write - the caller persists. Used by dynamic-agent creation.
func ARAgentRegisterOp(payload map[string]any) (map[string]any, string) {
	dir, _ := payload["dir"].(string)
	agent, _ := payload["agent"].(string)
	if agent == "" {
		return nil, "agent id required"
	}
	outputs := acStrings(payload["outputs"])
	reg, _, e := acLoad(dir)
	if e != "" {
		return nil, e
	}
	bad := []string{}
	for _, out := range outputs {
		if out == "none" || out == "modality" {
			continue
		}
		if _, ok := reg[out]; !ok {
			bad = append(bad, "unknown artifact "+out)
		}
	}
	return map[string]any{"ok": len(bad) == 0, "agent": agent, "errors": bad}, ""
}

// ARAgentCoverageOp checks the agent registry: every supplied agent has a spec, and every
// spec's outputs reference a known artifact contract.
func ARAgentCoverageOp(payload map[string]any) (map[string]any, string) {
	dir, _ := payload["dir"].(string)
	agents, e := arLoad(dir)
	if e != "" {
		return nil, e
	}
	reg, _, e2 := acLoad(dir)
	if e2 != "" {
		return nil, e2
	}
	want := acStrings(payload["agents"])
	missing := []string{}
	bad := []string{}
	for _, a := range want {
		if _, ok := agents[a]; !ok {
			missing = append(missing, a)
		}
	}
	for id, sp := range agents {
		if sp.Title == "" {
			bad = append(bad, id+": no title")
		}
		if len(sp.Outputs) == 0 {
			bad = append(bad, id+": no outputs")
		}
		for _, out := range sp.Outputs {
			if out == "none" || out == "modality" {
				continue
			}
			if _, ok := reg[out]; !ok {
				bad = append(bad, id+": unknown artifact "+out)
			}
		}
	}
	sort.Strings(missing)
	sort.Strings(bad)
	ok := len(missing) == 0 && len(bad) == 0
	return map[string]any{"ok": ok, "missing_agents": missing, "bad_specs": bad}, ""
}
