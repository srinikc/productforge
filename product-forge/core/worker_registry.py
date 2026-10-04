"""PFSSOT-P6 (BI-PF-0367): minimal, runtime-neutral worker registry + heartbeat + lifecycle.

Workers are **externally registered execution resources** (OpenCode session, CLI, remote runtime) - NOT
PF agents (agents stay native; doc §2/§23). The scheduler/control plane owns authoritative worker state
(§19); workers report facts (registration/heartbeat/assignment) and the registry derives the rest.

One concern, one writer: ``engineering/worker-registry.json`` (registered in config/store-registry.json).
No large payloads in heartbeat (§20); no per-worker identity system.
"""
import contextlib
import json
import os
import time
from datetime import datetime
from typing import Any

from core.paths import PRODUCTS_DIR, ROOT

FILENAME = "worker-registry.json"
# lifecycle: REGISTERING -> ONLINE -> {IDLE | BUSY | PAUSED | DRAINING | OFFLINE | STALE}
LIFECYCLE = ("REGISTERING", "ONLINE", "IDLE", "BUSY", "PAUSED", "DRAINING", "OFFLINE", "STALE")
_DEFAULT_STALE_SECONDS = 90


def _norm_scope(scope: str) -> str:
    return "product_forge" if str(scope) in ("portfolio", "product_forge") else "project"


def _dir(scope: str, project: str | None = None) -> str:
    if _norm_scope(scope) == "product_forge":
        return os.path.join(ROOT, "engineering")
    return os.path.join(PRODUCTS_DIR, str(project or "_unknown"), "engineering")


def path(scope: str, project: str | None = None) -> str:
    return os.path.join(_dir(scope, project), FILENAME)


def _stale_seconds() -> int:
    try:
        from core import env_flags
        return int(env_flags.get("PF_WORKER_STALE_SECONDS", _DEFAULT_STALE_SECONDS) or _DEFAULT_STALE_SECONDS)
    except Exception:
        return _DEFAULT_STALE_SECONDS


def _lock(d: str) -> str:
    os.makedirs(d, exist_ok=True)
    lp = os.path.join(d, ".worker-registry.lock")
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
    raise TimeoutError("could not acquire worker-registry lock")


def _unlock(lp: str) -> None:
    with contextlib.suppress(Exception):
        os.remove(lp)


def _read(scope: str, project: str | None = None) -> dict[str, Any]:
    try:
        with open(path(scope, project), encoding="utf-8-sig") as f:
            d = json.load(f)
        if isinstance(d, dict) and isinstance(d.get("workers"), dict):
            return d
    except Exception:
        pass
    return {"workers": {}}


def _write(scope: str, project: str | None, data: dict[str, Any]) -> None:
    p = path(scope, project)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, p)


def _heartbeat_age_ms(w: dict[str, Any]) -> float:
    hb = str(w.get("last_heartbeat") or w.get("registered_at") or "")
    if not hb:
        return float("inf")
    try:
        return (datetime.now() - datetime.fromisoformat(hb)).total_seconds() * 1000
    except Exception:
        return float("inf")


def _effective_status(w: dict[str, Any]) -> str:
    """Authoritative status: a non-OFFLINE worker with too-old heartbeat is STALE (doc §20)."""
    st = str(w.get("status") or "ONLINE")
    if st in ("OFFLINE", "DRAINING", "PAUSED", "REGISTERING"):
        return st
    if _heartbeat_age_ms(w) > _stale_seconds() * 1000:
        return "STALE"
    return st


# ── public API ──────────────────────────────────────────────────────────────
def register(scope: str, project: str | None, *, runtime: str = "opencode", capabilities: list | None = None,
             role: str = "", endpoint: str = "", workspace: str = "", worker_id: str = "") -> dict[str, Any]:
    """Register (or re-register) a worker. Minimal payload; returns the worker record with its id."""
    d = _dir(scope, project)
    lp = _lock(d)
    try:
        store = _read(scope, project)
        now = datetime.now().isoformat()
        wid = worker_id or f"WRK-{runtime}-{int(time.time() * 1000) % 10 ** 8}"
        existing = store["workers"].get(wid) or {}
        rec = {
            "worker_id": wid, "runtime": str(runtime or "opencode"),
            "capabilities": [str(c) for c in (capabilities or [])],
            "role": str(role or ""), "endpoint": str(endpoint or ""), "workspace": str(workspace or ""),
            "status": "ONLINE", "current_assignment_id": str(existing.get("current_assignment_id") or ""),
            "registered_at": existing.get("registered_at") or now, "last_heartbeat": now,
            "capability_version": int(existing.get("capability_version") or 0) + 1,
        }
        store["workers"][wid] = rec
        _write(scope, project, store)
        return rec
    finally:
        _unlock(lp)


def heartbeat(scope: str, project: str | None, worker_id: str, *, status: str = "",
              current_assignment_id: str = "") -> dict[str, Any]:
    """Lightweight liveness + optional status/assignment. Scheduler derives authoritative state."""
    d = _dir(scope, project)
    lp = _lock(d)
    try:
        store = _read(scope, project)
        w = store["workers"].get(str(worker_id))
        if not w:
            return {"ok": False, "reason": "unknown worker"}
        w["last_heartbeat"] = datetime.now().isoformat()
        if status and str(status).upper() in LIFECYCLE:
            w["status"] = str(status).upper()
        if current_assignment_id:
            w["current_assignment_id"] = str(current_assignment_id)
        _write(scope, project, store)
        return {"ok": True, "worker_id": w["worker_id"], "status": _effective_status(w)}
    finally:
        _unlock(lp)


def list_workers(scope: str, project: str | None = None) -> list[dict[str, Any]]:
    store = _read(scope, project)
    out = []
    for w in store["workers"].values():
        r = dict(w)
        r["status"] = _effective_status(w)
        r["heartbeat_age_ms"] = round(_heartbeat_age_ms(w), 1)
        out.append(r)
    return sorted(out, key=lambda x: str(x.get("worker_id")))


def get(scope: str, project: str | None, worker_id: str) -> dict[str, Any] | None:
    store = _read(scope, project)
    w = store["workers"].get(str(worker_id))
    if not w:
        return None
    r = dict(w)
    r["status"] = _effective_status(w)
    r["heartbeat_age_ms"] = round(_heartbeat_age_ms(w), 1)
    return r


def capabilities(scope: str, project: str | None, worker_id: str) -> list[str]:
    w = get(scope, project, worker_id)
    return list((w or {}).get("capabilities") or [])


def set_status(scope: str, project: str | None, worker_id: str, status: str) -> dict[str, Any]:
    st = str(status or "").upper()
    if st not in LIFECYCLE:
        raise ValueError(f"status must be one of {list(LIFECYCLE)}")
    d = _dir(scope, project)
    lp = _lock(d)
    try:
        store = _read(scope, project)
        w = store["workers"].get(str(worker_id))
        if not w:
            return {"ok": False, "reason": "unknown worker"}
        w["status"] = st
        w["last_heartbeat"] = datetime.now().isoformat()
        _write(scope, project, store)
        return {"ok": True, "worker_id": worker_id, "status": st}
    finally:
        _unlock(lp)


def unregister(scope: str, project: str | None, worker_id: str, *, revoke: bool = False) -> dict[str, Any]:
    """Remove (unregister) or mark OFFLINE+revoked a worker."""
    d = _dir(scope, project)
    lp = _lock(d)
    try:
        store = _read(scope, project)
        wid = str(worker_id)
        if revoke and wid in store["workers"]:
            store["workers"][wid]["status"] = "OFFLINE"
            store["workers"][wid]["revoked"] = True
            store["workers"][wid]["last_heartbeat"] = datetime.now().isoformat()
            _write(scope, project, store)
            return {"ok": True, "worker_id": wid, "revoked": True}
        existed = store["workers"].pop(wid, None) is not None
        _write(scope, project, store)
        return {"ok": True, "worker_id": wid, "removed": existed}
    finally:
        _unlock(lp)


def available_slots(scope: str, project: str | None = None) -> list[dict[str, Any]]:
    """Bridge to the EXISTING scheduler slot shape: ONLINE/IDLE registry workers -> slots.

    Extends (does not replace) the static pool: callers may merge with ``scheduler.worker_slots()``.
    """
    slots = []
    for w in list_workers(scope, project):
        if w.get("revoked"):
            continue
        if str(w.get("status")) not in ("ONLINE", "IDLE"):
            continue
        slots.append({"slot_id": f"reg:{w['worker_id']}", "worker_id": w["worker_id"],
                      "type": w.get("runtime") or "external", "capabilities": list(w.get("capabilities") or []),
                      "max_concurrency": 1, "source": "registry", "role": w.get("role") or ""})
    return slots
