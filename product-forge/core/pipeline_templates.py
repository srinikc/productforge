"""Pipeline template registry (BI-0116): load/validate/select templates and convert to a runnable stage map.

Templates live in pipeline_templates/<id>/template.json (schema: docs/schemas/pipeline-template.v1.schema.json).
A template plus the common pipeline-definition.json produce a tailored per-project pipeline.
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

import json, os
from typing import Any, Dict, List, Optional

TEMPLATES_DIR = os.path.join(str(_PF_ROOT), "pipeline_templates")
SCHEMA_REQUIRED = ("id", "name", "stages")


def _load(path: str) -> Optional[Dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def list_templates() -> List[Dict]:
    out = []
    if not os.path.isdir(TEMPLATES_DIR):
        return out
    for d in sorted(os.listdir(TEMPLATES_DIR)):
        tp = os.path.join(TEMPLATES_DIR, d, "template.json")
        t = _load(tp)
        if not t:
            continue
        out.append({"id": t.get("id") or d, "name": t.get("name"), "category": t.get("category"),
                    "description": t.get("description"), "type": t.get("type"),
                    "stages": len(t.get("stages") or {}), "path": tp})
    return out


def get_template(tid: str) -> Optional[Dict]:
    for cand in (os.path.join(TEMPLATES_DIR, tid, "template.json"),):
        t = _load(cand)
        if t:
            return t
    for d in os.listdir(TEMPLATES_DIR):
        t = _load(os.path.join(TEMPLATES_DIR, d, "template.json"))
        if t and t.get("id") == tid:
            return t
    return None


def validate(t: Dict) -> Dict:
    errs = [f"missing '{k}'" for k in SCHEMA_REQUIRED if not t.get(k)]
    for sid, st in (t.get("stages") or {}).items():
        if not st.get("agent"):
            errs.append(f"stage {sid} has no agent")
        if not st.get("depends_on"):
            errs.append(f"stage {sid} has no depends_on")
    return {"ok": not errs, "errors": errs}


def to_pipeline_def(template: Dict, common: Optional[Dict] = None) -> Dict:
    """Convert a template into a pipeline_def-shaped dict the executor can run.

    Template stages use a flat `agent` field; we emit the common stage schema
    (ideal_flow/depends_on/approval_gate/...) so DAGExecutor + stage_runner accept it.
    """
    stages = {}
    for sid, st in (template.get("stages") or {}).items():
        agent = st.get("agent")
        stages[sid] = {
            "name": st.get("name") or sid,
            "ideal_flow": [agent] if agent else [],
            "on_complete": st.get("on_complete") or "orchestrator",
            "sub_agents": st.get("sub_agents") or {},
            "approval_gate": st.get("approval_gate"),
            "budget_limit": st.get("budget_limit", 0.1),
            "design_critic": False, "visual_qa": False,
            "depends_on": list(st.get("depends_on") or []),
            "parallel_safe": bool(st.get("parallel_safe", False)),
            "agent_dependencies": {agent: []} if agent else {},
            "display_id": st.get("display_id") or sid,
            "phase": st.get("phase") or (template.get("name") or template.get("category") or "Template"),
        }
    return {"version": "template/1.0", "description": template.get("description", ""),
            "template_id": template.get("id"), "stages": stages}


def apply_template(common: Dict, template: Dict) -> Dict:
    """Common pipeline with the template's stages replacing the stage map (template drives the whole run)."""
    import copy
    pd = to_pipeline_def(template, common)
    pd["_from_template"] = template.get("id")
    return pd


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Pipeline template registry (BI-0116)")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--validate", default="", help="template id")
    a = ap.parse_args()
    if a.validate:
        t = get_template(a.validate)
        print(json.dumps(validate(t) if t else {"ok": False, "errors": ["not found"]}, indent=2))
    else:
        print(json.dumps(list_templates(), indent=2))
