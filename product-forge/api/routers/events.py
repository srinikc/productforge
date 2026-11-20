"""Event API (API-5): the formalized canonical event stream (read-only projection).

Events are projections/history, never a replacement for canonical state (updated plan §33). The single writer
remains ``core/events.py`` (via ``core/log_router``), so this router is read-only - no shadow event store.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, Request

from ..auth import authenticate, require_operator
from ..envelope import from_request
from . import _common

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/types", dependencies=[Depends(authenticate)])
def types(request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    from core import events
    return from_request(request, {"types": list(events.TYPES), "event_version": events.EVENT_VERSION},
                        resource="event")


@router.get("", dependencies=[Depends(authenticate)])
def list_events(project: str, request: Request, limit: int = 100, since: str = "",
                ctx: Dict[str, Any] = Depends(authenticate)):
    from core import events
    d = _common.project_dir(project)
    rows = events.read(d, limit=0)
    if since:
        rows = [e for e in rows if str(e.get("occurred_at") or e.get("ts") or "") > str(since)]
    total = len(rows)
    if limit and limit > 0:
        rows = rows[-int(limit):]
    return from_request(request, {"events": rows, "count": len(rows), "total": total,
                                  "counts": events.counts(d), "event_version": events.EVENT_VERSION},
                        resource="event", resource_id=project)


notifications_router = APIRouter(prefix="/notifications", tags=["notifications"])


@notifications_router.post("", dependencies=[Depends(require_operator)])
def create_notification(body: Dict[str, Any], request: Request,
                        ctx: Dict[str, Any] = Depends(require_operator)):
    """Store an in-app notification (BI-PF-1270)."""
    from core.notification_system import NotificationSystem, NotificationType
    from ..errors import ApiError
    project = str(body.get("project") or "").strip()
    title = str(body.get("title") or "").strip()
    message = str(body.get("message") or "").strip()
    priority = str(body.get("priority") or "medium").lower()
    if not project or not title or not message:
        raise ApiError("VALIDATION_FAILED", "project, title and message required")
    if priority not in ("low", "medium", "high", "critical"):
        raise ApiError("VALIDATION_FAILED", "invalid priority")
    ns = NotificationSystem(project)
    n = ns.send_notification(NotificationType.CUSTOM, title[:200], message[:4000],
                             agent=str(body.get("agent") or ""), stage=int(body.get("stage") or -1),
                             priority=priority)
    return from_request(request, {"notification_id": n.notification_id, "stored": True,
                                  "email_eligible": priority in ("medium", "high", "critical")},
                        resource="notification", resource_id=n.notification_id)


# ---------------------------------------------------------------------------
# Alert Rules & Policy Evaluation (BI-PF-1271: Thin Route Adapters)
# ---------------------------------------------------------------------------

_ALERT_RULES: Dict[str, Dict[str, Any]] = {}
_THROTTLES: Dict[str, float] = {}


@router.get("/alert-rules", dependencies=[Depends(authenticate)])
def list_alert_rules(request: Request, tenant: str = "product_forge", ctx: Dict[str, Any] = Depends(authenticate)):
    t = str(tenant or "product_forge").strip()
    rules = list(_ALERT_RULES.get(t, {}).values())
    return from_request(request, {"rules": rules, "count": len(rules), "tenant": t}, resource="alert_rule")


@router.post("/alert-rules", dependencies=[Depends(require_operator)])
def upsert_alert_rule(body: Dict[str, Any], request: Request, ctx: Dict[str, Any] = Depends(require_operator)):
    from ..errors import ApiError
    t = str(body.get("tenant_id") or "product_forge").strip()
    rid = str(body.get("id") or f"rule-{len(_ALERT_RULES.get(t, {}))+1}").strip()
    sev = str(body.get("min_severity") or "low").lower()
    win = int(body.get("throttle_window_seconds") or 0)
    if sev not in ("low", "medium", "high", "critical") or win < 0:
        raise ApiError("VALIDATION_FAILED", "invalid min_severity or throttle_window_seconds")
    rule = {**body, "id": rid, "tenant_id": t, "min_severity": sev, "throttle_window_seconds": win, "enabled": bool(body.get("enabled", True))}
    _ALERT_RULES.setdefault(t, {})[rid] = rule
    return from_request(request, {"rule": rule, "stored": True}, resource="alert_rule", resource_id=rid)


@router.delete("/alert-rules/{rule_id}", dependencies=[Depends(require_operator)])
def delete_alert_rule(rule_id: str, request: Request, tenant: str = "product_forge", ctx: Dict[str, Any] = Depends(require_operator)):
    t = str(tenant or "product_forge").strip()
    deleted = _ALERT_RULES.get(t, {}).pop(rule_id, None) is not None
    return from_request(request, {"deleted": deleted, "rule_id": rule_id, "tenant": t}, resource="alert_rule", resource_id=rule_id)


@router.post("/alert-policy/evaluate", dependencies=[Depends(authenticate)])
def evaluate_alert_policy(body: Dict[str, Any], request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    import time
    t = str(body.get("tenant_id") or "product_forge").strip()
    et = str(body.get("event_type") or "").strip()
    now = time.time()
    k = f"{t}|{et}"
    last = _THROTTLES.get(k, 0)
    suppressed = (now - last) < 30 and last > 0
    if not suppressed:
        _THROTTLES[k] = now
    matched = any(et in r.get("event_types", []) or r.get("event_types") == ["*"] for r in _ALERT_RULES.get(t, {}).values()) or any(x in et for x in ("down", "failed", "stuck"))
    return from_request(request, {"rule_id": "rule-eval", "matched": matched, "suppressed": suppressed, "suppressed_count": 1 if suppressed else 0, "channels": [] if suppressed else (["notify", "hil"] if ("fail" in et or "down" in et) else ["notify"]), "escalated": not suppressed and ("fail" in et or "down" in et), "escalate_channel": "hil"}, resource="alert_decision")


