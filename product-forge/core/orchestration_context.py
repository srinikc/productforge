"""Orchestration context + Coordinator routing (BI-0020).

Builds the context the Coordinator (the `orchestrator` agent, AKA judgement plane) needs:
recent events, backlog exceptions, open defects, budget state — then routes a signal to a
decision. Routing is policy-first (deterministic, cheap) with an optional Coordinator-LLM
escalation; HIL/auto handling is explicit.
"""
import os
from typing import Any, Dict, List, Optional

_POLICY = {
    # kind                  -> (action, priority, escalate_to_coordinator)
    "stuck":                 ("retry_with_backoff", "high", False),
    "anomaly":               ("quarantine_and_analyze", "high", True),
    "compliance_exhausted":  ("request_hil_decision", "critical", True),
    "agent_conflict":        ("coordinator_arbitrate", "high", True),
    "coverage_gap":          ("generate_missing_tests", "medium", False),
    "scope_change":          ("request_hil_decision", "high", True),
    "escalation":            ("notify_and_pause", "critical", True),
    "follow_up_due":         ("notify_owner", "low", False),
}


def build(project: str = "", limit: int = 50) -> Dict:
    from core import event_bus
    ctx: Dict[str, Any] = {"project": project,
                           "events": event_bus.recent(limit),
                           "generated_at": __import__("datetime").datetime.now().isoformat()}
    try:
        from core import backlog
        scope = "project" if project else "product_forge"
        ctx["backlog_exceptions"] = [
            {"id": i["id"], "status": i["status"], "title": i.get("title", "")}
            for i in backlog.list_open(scope, project or None, order=False)
            if i.get("status") in ("blocked", "escalated", "needs_retry")
        ]
    except Exception:
        ctx["backlog_exceptions"] = []
    try:
        from core.defect_loop import open_defects
        ctx["open_defects"] = len(open_defects(project)) if project else 0
    except Exception:
        ctx["open_defects"] = 0
    return ctx


def route(event: Dict, use_coordinator: bool = False) -> Dict:
    """Route an event to a decision. Policy first; Coordinator LLM only if asked."""
    kind = str((event or {}).get("kind", ""))
    action, priority, escalate = _POLICY.get(kind, ("log_only", "low", False))
    decision = {"kind": kind, "action": action, "priority": priority,
                "escalate": escalate, "at": __import__("datetime").datetime.now().isoformat()}
    if use_coordinator and escalate:
        try:
            # Judgement plane: hand to the Coordinator (orchestrator agent) when wired.
            from core.orchestrator.agent_runner import AgentRunner  # type: ignore
            decision["coordinator"] = "available"
        except Exception:
            decision["coordinator"] = "unavailable_policy_used"
    # Surface as a notification/backlog signal (never raises).
    try:
        if kind in ("escalation", "compliance_exhausted"):
            from core import event_bus
            event_bus.emit("follow_up_due", reason=f"{kind}: {action}", source=event.get("at"))
    except Exception:
        pass
    return decision


def handle(event: Dict, project: str = "") -> Dict:
    return {"context": build(project), "decision": route(event)}
