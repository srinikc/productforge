"""ENG-0: canonical engineering architecture descriptor (read + validate).

Single reader of ``config/engineering-flow.json``. The descriptor records the **two independent entry paths**:

  * ``external_ingestion`` — the already-implemented Intake path (external idea/requirement -> work item).
    It has NO dependency edge into engineering.
  * ``flow`` — the engineering execution path. It starts at the **direct engineering entry**
    ``task_contract`` (the Task/Work API) and runs scheduler -> worker -> worktree -> commit -> PR.

**Intake is not a prerequisite for engineering work.** This module defines no engine and writes nothing; the
surface ``GET /api/v1/engineering`` serves it and ``scripts/dev/engineering_flow_check.py`` gates it.
"""
import json
import os
from typing import Any, Dict, List, Optional

from core.paths import ROOT

FILENAME = "engineering-flow.json"
_PATH = os.path.join(ROOT, "config", FILENAME)
_STATUSES = ("exists", "partial", "planned")
ENTRY_KINDS = ("engineering", "external")
_DIRECT_ENTRY = "task_contract"
_INTAKE_OWNER = "core/intake.py"


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
    """The engineering execution flow (starts at the direct engineering entry)."""
    return list(load().get("flow") or [])


def external_ingestion() -> List[Dict[str, Any]]:
    """The separate external-ingestion path (Intake); no edge into the engineering flow."""
    return list(load().get("external_ingestion") or [])


def entries() -> Dict[str, List[Dict[str, Any]]]:
    return {"engineering": flow(), "external": external_ingestion()}


def stage(stage_id: str) -> Optional[Dict[str, Any]]:
    sid = str(stage_id or "")
    return next((s for s in flow() + external_ingestion() if s.get("id") == sid), None)


def coverage() -> Dict[str, Any]:
    steps = flow()
    by_status: Dict[str, int] = {s: 0 for s in _STATUSES}
    for st in steps:
        stt = str(st.get("status") or "planned")
        by_status[stt] = by_status.get(stt, 0) + 1
    return {"total": len(steps), "by_status": by_status, "external_ingestion": len(external_ingestion()),
            "direct_entry": _DIRECT_ENTRY,
            "planned_phases": sorted({str(s.get("phase")) for s in steps
                                      if s.get("status") == "planned" and s.get("phase")})}


def _check_owner(steps: List[Dict[str, Any]], errors: List[str], bucket: str) -> None:
    for s in steps:
        sid = str(s.get("id") or "?")
        status = str(s.get("status") or "")
        if status not in _STATUSES:
            errors.append(f"{sid}: invalid status {status!r}")
        if status != "planned":
            owner = str(s.get("owner") or "")
            if not owner:
                errors.append(f"{bucket}:{sid}: missing owner for status={status}")
            elif not os.path.isfile(os.path.join(ROOT, owner)):
                errors.append(f"{bucket}:{sid}: owner file not found: {owner}")


def validate() -> Dict[str, Any]:
    """Structural + entry-path + owner-file checks (route wiring is checked by the precheck gate)."""
    errors: List[str] = []
    eng = flow()
    ext = external_ingestion()
    ids = [str(s.get("id") or "") for s in eng + ext]
    if not eng:
        errors.append("engineering flow is empty")
    if len(ids) != len(set(ids)):
        errors.append("duplicate step ids across entries")

    _check_owner(eng, errors, "flow")
    _check_owner(ext, errors, "external_ingestion")

    # Entry-path contract: engineering work must not route through Intake.
    if any(str(s.get("owner")) == _INTAKE_OWNER for s in eng):
        errors.append("flow contains an intake-owned step (Intake must not be an engineering prerequisite)")
    direct = [s for s in eng if str(s.get("id")) == _DIRECT_ENTRY]
    if not direct:
        errors.append(f"missing direct engineering entry {_DIRECT_ENTRY!r} in flow")
    elif str(direct[0].get("entry")) != "engineering":
        errors.append(f"{_DIRECT_ENTRY!r} must declare entry=engineering")
    if not ext:
        errors.append("external_ingestion path missing (Intake must be represented as a separate path)")

    data = load()
    if not data.get("invariants"):
        errors.append("invariants missing")
    if not data.get("forbidden"):
        errors.append("forbidden list missing")
    return {"ok": not errors, "errors": errors, "checked": len(eng) + len(ext),
            "engineering": len(eng), "external_ingestion": len(ext),
            "planned": sum(1 for s in eng if s.get("status") == "planned")}
