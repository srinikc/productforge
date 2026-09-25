"""Context policy — how much of each upstream artifact an agent receives (FULL vs SUMMARY).

Replaces the implicit "last 3 full, older 500-char slice" with a DECLARED, per-agent
policy and records FIDELITY (what was actually passed) + GAPS (declared-FULL inputs
that were missing or summarised) so "all info considered" is provable.

Config: config/context-policy.json
  {
    "default": {"recent_full": 3, "ambient_max_chars": 2000},
    "agents": {
      "design":    {"full_stages": ["0", "0a", "1a"]},
      "architect": {"full_stages": ["0a", "1", "1a"]}
    },
    "project_overrides": {}
  }

Owner: this module (reads config only; no state written here).
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

REPO = str(_PF_ROOT)
_CONFIG = os.path.join(REPO, "config", "context-policy.json")

_DEFAULT = {
    "default": {"recent_full": 3, "ambient_max_chars": 2000},
    "agents": {},
    "project_overrides": {},
}


def _load() -> dict:
    cfg = json.loads(json.dumps(_DEFAULT))
    try:
        with open(_CONFIG, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        for k in ("default", "agents", "project_overrides"):
            if isinstance(data.get(k), dict):
                cfg[k].update(data[k])
    except Exception:
        pass
    return cfg


def policy_for(agent_id: str, project: str = "") -> dict:
    cfg = _load()
    pol = dict(cfg["default"])
    proj_ov = (cfg["project_overrides"].get(project) or {})
    if isinstance(proj_ov, dict):
        pol.update(proj_ov)
        if agent_id in (proj_ov.get("agents") or {}):
            pol.update(proj_ov["agents"][agent_id])
    if agent_id in cfg["agents"]:
        pol.update(cfg["agents"][agent_id])
    return pol


def decide(agent_id: str, stage_key: str, index: int, count: int, project: str = "") -> str:
    """Return 'full' or 'summary' for one artifact about to be injected.

    FULL when: the artifact's stage is in the agent's ``full_stages`` (a required
    direct input), OR it is among the newest ``recent_full``. Otherwise 'summary'.
    """
    pol = policy_for(agent_id, project)
    stage_of = str(stage_key).split("_", 1)[0]
    if stage_of in (pol.get("full_stages") or []):
        return "full"
    recent = int(pol.get("recent_full", 3) or 3)
    return "full" if index >= (count - recent) else "summary"


def ambient_budget(agent_id: str, project: str = "") -> int:
    return int(policy_for(agent_id, project).get("ambient_max_chars", 2000) or 2000)
