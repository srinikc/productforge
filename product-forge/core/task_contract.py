"""ENG-1: Engineering Task Contract — the executable unit of work.

A task is not merely a backlog title: it is a structured contract any *compatible worker* can execute
(plan §13). This module is the single writer of the contract store ``tasks/task-contracts.json`` per scope
(``product-forge/tasks/`` or ``products/<project>/tasks/``) and the only validator of the contract shape.

Work-item ids in the backlog remain the work SSOT; a task contract references them (``epic_id``/``feature_id``)
and carries the execution fields the scheduler/worker need. No engine, no duplicate of the backlog.
"""
import json
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.paths import PRODUCTS_DIR, ROOT

FILENAME = "task-contracts.json"
_SEP = "/"

RISKS = ("low", "medium", "high", "critical")
STATUSES = ("draft", "ready", "assigned", "in_progress", "blocked", "review", "done", "cancelled", "failed")
PRIORITIES = ("P0", "P1", "P2", "P3")

_STR_FIELDS = ("task_id", "project_id", "epic_id", "feature_id", "parent_task_id", "title", "description",
               "objective", "required_worker_type", "validation_profile", "owner", "status", "run_id")
_LIST_FIELDS = ("acceptance_criteria", "dependencies", "blocked_by", "affected_components", "affected_files",
                "allowed_paths", "restricted_paths", "required_capabilities", "test_requirements",
                "security_requirements", "performance_requirements", "expected_artifacts")
# The full conceptual contract (plan §13) - every field is always present after normalize().
FIELDS = _STR_FIELDS + _LIST_FIELDS + ("risk", "priority", "branch_policy", "repair_policy")


def _norm_scope(scope: str) -> str:
    return "product_forge" if str(scope) in ("portfolio", "product_forge") else "project"


def _dir(scope: str, project: Optional[str] = None) -> str:
    if _norm_scope(scope) == "product_forge":
        return os.path.join(ROOT, "tasks")
    return os.path.join(PRODUCTS_DIR, str(project or "_unknown"), "tasks")


def path(scope: str, project: Optional[str] = None) -> str:
    return os.path.join(_dir(scope, project), FILENAME)


def _lock(d: str) -> str:
    os.makedirs(d, exist_ok=True)
    lp = os.path.join(d, ".lock")
    for _ in range(50):
        try:
            fd = os.open(lp, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return lp
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(lp) > 300:
                    os.remove(lp)
                    continue
            except Exception:
                pass
            time.sleep(0.1)
    raise TimeoutError("could not acquire task-contract lock")


def _unlock(lp: str) -> None:
    try:
        os.remove(lp)
    except Exception:
        pass


def _read(scope: str, project: Optional[str] = None) -> Dict[str, Any]:
    p = path(scope, project)
    try:
        with open(p, encoding="utf-8-sig") as f:
            d = json.load(f)
        if isinstance(d, dict) and isinstance(d.get("tasks"), dict):
            return d
    except Exception:
        pass
    return {"next": 1, "tasks": {}}


def _write(scope: str, project: Optional[str], data: Dict[str, Any]) -> None:
    p = path(scope, project)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, p)


def _tag(scope: str, project: Optional[str]) -> str:
    if _norm_scope(scope) == "product_forge":
        return "PF"
    slug = re.sub(r"[^A-Za-z0-9]", "", str(project or ""))[:3].upper()
    return slug or "PRJ"


def validate(data: Dict[str, Any]) -> Dict[str, Any]:
    """Shape check of a proposed contract. Returns ``{ok, errors}`` (fail-closed)."""
    errors: List[str] = []
    if not isinstance(data, dict):
        return {"ok": False, "errors": ["contract must be an object"]}
    if not str(data.get("title") or "").strip():
        errors.append("title required")
    if not str(data.get("objective") or "").strip():
        errors.append("objective required")
    ac = data.get("acceptance_criteria")
    if not isinstance(ac, (list, tuple)) or not [x for x in ac if str(x).strip()]:
        errors.append("acceptance_criteria must be a non-empty list")
    risk = str(data.get("risk") or "medium").lower()
    if risk not in RISKS:
        errors.append(f"risk must be one of {list(RISKS)}")
    priority = str(data.get("priority") or "P2").upper()
    if priority not in PRIORITIES:
        errors.append(f"priority must be one of {list(PRIORITIES)}")
    status = str(data.get("status") or "draft").lower()
    if status not in STATUSES:
        errors.append(f"status must be one of {list(STATUSES)}")
    for f in _LIST_FIELDS:
        v = data.get(f)
        if v is not None and not isinstance(v, (list, tuple)):
            errors.append(f"{f} must be a list")
    return {"ok": not errors, "errors": errors}


def normalize(data: Dict[str, Any]) -> Dict[str, Any]:
    """Fill every contract field with a safe default (plan §13 shape)."""
    out: Dict[str, Any] = {}
    for f in _STR_FIELDS:
        out[f] = str(data.get(f) or "")
    for f in _LIST_FIELDS:
        v = data.get(f)
        out[f] = [str(x) for x in v] if isinstance(v, (list, tuple)) else []
    out["risk"] = str(data.get("risk") or "medium").lower()
    out["priority"] = str(data.get("priority") or "P2").upper()
    out["status"] = str(data.get("status") or "draft").lower()
    for f in ("branch_policy", "repair_policy"):
        v = data.get(f)
        out[f] = dict(v) if isinstance(v, dict) else {}
    return out


def create(scope: str, project: Optional[str], data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a contract (validated + normalized + id-assigned). Raises ValueError if invalid."""
    res = validate(data)
    if not res["ok"]:
        raise ValueError("; ".join(res["errors"]))
    d = _lock(_dir(scope, project))
    try:
        store = _read(scope, project)
        n = int(store.get("next") or 1)
        tid = f"TC-{_tag(scope, project)}-{n:04d}"
        store["next"] = n + 1
        item = normalize(data)
        item["task_id"] = tid
        item["project_id"] = str(item.get("project_id") or project or "")
        now = datetime.now().isoformat()
        item["created_at"] = now
        item["updated_at"] = now
        store["tasks"][tid] = item
        _write(scope, project, store)
        return item
    finally:
        _unlock(d)


def get(scope: str, project: Optional[str], task_id: str) -> Optional[Dict[str, Any]]:
    return _read(scope, project).get("tasks", {}).get(str(task_id))


def list_tasks(scope: str, project: Optional[str] = None, status: str = "") -> List[Dict[str, Any]]:
    items = list(_read(scope, project).get("tasks", {}).values())
    if status:
        items = [it for it in items if it.get("status") == status]
    return sorted(items, key=lambda it: str(it.get("created_at") or ""))


def set_status(scope: str, project: Optional[str], task_id: str, status: str,
               note: str = "") -> Optional[Dict[str, Any]]:
    st = str(status or "").strip().lower()
    if st not in STATUSES:
        raise ValueError(f"status must be one of {list(STATUSES)}")
    d = _lock(_dir(scope, project))
    try:
        store = _read(scope, project)
        it = store.get("tasks", {}).get(str(task_id))
        if it is None:
            return None
        it["status"] = st
        it["updated_at"] = datetime.now().isoformat()
        if note:
            it.setdefault("notes", []).append({"at": it["updated_at"], "note": str(note)})
        _write(scope, project, store)
        return it
    finally:
        _unlock(d)
