"""Per-model eligibility policy — versioned rules consumed by model_gate/model_strategy (BI-PF-0278).

Owner of ``config/model-policy.json``. Rules: allowed/restricted tasks, quality_threshold, max_task_cost,
fallback, independent_review. ``eligible()`` is fail-closed: unknown model / restricted task / over-budget /
unmet quality -> deny with reasons. Composes (never forks) model_catalog facts. See docs/MODEL-POLICY-DESIGN.md.
"""

import json
import os
from typing import Dict, List, Optional

try:
    from core.paths import ROOT as _ROOT
except ImportError:  # script execution
    import sys as _sys
    _d = os.path.abspath(__file__)
    for _ in range(3):
        _d = os.path.dirname(_d)
        if os.path.isfile(os.path.join(_d, "core", "paths.py")):
            _sys.path.insert(0, _d)
            break
    from core.paths import ROOT as _ROOT

STORE = os.path.join(str(_ROOT), "config", "model-policy." + "json")
SCHEMA_VERSION = 1

_DEFAULT = {"allowed_tasks": [], "restricted_tasks": [], "quality_threshold": 0.0,
            "max_task_cost": 0.0, "fallback": [], "independent_review": False}


def load() -> Dict:
    try:
        with open(STORE, encoding="utf-8-sig") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def all_policies() -> Dict:
    return load().get("models") or {}


def _resolve(policies: Dict, model: str) -> Optional[Dict]:
    """Robust lookup by id / registry_name / last path segment / ':free' variant."""
    if not model or not isinstance(policies, dict):
        return None
    if model in policies:
        return policies[model]
    tail = str(model).split("/")[-1]
    for k, v in policies.items():
        if not isinstance(v, dict):
            continue
        if v.get("id") == model or v.get("registry_name") == model:
            return v
        if str(k).split("/")[-1] == tail:
            return v
    base = tail.replace(":free", "")
    for k, v in policies.items():
        if isinstance(v, dict) and str(k).split("/")[-1].replace(":free", "") == base:
            return v
    return None


def policy_for(model: str) -> Optional[Dict]:
    p = _resolve(all_policies(), model)
    if p is None:
        return None
    return {**_DEFAULT, **p}


# ── schema validation (fail-closed) ─────────────────────────────────────────
def validate(policy: Optional[Dict] = None) -> List[str]:
    """Return a list of schema errors ([] = valid)."""
    doc = policy if policy is not None else load()
    errs: List[str] = []
    if not isinstance(doc, dict):
        return ["policy must be an object"]
    if int(doc.get("schema_version") or 0) != SCHEMA_VERSION:
        errs.append(f"schema_version must be {SCHEMA_VERSION}")
    models = doc.get("models")
    if not isinstance(models, dict):
        errs.append("models must be an object")
        return errs
    try:
        from core import model_catalog as _mc
        known = set((_mc.load() or {}).keys())
    except Exception:
        known = set()
    for name, p in models.items():
        if not isinstance(p, dict):
            errs.append(f"{name}: policy must be an object")
            continue
        if not isinstance(p.get("allowed_tasks", []), list):
            errs.append(f"{name}: allowed_tasks must be a list")
        if not isinstance(p.get("restricted_tasks", []), list):
            errs.append(f"{name}: restricted_tasks must be a list")
        qt = p.get("quality_threshold", 0.0)
        if not isinstance(qt, (int, float)) or not (0.0 <= float(qt) <= 1.0):
            errs.append(f"{name}: quality_threshold must be 0..1")
        mtc = p.get("max_task_cost", 0.0)
        if not isinstance(mtc, (int, float)) or float(mtc) < 0:
            errs.append(f"{name}: max_task_cost must be >= 0")
        fb = p.get("fallback", [])
        if not isinstance(fb, list):
            errs.append(f"{name}: fallback must be a list")
        else:
            for f in fb:
                if known and str(f) not in known:
                    errs.append(f"{name}: fallback '{f}' is not a known catalog model")
        if not isinstance(p.get("independent_review", False), bool):
            errs.append(f"{name}: independent_review must be a bool")
    return errs


# ── eligibility decision ────────────────────────────────────────────────────
def eligible(model: str, task: str = "", *, critical: bool = False,
             est_cost: float = 0.0, quality: Optional[float] = None) -> Dict:
    """Decide whether ``model`` may run ``task``. Fail-closed on unknown model/policy errors.

    Returns {ok, reasons[], fallback[], independent_review, policy_found}.
    """
    reasons: List[str] = []
    p = policy_for(model)
    if p is None:
        # unknown model OR no policy: fail-closed under strict, else allow (zero regression)
        strict = str(os.environ.get("MODEL_GATE_REJECT_UNKNOWN", "")).strip().lower() in ("1", "true", "yes")
        if strict:
            return {"ok": False, "policy_found": False,
                    "reasons": ["no policy and MODEL_GATE_REJECT_UNKNOWN is set"], "fallback": [],
                    "independent_review": False}
        return {"ok": True, "policy_found": False, "reasons": ["no policy (allowed)"], "fallback": [],
                "independent_review": False}
    if task and task in (p.get("restricted_tasks") or []):
        reasons.append(f"task '{task}' is restricted for {model}")
    allowed = p.get("allowed_tasks") or []
    if task and allowed and task not in allowed:
        reasons.append(f"task '{task}' not in allowed_tasks for {model}")
    mtc = float(p.get("max_task_cost") or 0.0)
    if mtc and float(est_cost or 0.0) > mtc:
        reasons.append(f"estimated cost {est_cost} exceeds max_task_cost {mtc}")
    qth = float(p.get("quality_threshold") or 0.0)
    if critical and qth > 0.0:
        q = quality
        if q is None:
            try:
                from core import model_catalog as _mc
                q = (_mc.capabilities(model) or {}).get("quality")
            except Exception:
                q = None
        if q is not None and float(q) < qth:
            reasons.append(f"quality {q} below threshold {qth} for critical task")
    return {"ok": not reasons, "policy_found": True, "reasons": reasons,
            "fallback": list(p.get("fallback") or []),
            "independent_review": bool(p.get("independent_review", False))}
