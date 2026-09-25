"""
Feature flags / integration toggles.

Governance model (precedence high -> low):
  1. HIL / run override      : explicit per-run decision (CLI/interactive)
  2. project config          : project.json -> "integrations" (committed decision of record)
  3. environment             : PIPELINE_<NAME> (CI/ops convenience)
  4. built-in default

The orchestrator *evaluates* this deterministically; it does not invent its own
heuristics. Every decision carries its source so it can be audited/recorded.
"""
import json
import os
from typing import Any, Dict, Optional, Tuple

# name -> built-in default
# Internal (no effect on the shipped product/quality) default ON; user-facing default OFF (HIL).
DEFAULTS: Dict[str, bool] = {
    "techstack_guidelines": True,   # internal
    "spec_llm": True,               # internal
    "code_analyzer": True,          # internal (only used by fix; adds a change plan)
    "per_category": True,           # internal
    "business_skills": False,       # user-facing -> HIL
    "service_catalog": False,       # user-facing -> HIL
}

# Impact classification: internal = auto; user_facing = HIL-confirmed.
INTERNAL = {"techstack_guidelines", "spec_llm", "code_analyzer", "per_category"}


def _project_cfg(project_dir: Optional[str]) -> Dict[str, Any]:
    if not project_dir:
        return {}
    try:
        p = os.path.join(project_dir, "project.json")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return (json.load(f) or {})
    except Exception:
        pass
    return {}


def resolve(name: str, project_dir: Optional[str] = None,
            override: Optional[bool] = None) -> Tuple[bool, str]:
    """Return (enabled, source).

    Precedence: HIL run override > project config > HIL/auto choices >
    pipeline recommendation > env > default.
    """
    if override is not None:
        return bool(override), "hil_override"

    cfg = _project_cfg(project_dir)
    for section in ("integrations", "features"):
        sec = cfg.get(section)
        if isinstance(sec, dict) and name in sec:
            return bool(sec[name]), f"project.{section}"

    choice = _choices(project_dir, name)
    if choice is not None:
        return choice, "hil_choice"

    rec = _recommendation(project_dir, name)
    if rec is not None:
        return rec, "recommendation"

    env = os.environ.get("PIPELINE_" + name.upper())
    if env is not None:
        return env not in ("0", "false", "False", ""), "env"

    return bool(DEFAULTS.get(name, False)), "default"


def _choices(project_dir: Optional[str], name: str) -> Optional[bool]:
    """HIL/auto decisions recorded by the integration advisor."""
    if not project_dir:
        return None
    try:
        p = os.path.join(project_dir, "integration_choices.json")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
            c = data.get("choices") or {}
            if name in c:
                return bool(c[name])
    except Exception:
        pass
    return None


def _recommendation(project_dir: Optional[str], name: str) -> Optional[bool]:
    """Pipeline-recommended value (core.integration_advisor output), if present."""
    if not project_dir:
        return None
    try:
        p = os.path.join(project_dir, "recommendations.json")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
            f_ = (data.get("flags") or {}).get(name)
            if isinstance(f_, dict) and "enabled" in f_:
                return bool(f_["enabled"])
    except Exception:
        pass
    return None


def enabled(name: str, project_dir: Optional[str] = None,
            override: Optional[bool] = None) -> bool:
    return resolve(name, project_dir, override)[0]


def decisions(project_dir: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """Snapshot of every flag + its resolved value/source (for audit/manifest)."""
    out = {}
    for name in DEFAULTS:
        val, src = resolve(name, project_dir)
        out[name] = {"enabled": val, "source": src}
    return out
