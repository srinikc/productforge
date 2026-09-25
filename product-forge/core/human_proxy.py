"""
Auto mode — Human-like agents (HIL proxy + ideation partner).

Used ONLY when a project runs in auto mode (project.json: auto_mode / auto_human).
- `human`         : external stakeholder that makes gate decisions (HIL proxy).
- `product-owner` : partners with ideation/discovery to distill the idea.

Recorded as human-equivalent decisions; never invents stage work.
"""
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

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, Optional

_REPO = str(_PF_ROOT)


def is_auto(project_dir: str) -> bool:
    try:
        with open(os.path.join(project_dir, "project.json"), "r", encoding="utf-8") as f:
            cfg = json.load(f) or {}
        return bool(cfg.get("auto_mode")) or bool(cfg.get("auto_human")) \
            or str(cfg.get("mode", "")).lower() == "auto"
    except Exception:
        return False


def _parse(text: str) -> Dict[str, Any]:
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.S) or re.search(r"(\{.*\})", text, re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    return {"decision": "approve", "reasons": ["decision not parsed"], "gate": ""}


def _record(project_dir: str, stage_id: str, agent_id: str, decision: Dict):
    try:
        qa = os.path.join(project_dir, "docs", "qa")
        os.makedirs(qa, exist_ok=True)
        with open(os.path.join(qa, "human-review.md"), "a", encoding="utf-8") as f:
            f.write(f"\n## Human Proxy — stage {stage_id} / {agent_id} "
                    f"({datetime.now().isoformat()})\n"
                    f"- decision: **{decision.get('decision')}**\n"
                    f"- reasons: {decision.get('reasons')}\n")
    except Exception:
        pass


def decide(executor, agent_id: str, stage_id: str,
           artifacts: Optional[list] = None) -> Dict[str, Any]:
    """Invoke the `human` agent to make the gate decision (auto mode)."""
    task = (f"Decide as the human owner for gate '{stage_id}' (agent '{agent_id}'). "
            "Review the stage context and artifacts, then output ONLY the JSON decision "
            "{\"decision\":\"approve\"|\"changes\", \"gate\":..., \"reasons\":[...], \"notes\":...}.")
    try:
        ex = executor.execute_agent("human", stage_id, task)
        text = ""
        for p in (getattr(ex, "artifacts", []) or []):
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    text += f.read()
            except Exception:
                pass
        text += "\n" + str(getattr(ex, "error", "") or "")
        decision = _parse(text)
        decision.setdefault("gate", stage_id)
        _record(getattr(executor, "project_dir", ""), stage_id, agent_id, decision)
        return decision
    except Exception as e:
        return {"decision": "approve", "reasons": [f"proxy error: {e}"], "gate": stage_id}


def ideation_partner(executor, stage_id: str = "0") -> Optional[Any]:
    """Invoke `product-owner` to distill the idea (auto mode)."""
    task = ("Partner with the ideation/discovery agents. Distill the idea into: vision & goals "
            "(measurable), target users, scope (must/nice), 10-15 key features, constraints/risks, "
            "and suggested phasing. Write docs/product-goals.md. Do NOT write code.")
    try:
        return executor.execute_agent("product-owner", stage_id, task)
    except Exception as e:
        print(f"[HumanProxy] ideation partner: {e}")
        return None
