"""Canonical run-lifecycle event taxonomy â€” ONE schema emitted by the pipeline backend,
consumed by analytics (dashboard). Append-only JSONL per project: events.jsonl.

Event types (canonical):
  run_started Â· run_completed Â· run_failed
  stage_started Â· stage_completed Â· stage_failed
  agent_started Â· agent_completed Â· agent_stage_changed
  human_input_required Â· tokens_used

Owner: this module (single writer). Wired: run_entry (run_*), stage_runner (stage_*/agent_*).
"""
import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional

TYPES = ("run_started", "run_completed", "run_failed",
         "stage_started", "stage_completed", "stage_failed",
         "agent_started", "agent_completed", "agent_failed", "agent_blocked",
         "agent_heartbeat", "plan_confirmed", "agent_stage_changed",
         "readiness_failed", "brief_insufficient", "human_input_required", "tokens_used",
         "gen_ai_call")

FILENAME = "events.jsonl"


def _span_id() -> str:
    try:
        from core import tracing
        return tracing.new_span_id()
    except Exception:
        return ""


def path(project_dir: str) -> str:
    return os.path.join(project_dir, FILENAME)


EVENT_VERSION = "1"


def emit(project_dir: str, event_type: str, *, run_id: str = "", stage: str = "",
         agent: str = "", correlation_id: str = "", causation_id: str = "",
         task_id: str = "", worker_id: str = "", actor: str = "", **fields) -> Optional[Dict]:
    """Append one canonical event. Best-effort (never raises).

    API-5 / BI-PF-1272: carries the formal event envelope (event_id, event_version, occurred_at,
    correlation_id, causation_id, task_id, worker_id, actor, payload) **additively** - the legacy
    flat fields (ts/type/level/run_id/stage/agent/trace_id/span_id) are kept for back-compat.
    Delegates to the Go event authority (go_host.event_append) for monotonic seq assignment,
    with automatic fallback to local JSONL append if Go core is unavailable.
    """
    try:
        now = datetime.now().isoformat(timespec="seconds")
        extra = {k: v for k, v in fields.items() if v not in (None, "")}
        ev = {"event_id": uuid.uuid4().hex, "event_type": str(event_type), "event_version": EVENT_VERSION,
              "occurred_at": now, "tenant_id": "", "project_id": os.path.basename(os.path.normpath(project_dir)),
              "run_id": run_id, "stage_id": stage, "task_id": task_id, "worker_id": worker_id,
              "actor": actor, "correlation_id": correlation_id or str(run_id or ""),
              "causation_id": causation_id, "payload": extra,
              # legacy flat fields (back-compat)
              "ts": now, "type": str(event_type), "level": "INFO", "stage": stage,
              "agent": agent, "trace_id": str(run_id or ""), "span_id": _span_id()}
        ev.update(extra)
        # BI-PF-1272: Delegate to Go event authority via A1 wire seam (go_host.event_append)
        appended = False
        try:
            from core import go_host
            target_path = path(project_dir)
            resp = go_host.event_append(target_path, ev)
            if isinstance(resp, dict) and resp.get("ok"):
                res_data = resp.get("result") or {}
                if isinstance(res_data, dict) and "seq" in res_data:
                    ev["seq"] = res_data["seq"]
                appended = True
        except Exception:
            appended = False

        if not appended:
            # Fallback strangler path: preserve local JSONL append if Go host is unavailable
            try:
                from core import log_router as _lr
                _lr.append_jsonl(_lr.run_events_path(project_dir), ev)
            except Exception:
                p = path(project_dir)
                os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
                with open(p, "a", encoding="utf-8") as f:
                    f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        return ev
    except Exception:
        return None


def read(project_dir: str, limit: int = 0) -> List[Dict]:
    out: List[Dict] = []
    try:
        for line in open(path(project_dir), encoding="utf-8", errors="ignore"):
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    except Exception:
        return []
    return out[-limit:] if limit else out


def counts(project_dir: str) -> Dict[str, int]:
    c: Dict[str, int] = {}
    for e in read(project_dir):
        c[e.get("type", "?")] = c.get(e.get("type", "?"), 0) + 1
    return c


def _bus_pid_file(project: Optional[str] = None) -> str:
    return os.path.join("products", project, ".events", "bus.pid") if project else os.path.join("products", ".events", "bus.pid")


def bus_status(project: Optional[str] = None) -> Dict[str, Any]:
    """Query event bus daemon status (BI-PF-1275)."""
    import time
    pf = _bus_pid_file(project)
    if os.path.isfile(pf):
        try:
            d = json.loads(open(pf, encoding="utf-8").read())
            pid, t0 = int(d.get("pid") or 0), float(d.get("started_at") or 0)
            from core.capacity import _pid_alive
            if _pid_alive(pid):
                return {"running": True, "pid": pid, "uptime_seconds": int(max(0, time.time() - t0)) if t0 else 0, "status": "running"}
            os.remove(pf)
        except Exception:
            pass
    return {"running": False, "pid": None, "uptime_seconds": 0, "status": "stopped"}


def start_bus(project: Optional[str] = None) -> Dict[str, Any]:
    """Idempotently launch the event bus daemon under PID lock (BI-PF-1275)."""
    import subprocess, sys, time
    st = bus_status(project)
    if st.get("running"):
        return {"ok": True, "pid": st.get("pid"), "already_running": True, "status": "running"}
    pf = _bus_pid_file(project)
    os.makedirs(os.path.dirname(pf), exist_ok=True)
    fl = (subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000008) if os.name == "nt" else 0
    try:
        proc = subprocess.Popen([sys.executable, "-m", "core.events", "--daemon"], creationflags=fl)
        with open(pf, "w", encoding="utf-8") as f:
            json.dump({"pid": proc.pid, "started_at": time.time(), "project": project or ""}, f)
        return {"ok": True, "pid": proc.pid, "already_running": False, "status": "running"}
    except Exception as e:
        return {"ok": False, "error": str(e), "status": "failed"}


def stop_bus(project: Optional[str] = None) -> Dict[str, Any]:
    """Gracefully terminate live event bus daemon (BI-PF-1275)."""
    pf, stopped = _bus_pid_file(project), []
    if os.path.isfile(pf):
        try:
            pid = int(json.loads(open(pf, encoding="utf-8").read()).get("pid") or 0)
            from core.capacity import _pid_alive
            if _pid_alive(pid):
                import subprocess
                subprocess.run(["taskkill", "/PID", str(pid), "/T"], capture_output=True) if os.name == "nt" else os.kill(pid, 15)

                stopped.append(pid)
            os.remove(pf)
        except Exception:
            pass
    return {"ok": True, "stopped": stopped, "status": "stopped"}


def _main(argv=None) -> int:
    import argparse, time
    ap = argparse.ArgumentParser(description="Run-lifecycle events")
    ap.add_argument("--project", default=""); ap.add_argument("--limit", type=int, default=20); ap.add_argument("--daemon", action="store_true")
    a = ap.parse_args(argv)
    if a.daemon:
        while True:
            time.sleep(60)
    pj = os.path.join("products", a.project) if a.project else "products"
    print(json.dumps({"counts": counts(pj), "recent": read(pj, a.limit)}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
