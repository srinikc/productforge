"""PFSSOT-P7 (BI-PF-0368): runtime-neutral worker adapter contract.

The scheduler assigns work through an **abstraction**, never OpenCode directly (doc §17/§18). An adapter is
a thin translator between the worker protocol and a concrete runtime:

    register · heartbeat · get_status · accept_assignment · start · pause · cancel · report_result · disconnect

Adapters hold NO orchestration logic and NO state beyond a reference to the runtime; state lives in
``core.worker_registry`` (P6) and ``core.job_manager`` (P5). OpenCode is the FIRST adapter and is never a
dependency (``core.worker.py:OpenCodeProvider`` already degrades to BLOCKED if absent).

Reuse, not rewrite: adapters wrap the existing providers (``core.worker``) + registry + lease.
"""
import contextlib
from typing import Any

# The doc §18 verb set - the canonical worker protocol surface.
ADAPTER_OPS = ("register", "heartbeat", "get_status", "accept_assignment",
               "start", "pause", "cancel", "report_result", "disconnect")


class WorkerAdapter:
    """Runtime-neutral adapter contract. Subclasses translate to a concrete runtime."""
    runtime = "base"
    description = ""

    def available(self) -> bool:
        return True

    # -- registration / liveness (delegate to core.worker_registry) --
    def register(self, scope: str, project: str | None, **meta) -> dict[str, Any]:
        from core import worker_registry
        return worker_registry.register(scope, project, runtime=self.runtime,
                                        capabilities=meta.get("capabilities") or [],
                                        role=str(meta.get("role") or ""),
                                        endpoint=str(meta.get("endpoint") or ""),
                                        workspace=str(meta.get("workspace") or ""),
                                        worker_id=str(meta.get("worker_id") or ""))

    def heartbeat(self, scope: str, project: str | None, worker_id: str, **kw) -> dict[str, Any]:
        from core import worker_registry
        return worker_registry.heartbeat(scope, project, worker_id, status=str(kw.get("status") or ""),
                                         current_assignment_id=str(kw.get("current_assignment_id") or ""))

    def get_status(self, scope: str, project: str | None, worker_id: str) -> dict[str, Any]:
        from core import worker_registry
        return worker_registry.get(scope, project, worker_id) or {"ok": False, "reason": "unknown worker"}

    def disconnect(self, scope: str, project: str | None, worker_id: str, *, revoke: bool = False) -> dict[str, Any]:
        from core import worker_registry
        return worker_registry.unregister(scope, project, worker_id, revoke=revoke)

    # -- assignment lifecycle (default: record intent on the registry; runtime-specific in subclasses) --
    def accept_assignment(self, scope: str, project: str | None, worker_id: str,
                          assignment_id: str) -> dict[str, Any]:
        return self.heartbeat(scope, project, worker_id, status="BUSY",
                              current_assignment_id=assignment_id)

    def start(self, scope: str, project: str | None, worker_id: str, objective: str = "",
              worktree: str = "") -> dict[str, Any]:
        raise NotImplementedError  # subclass: how the runtime starts the work

    def pause(self, scope: str, project: str | None, worker_id: str) -> dict[str, Any]:
        return self.heartbeat(scope, project, worker_id, status="PAUSED")

    def cancel(self, scope: str, project: str | None, worker_id: str) -> dict[str, Any]:
        return self.heartbeat(scope, project, worker_id, status="IDLE", current_assignment_id="")

    def report_result(self, scope: str, project: str | None, worker_id: str,
                      result: dict[str, Any]) -> dict[str, Any]:
        from core import worker
        # persist via the canonical worker-result store + task metrics (single writers)
        with contextlib.suppress(Exception):
            worker.record_result(scope, project, result or {})
        return self.heartbeat(scope, project, worker_id, status="IDLE", current_assignment_id="")


class OpenCodeAdapter(WorkerAdapter):
    """First adapter: an OpenCode session. Optional client - never a PF dependency."""
    runtime = "opencode"
    description = "OpenCode session adapter (optional client; degrades to BLOCKED if absent)"

    def available(self) -> bool:
        from core import worker
        p = worker._PROVIDERS.get("opencode")
        return bool(p and p.available())

    def start(self, scope: str, project: str | None, worker_id: str, objective: str = "",
              worktree: str = "") -> dict[str, Any]:
        from core import worker
        prov = worker._PROVIDERS.get("opencode")
        if prov is None or not prov.available():
            return {"ok": False, "status": "blocked",
                    "error": "opencode not installed (optional adapter; not a dependency)"}
        out = prov.run({"worktree": worktree, "objective": objective, "run_id": ""})
        return {"ok": bool(out.get("ok")), "status": out.get("status"), "output": out.get("output"),
                "error": out.get("error", "")}


class CommandAdapter(WorkerAdapter):
    """Local/test runtime: run a configured command in the worktree (exercises the contract offline)."""
    runtime = "command"
    description = "command adapter (run a command in the worktree; local/test runtime)"

    def start(self, scope: str, project: str | None, worker_id: str, objective: str = "",
              worktree: str = "", command: Any = None) -> dict[str, Any]:
        from core import worker
        prov = worker._PROVIDERS.get("command")
        if prov is None:
            return {"ok": False, "status": "blocked", "error": "command provider unavailable"}
        out = prov.run({"worktree": worktree, "command": command or objective, "timeout": 1800})
        return {"ok": bool(out.get("ok")), "status": out.get("status"), "output": out.get("output"),
                "error": out.get("error", "")}


class NativeAdapter(WorkerAdapter):
    """Declares PF's OWN native execution path for completeness.

    It does NOT route PF agents through the external worker scheduler (doc §43(d)). ``start`` simply
    signals that native execution is handled by the pipeline executor, not this registry.
    """
    runtime = "native"
    description = "PF-native execution path (declared; agents stay native - not routed through workers)"

    def start(self, scope: str, project: str | None, worker_id: str, objective: str = "",
              worktree: str = "") -> dict[str, Any]:
        return {"ok": True, "status": "native",
                "output": "native execution is handled by the PF pipeline executor (not the worker registry)"}


_ADAPTERS: dict[str, WorkerAdapter] = {a.runtime: a for a in
                                      (OpenCodeAdapter(), CommandAdapter(), NativeAdapter())}


def resolve(runtime: str) -> WorkerAdapter | None:
    return _ADAPTERS.get(str(runtime or "").strip().lower())


def list_adapters() -> list[dict[str, Any]]:
    return [{"runtime": a.runtime, "description": a.description, "available": bool(a.available()),
             "ops": list(ADAPTER_OPS)} for a in _ADAPTERS.values()]


def contract() -> dict[str, Any]:
    """The adapter contract surface (for docs/API)."""
    return {"ops": list(ADAPTER_OPS),
            "runtimes": [a.runtime for a in _ADAPTERS.values()],
            "note": "scheduler talks to this abstraction; OpenCode is one adapter, never a dependency"}
