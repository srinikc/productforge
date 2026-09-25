"""BI-0096 Review-feedback ledger + BI-0117 dynamic agent creation.

Two cohesive capabilities:
  * ReviewLedger  -> products/<project>/review-ledger.json (producer agent, artifact, reviewer, feedback, resolution)
  * AgentComposer  -> create/register a MAIN agent dynamically (validated + stitched into config SSOT)
Owner store: this module (single writer for review-ledger.json; agents/*.agent.json + config for created agents).
"""
from __future__ import annotations
try:
    from core.paths import ROOT as _PF_ROOT
except ImportError:  # executed as a script: seed the repo root on sys.path, then retry
    import os as _pf_os
    import sys as _pf_sys
    _pf_d = _pf_os.path.abspath(__file__)
    for _pf_i in range(3):
        _pf_d = _pf_os.path.dirname(_pf_d)
        if _pf_os.path.isfile(_pf_os.path.join(_pf_d, 'core', 'paths.py')):
            _pf_sys.path.insert(0, _pf_d)
            break
    from core.paths import ROOT as _PF_ROOT

import json, os, re
from datetime import datetime
from typing import Any, Dict, List, Optional

REPO = str(_PF_ROOT)
LEDGER = "review-ledger.json"


# ── BI-0096: review / feedback ledger ──────────────────────────────────────
def _lp(project_dir: str) -> str:
    return os.path.join(project_dir, LEDGER)


def load(project_dir: str) -> Dict:
    try:
        with open(_lp(project_dir), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"entries": []}


def _save(project_dir: str, d: Dict) -> str:
    p = _lp(project_dir)
    os.makedirs(project_dir, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
    return p


def record(project_dir: str, producer: str, artifact: str, reviewer: str,
           feedback: str, severity: str = "major", stage: str = "") -> Dict:
    d = load(project_dir)
    eid = f"RV-{len(d['entries']) + 1:04d}"
    entry = {"id": eid, "stage": stage, "producer": producer, "artifact": artifact,
             "reviewer": reviewer, "feedback": feedback, "severity": severity,
             "status": "open", "resolution": "", "created_at": datetime.now().isoformat()}
    d["entries"].append(entry)
    _save(project_dir, d)
    return entry


def resolve(project_dir: str, eid: str, resolution: str, status: str = "resolved") -> Optional[Dict]:
    d = load(project_dir)
    for e in d["entries"]:
        if e["id"] == eid:
            e["resolution"] = resolution
            e["status"] = status
            e["resolved_at"] = datetime.now().isoformat()
            _save(project_dir, d)
            return e
    return None


def open_items(project_dir: str) -> List[Dict]:
    return [e for e in load(project_dir)["entries"] if e.get("status") == "open"]


# ── BI-0117: dynamic agent creation ────────────────────────────────────────
AGENT_CARD = """---
description: {desc}
mode: primary
model: {model}
agent_id: {aid}
version: 1.0.0
spec_version: "1.0"
permission:
  bash: {bash}
  edit: {edit}
  web: {web}
---

# {name}

## 0. METADATA
- **Agent ID**: {aid}
- **Version**: 1.0.0
- **Model tier**: {tier}
- **Tools**: {tools}

## 1. ROLE
{role}

- Decides: {decides}
- Does NOT: {notd}

## 2. INPUTS
- Allowed: {allowed}
- Forbidden: {forbidden}

## 3. OUTPUTS
- Artifact: `{artifact}` ({fmt})

## 4. RULES
{rules}

## 5. WORKFLOW
1. Read only the listed inputs (plus bound knowledge/skills).
2. Produce the required artifact with explicit, sourced reasoning.
3. Return a short final summary.

## 6. ARTIFACTS
- {artifact}

## 7. QUALITY CHECKS
- output present, role-appropriate, consistent with inputs; no fabricated data

## 8. STATE UPDATES
- Append an entry to `docs/agent-audit.md`.
- Update `docs/agent-context.md`.
"""


def _valid_id(aid: str) -> bool:
    return bool(re.match(r"^[a-z][a-z0-9-]{1,40}$", aid or ""))


def create_agent(spec: Dict, register: bool = True) -> Dict:
    """Create a MAIN agent from a spec dict (validated). Returns {ok,id,errors,paths}.

    spec keys: id, name, description, role, decides, notd, inputs, outputs, artifact,
               model, tier, tools, skills, knowledge, sub_agents, kind
    """
    aid = (spec.get("id") or "").strip().lower()
    errs: List[str] = []
    if not _valid_id(aid):
        errs.append("invalid id (use kebab-case, e.g. 'market-analyst')")
    if not spec.get("name"):
        errs.append("name required")
    if not spec.get("role"):
        errs.append("role required")
    if not spec.get("artifact"):
        errs.append("artifact required")
    if aid and os.path.exists(os.path.join(REPO, "agents", f"{aid}.agent.json")):
        errs.append(f"agent '{aid}' already exists")
    if errs:
        return {"ok": False, "errors": errs, "id": aid}

    tools = spec.get("tools") or ["read_file", "write_file", "list_dir"]
    tier = spec.get("tier") or "medium"
    model = spec.get("model") or "opencode-go/mimo-v2.5"
    md = AGENT_CARD.format(
        desc=spec.get("description") or spec.get("role", ""),
        model=model, aid=aid, name=spec.get("name"),
        bash="allow" if "run_command" in tools else "deny",
        edit="allow" if "write_file" in tools else "deny",
        web="allow" if "http_get" in tools else "deny",
        tier=tier, tools=", ".join(tools), role=spec.get("role", ""),
        decides=spec.get("decides", "own stage outputs"),
        notd=spec.get("notd", "reduce scope or write outside the workspace"),
        allowed=", ".join(spec.get("inputs") or []) or "prior-stage artifacts",
        forbidden=", ".join(spec.get("forbidden") or []) or "unrelated files",
        artifact=spec.get("artifact"), fmt=spec.get("format", "markdown"),
        rules="\n".join(f"- {r}" for r in (spec.get("rules") or
                        ["No mocks, TODOs, placeholders.", "Respect the declared scope."])),
    )
    paths = {}
    if register:
        os.makedirs(os.path.join(REPO, ".opencode", "agent"), exist_ok=True)
        os.makedirs(os.path.join(REPO, "agents"), exist_ok=True)
        mp = os.path.join(REPO, ".opencode", "agent", f"{aid}.md")
        with open(mp, "w", encoding="utf-8", newline="\n") as f:
            f.write(md)
        paths["card"] = mp
        jp = os.path.join(REPO, "agents", f"{aid}.agent.json")
        card = {"id": aid, "name": spec.get("name"), "description": spec.get("description") or spec.get("role"),
                "mode": "primary", "instructions": md, "tools": tools,
                "skills": spec.get("skills") or [], "sub_agents": spec.get("sub_agents") or [],
                "model_tier": tier, "model_pin": model, "max_input_tokens": 8000, "max_output_tokens": 6000,
                "allowed_inputs": spec.get("inputs") or [], "forbidden_inputs": spec.get("forbidden") or [],
                "knowledge_layers": spec.get("knowledge") or [], "decision_logic": {},
                "can_invoke": spec.get("sub_agents") or [], "output_format": spec.get("format", "markdown"),
                "completion": [], "source": f"opencode:.opencode/agent\\{aid}.md", "dynamic": True}
        with open(jp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(card, f, indent=2, ensure_ascii=False)
        paths["spec"] = jp
    return {"ok": True, "id": aid, "errors": [], "paths": paths, "card_md": md}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Review ledger (BI-0096) / agent composer (BI-0117)")
    sub = ap.add_subparsers(dest="cmd")
    r = sub.add_parser("ledger"); r.add_argument("--project", required=True)
    c = sub.add_parser("create-agent"); c.add_argument("--spec", required=True, help="path to JSON spec")
    a = ap.parse_args()
    if a.cmd == "ledger":
        print(json.dumps(load(os.path.join("products", a.project)), indent=2))
    elif a.cmd == "create-agent":
        print(json.dumps(create_agent(json.load(open(a.spec, encoding="utf-8"))), indent=2))
