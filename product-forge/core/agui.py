"""AG-UI typed event stream — projection of the canonical event bus (BI-0198).

Maps our canonical events (core.events) to AG-UI-compatible typed events so the dashboard/external
clients consume a standard stream with NO coupling to internals. Pure projection: reads the canonical
stream; owns NO store; never emits content/secrets (bounded).

Canonical -> AG-UI:
  run_started/run_completed/run_failed      -> RUN_STARTED / RUN_FINISHED / RUN_ERROR
  stage_started|agent_started               -> STEP_STARTED
  stage_completed|agent_completed           -> STEP_FINISHED
  stage_failed|agent_failed                 -> STEP_FINISHED (status=error)
  agent_stage_changed|plan_confirmed        -> STATE_DELTA
  tokens_used|gen_ai_call                   -> USAGE
  human_input_required|agent_blocked        -> CUSTOM
  *                                         -> CUSTOM (never dropped)

See docs/AGUI-DESIGN.md.
"""
from typing import Dict, List, Optional

_STEP_START = ("stage_started", "agent_started")
_STEP_END = ("stage_completed", "agent_completed")
_STEP_ERR = ("stage_failed", "agent_failed")
_STATE = ("agent_stage_changed", "plan_confirmed")
_USAGE = ("tokens_used", "gen_ai_call")


def _step_name(ev: Dict) -> str:
    return str(ev.get("agent") or ev.get("stage") or ev.get("type") or "")


def map_event(ev: Dict) -> Optional[Dict]:
    """Project one canonical event to an AG-UI typed event. Unknown => CUSTOM. Never raises."""
    try:
        t = str(ev.get("type") or "")
        base = {
            "threadId": str(ev.get("project") or ""),
            "runId": str(ev.get("trace_id") or ev.get("run_id") or ""),
            "timestamp": ev.get("ts") or ev.get("at") or "",
            "raw": t,
        }
        if t == "run_started":
            return {**base, "type": "RUN_STARTED"}
        if t == "run_completed":
            return {**base, "type": "RUN_FINISHED"}
        if t == "run_failed":
            return {**base, "type": "RUN_ERROR", "message": str(ev.get("message") or "run failed")}
        if t in _STEP_START:
            return {**base, "type": "STEP_STARTED", "step": _step_name(ev),
                    "stage": ev.get("stage", ""), "agent": ev.get("agent", "")}
        if t in _STEP_END:
            return {**base, "type": "STEP_FINISHED", "step": _step_name(ev), "status": "ok"}
        if t in _STEP_ERR:
            return {**base, "type": "STEP_FINISHED", "step": _step_name(ev), "status": "error",
                    "message": str(ev.get("message") or "")}
        if t in _STATE:
            return {**base, "type": "STATE_DELTA", "stage": ev.get("stage", ""),
                    "agent": ev.get("agent", "")}
        if t in _USAGE:
            return {**base, "type": "USAGE",
                    "input_tokens": int(ev.get("input_tokens") or 0),
                    "output_tokens": int(ev.get("output_tokens") or 0),
                    "model": str(ev.get("model") or "")}
        return {**base, "type": "CUSTOM", "event": t}
    except Exception:
        return None


def map_all(project_dir: str, run_id: str = "") -> List[Dict]:
    """Ordered typed AG-UI events from the canonical stream (optional run filter)."""
    out: List[Dict] = []
    try:
        from core import events
        for ev in events.read(project_dir):
            if run_id and str(ev.get("trace_id") or ev.get("run_id") or "") != run_id:
                continue
            m = map_event(ev)
            if m:
                m["threadId"] = m.get("threadId") or ""
                out.append(m)
    except Exception:
        pass
    return out


def types() -> List[str]:
    return ["RUN_STARTED", "RUN_FINISHED", "RUN_ERROR", "STEP_STARTED", "STEP_FINISHED",
            "STATE_DELTA", "USAGE", "CUSTOM"]
