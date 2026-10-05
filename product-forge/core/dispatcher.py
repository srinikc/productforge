"""PFSSOT-P9 (BI-PF-0371): automatic dispatch - assign eligible items to available workers.

When enabled, a dispatch pass matches **available workers** (P6 registry) to **eligible backlog items**
(P4) and claims them (P5), handing each assignment to the worker's **adapter** (P7). It does NOT execute
work (adapter ``start`` stays explicit/opt-in).

Config (central flag registry):
  * ``WORKER_AUTO_DISPATCH``         default "0" (manual pull only)
  * ``WORKER_DISPATCH_POLL_SECONDS`` default "5"
Gated by ``WORKER_INTEGRATION_ENABLED`` (P8A): if the worker layer is off, dispatch is a no-op.

Composes existing owners; no new engine and no new store. Idempotent: relies on P4 eligibility + P5 atomic
claim, so it never double-assigns.
"""
from datetime import datetime
from typing import Any

_STATE: dict[str, Any] = {"last_tick": "", "last_assigned": [], "ticks": 0}


def _flag(name: str, default: str) -> str:
    try:
        from core import env_flags
        return str(env_flags.get(name, default) or default)
    except Exception:
        return default


def enabled() -> bool:
    return _flag("WORKER_AUTO_DISPATCH", "0").lower() in ("1", "true", "yes", "on")


def poll_seconds() -> int:
    try:
        return int(_flag("WORKER_DISPATCH_POLL_SECONDS", "5"))
    except Exception:
        return 5


def status() -> dict[str, Any]:
    from core import worker_registry
    return {"enabled": enabled(), "worker_integration": worker_registry.integration_enabled(),
            "poll_seconds": poll_seconds(), "last_tick": _STATE["last_tick"],
            "ticks": _STATE["ticks"], "last_assigned": list(_STATE["last_assigned"])}


def tick(scope: str = "product_forge", project: str | None = None, *,
         force: bool = False, max_assign: int = 0) -> dict[str, Any]:
    """Run ONE dispatch pass. Returns ``{ran, assigned:[...], skipped, reason}``.

    ``force=True`` runs even when ``WORKER_AUTO_DISPATCH`` is off (operator tick / tests).
    """
    from core import worker_registry
    _STATE["ticks"] += 1
    _STATE["last_tick"] = datetime.now().isoformat()
    if not worker_registry.integration_enabled():
        return {"ran": False, "assigned": [], "reason": "worker integration disabled"}
    if not force and not enabled():
        return {"ran": False, "assigned": [], "reason": "auto dispatch disabled (WORKER_AUTO_DISPATCH=0)"}

    assigned: list[dict[str, Any]] = []
    limit = int(max_assign or 0) or 10 ** 6
    # available workers first (ONLINE/IDLE, not revoked)
    workers = [w for w in worker_registry.list_workers(scope, project)
               if not w.get("revoked") and str(w.get("status")) in ("ONLINE", "IDLE")]
    for w in workers:
        if len(assigned) >= limit:
            break
        wid = str(w.get("worker_id"))
        r = _assign_one(scope, project, wid, str(w.get("runtime") or ""))
        if r.get("assigned"):
            assigned.append({"worker_id": wid, "item": r.get("item")})
    _STATE["last_assigned"] = assigned
    return {"ran": True, "assigned": assigned, "workers": len(workers),
            "reason": "" if assigned else "no eligible work for available workers"}


def _assign_one(scope: str, project: str | None, worker_id: str, runtime: str) -> dict[str, Any]:
    """Assign the next eligible item to one worker (P4+P5+P7), reusing the work-pull path."""
    from core import work_pull
    r = work_pull.pull(scope, project, worker_id=worker_id, runtime=runtime)
    if not r.get("assigned"):
        return {"assigned": False, "reason": r.get("reason", "")}
    task = (r.get("package") or {}).get("task") or {}
    return {"assigned": True, "item": task.get("item_id")}
