"""Canonical run-lifecycle event taxonomy — ONE schema emitted by the pipeline backend,
consumed by analytics (dashboard). Append-only JSONL per project: events.jsonl.

Event types (canonical):
  run_started · run_completed · run_failed
  stage_started · stage_completed · stage_failed
  agent_started · agent_completed · agent_stage_changed
  human_input_required · tokens_used

Owner: this module (single writer). Wired: run_entry (run_*), stage_runner (stage_*/agent_*).
"""
import json
import os
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


def emit(project_dir: str, event_type: str, *, run_id: str = "", stage: str = "",
         agent: str = "", **fields) -> Optional[Dict]:
    """Append one canonical event. Best-effort (never raises)."""
    try:
        ev = {"ts": datetime.now().isoformat(timespec="seconds"),
              "type": str(event_type), "level": "INFO", "run_id": run_id, "stage": stage,
              "agent": agent, "trace_id": str(run_id or ""), "span_id": _span_id()}
        ev.update({k: v for k, v in fields.items() if v not in (None, "")})
        # BI-PF-0233: route the append through log_router (single owner of paths + writes).
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


def _main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Run-lifecycle events")
    ap.add_argument("--project", required=True)
    ap.add_argument("--limit", type=int, default=20)
    a = ap.parse_args(argv)
    pj = os.path.join("products", a.project)
    print(json.dumps({"counts": counts(pj), "recent": read(pj, a.limit)}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
