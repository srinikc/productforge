"""ENG-0: canonical engineering architecture descriptor (read + validate).

Single reader of ``config/engineering-flow.json`` — the ordered requirement -> deploy flow, each step mapped
to its canonical owner file and (where one exists) the canonical ``/api/v1`` route that exposes it.

Data-only: this module defines no engine and writes nothing. It is the architecture reference the engineering
phases (ENG-1 .. ENG-10) build against, and the surface ``GET /api/v1/engineering`` serves. No duplicate
engine/store is introduced (authority: ``config/store-registry.json``).
"""
import json
import os
from typing import Any, Dict, List, Optional

from core.paths import ROOT

FILENAME = "engineering-flow.json"
_PATH = os.path.join(ROOT, "config", FILENAME)
_STATUSES = ("exists", "partial", "planned")


def path() -> str:
    return _PATH


def load() -> Dict[str, Any]:
    try:
        with open(_PATH, encoding="utf-8-sig") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def flow() -> List[Dict[str, Any]]:
    return list(load().get("flow") or [])


def stage(stage_id: str) -> Optional[Dict[str, Any]]:
    sid = str(stage_id or "")
    return next((s for s in flow() if s.get("id") == sid), None)


def coverage() -> Dict[str, Any]:
    steps = flow()
    by_status: Dict[str, int] = {s: 0 for s in _STATUSES}
    for st in steps:
        stt = str(st.get("status") or "planned")
        by_status[stt] = by_status.get(stt, 0) + 1
    return {"total": len(steps), "by_status": by_status,
            "planned_phases": sorted({str(s.get("phase")) for s in steps
                                      if s.get("status") == "planned" and s.get("phase")})}


def validate() -> Dict[str, Any]:
    """Structural + owner-file checks (route wiring is checked by the precheck gate script)."""
    errors: List[str] = []
    steps = flow()
    ids = [str(s.get("id") or "") for s in steps]
    if not steps:
        errors.append("flow is empty")
    if len(ids) != len(set(ids)):
        errors.append("duplicate step ids")
    for s in steps:
        sid = str(s.get("id") or "?")
        status = str(s.get("status") or "")
        if status not in _STATUSES:
            errors.append(f"{sid}: invalid status {status!r}")
        if status != "planned":
            owner = str(s.get("owner") or "")
            if not owner:
                errors.append(f"{sid}: missing owner for status={status}")
            elif not os.path.isfile(os.path.join(ROOT, owner)):
                errors.append(f"{sid}: owner file not found: {owner}")
    data = load()
    if not data.get("invariants"):
        errors.append("invariants missing")
    if not data.get("forbidden"):
        errors.append("forbidden list missing")
    return {"ok": not errors, "errors": errors, "checked": len(steps),
            "planned": sum(1 for s in steps if s.get("status") == "planned")}
