"""Engineering change log (append-only) — records drift detected and the corrective action taken.

Traceability for structural/contract changes: when a gate detects drift (e.g. OpenAPI vs live app, or a stale
generated doc), the corrective regeneration/redesign/implementation is recorded here so it can be referenced or
reverted later. Boundaries:

  * ``core/change_registry`` = in-memory, generic change-REQUEST model (not persistent; not this).
  * backlog = work items (what to do); this log = what structural change already happened and why.
  * append-only (records are immutable) — reverting is done via git on the referenced commit(s).

Single writer of ``engineering/changes.jsonl`` (scope: product_forge) / ``products/<p>/engineering/changes.jsonl``.
"""
import contextlib
import json
import os
import time
import uuid
from datetime import datetime
from typing import Any

from core.paths import PRODUCTS_DIR, ROOT

FILENAME = "changes." + "jsonl"
KINDS = ("drift", "regeneration", "redesign", "implementation", "revert", "correction")


def _norm_scope(scope: str) -> str:
    return "product_forge" if str(scope) in ("portfolio", "product_forge") else "project"


def _dir(scope: str, project: str | None = None) -> str:
    if _norm_scope(scope) == "product_forge":
        return os.path.join(ROOT, "engineering")
    return os.path.join(PRODUCTS_DIR, str(project or "_unknown"), "engineering")


def path(scope: str, project: str | None = None) -> str:
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
    raise TimeoutError("could not acquire change-log lock")


def _unlock(lp: str) -> None:
    with contextlib.suppress(Exception):
        os.remove(lp)


def record(scope: str = "product_forge", project: str | None = None, *, kind: str = "drift",
           summary: str = "", detected_by: str = "", artifact: str = "", before: str = "", after: str = "",
           action: str = "", commit: str = "", revert_ref: str = "", reference: str = "",
           details: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Append one change record. Returns the record (or None on failure)."""
    k = str(kind or "").strip().lower()
    if k not in KINDS:
        k = "correction"
    if not str(summary or "").strip():
        return None
    rec = {"id": "CHG-" + uuid.uuid4().hex[:10], "at": datetime.now().isoformat(), "kind": k,
           "summary": str(summary), "detected_by": str(detected_by), "artifact": str(artifact),
           "before": str(before), "after": str(after), "action": str(action), "commit": str(commit),
           "revert_ref": str(revert_ref), "reference": str(reference),
           "details": dict(details or {}), "scope": _norm_scope(scope), "project": project or ""}
    d = _lock(_dir(scope, project))
    try:
        p = path(scope, project)
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec
    except Exception:
        return None
    finally:
        _unlock(d)


def list_records(scope: str = "product_forge", project: str | None = None,
                 kind: str = "") -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with open(path(scope, project), encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if kind and str(rec.get("kind")) != kind:
                    continue
                out.append(rec)
    except Exception:
        return []
    return out


def recent(scope: str = "product_forge", project: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    rows = list_records(scope, project)
    return rows[-max(1, int(limit)):]
