"""Product Forge's own scope store (Step 8): plan + run state.

Truths for the Product Forge scope (mirrors the project scope):
  config -> product-forge/plan.json    (writer: core/enhance.py)
  state  -> product-forge/state.json   (writer: pipeline_executor / self-enhance)
  backlog-> product-forge/backlog/*    (writer: core/backlog.py)
Single writer per file; atomic writes.
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
from datetime import datetime
from typing import Any, Dict, List, Optional

_REPO = str(_PF_ROOT)
_FORGE = os.path.join(_REPO, "data")


def plan_path() -> str:
    return os.path.join(_FORGE, "plan.json")


def state_path() -> str:
    return os.path.join(_FORGE, "state.json")


def _rj(p: str, d: Any) -> Any:
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def _wj(p: str, data: Any) -> Any:
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    os.replace(tmp, p)
    return data


def read_plan() -> Dict:
    return _rj(plan_path(), {"version": "1", "goals": [], "items": [], "updated_at": ""})


def write_plan(plan: Dict) -> Dict:
    plan = dict(plan or {})
    plan.setdefault("version", "1")
    plan["updated_at"] = datetime.now().isoformat()
    return _wj(plan_path(), plan)


def add_goal(title: str, body: str = "", item_id: str = "") -> Dict:
    plan = read_plan()
    goals: List[Dict] = plan.setdefault("goals", [])
    goals.append({"title": title, "body": body, "item_id": item_id,
                  "at": datetime.now().isoformat()})
    return write_plan(plan)


def read_state() -> Dict:
    return _rj(state_path(), {"scope": "product_forge", "status": "idle",
                              "current_stage": None, "completed_stages": [],
                              "total_tokens": 0, "total_cost": 0.0, "updated_at": ""})


def write_state(state: Dict) -> Dict:
    state = dict(state or {})
    state.setdefault("scope", "product_forge")
    state["updated_at"] = datetime.now().isoformat()
    return _wj(state_path(), state)


def update_state(**fields) -> Dict:
    st = read_state()
    st.update(fields or {})
    return write_state(st)
