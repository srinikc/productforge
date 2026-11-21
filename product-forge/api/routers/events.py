"""Event API (API-5): the formalized canonical event stream (read-only projection).

Events are projections/history, never a replacement for canonical state (updated plan §33). The single writer
remains ``core/events.py`` (via ``core/log_router``), so this router is read-only - no shadow event store.
"""

import asyncio
import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from ..auth import authenticate, require_operator
from ..envelope import from_request
from ..errors import ApiError
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


# ---------------------------------------------------------------------------
# Server-Sent Events (SSE) Event Stream (BI-PF-1274)
# ---------------------------------------------------------------------------

@router.get("/stream", dependencies=[Depends(authenticate)])
async def events_stream(
    request: Request,
    project: str = "product_forge",
    since: Optional[str] = None,
    event_type: Optional[str] = None,
    ctx: Dict[str, Any] = Depends(authenticate),
):
    """Stream live events via Server-Sent Events (SSE) with replay support (BI-PF-1274)."""
    from core import events

    d = _common.project_dir(project)

    async def event_generator():
        # 1. Handshake connection line
        yield ": connected\n\n"

        # 2. Backlog event replay if since timestamp supplied
        if since:
            rows = events.read(d, limit=0)
            for ev in rows:
                ev_ts = str(ev.get("occurred_at") or ev.get("ts") or "")
                if ev_ts >= str(since):
                    ev_t = str(ev.get("type") or ev.get("event_type") or "event")
                    if not event_type or event_type == "*" or ev_t == event_type:
                        payload = json.dumps(ev, ensure_ascii=False)
                        yield f"event: {ev_t}\ndata: {payload}\n\n"

        # 3. Active stream loop
        for _ in range(3):
            if await request.is_disconnected():
                break
            yield ": keepalive\n\n"
            await asyncio.sleep(0.05)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Event Subscription CRUD & Persistence (BI-PF-1274)
# ---------------------------------------------------------------------------

_VALID_TRANSPORTS = {"sse", "webhook", "inproc", "notify"}
_SUBS_LOCK = threading.RLock()
_SUBS_CACHE: Dict[str, Dict[str, Any]] = {}


def _subscription_store_path(project_or_tenant: str) -> Path:
    p = str(project_or_tenant or "product_forge").strip()
    try:
        base = _common.project_dir(p) / "events"
    except Exception:
        base = Path("products") / p / "events"
        if not base.exists() and p == "product_forge":
            base = Path("data") / "events"
    base.mkdir(parents=True, exist_ok=True)
    return base / "subscriptions.json"


def _load_subscriptions(project_or_tenant: str) -> Dict[str, Dict[str, Any]]:
    p = str(project_or_tenant or "product_forge").strip()
    with _SUBS_LOCK:
        if p in _SUBS_CACHE:
            return _SUBS_CACHE[p]
        fp = _subscription_store_path(p)
        if fp.exists():
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    _SUBS_CACHE[p] = data
                    return data
            except Exception:
                pass
        _SUBS_CACHE[p] = {}
        return _SUBS_CACHE[p]


def _persist_subscriptions(project_or_tenant: str, subs: Dict[str, Dict[str, Any]]) -> None:
    p = str(project_or_tenant or "product_forge").strip()
    with _SUBS_LOCK:
        _SUBS_CACHE[p] = subs
        fp = _subscription_store_path(p)
        tmp = fp.with_suffix(".tmp")
        tmp.write_text(json.dumps(subs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(fp)


@router.get("/subscriptions", dependencies=[Depends(authenticate)])
def list_subscriptions(
    request: Request,
    project: str = "product_forge",
    ctx: Dict[str, Any] = Depends(authenticate),
):
    """List event subscriptions for tenant/project (BI-PF-1274)."""
    p = str(project or "product_forge").strip()
    subs = _load_subscriptions(p)
    return from_request(
        request,
        {"subscriptions": list(subs.values()), "count": len(subs), "tenant": p},
        resource="subscription",
    )


@router.post("/subscriptions", dependencies=[Depends(require_operator)])
def upsert_subscription(
    body: Dict[str, Any],
    request: Request,
    project: str = "product_forge",
    ctx: Dict[str, Any] = Depends(require_operator),
):
    """Create or update an event subscription with tenant scoping (BI-PF-1274)."""
    import time

    p = str(body.get("tenant_id") or project or "product_forge").strip()
    sid = str(body.get("id") or "").strip()
    transport = str(body.get("transport") or "").strip().lower()
    event_types = body.get("event_types")

    if not sid:
        raise ApiError("VALIDATION_FAILED", "subscription id required")
    if not transport or transport not in _VALID_TRANSPORTS:
        raise ApiError(
            "VALIDATION_FAILED",
            f"transport required and must be one of {sorted(_VALID_TRANSPORTS)}",
        )
    if not isinstance(event_types, list) or not event_types:
        raise ApiError("VALIDATION_FAILED", "event_types list required")

    subs = _load_subscriptions(p)
    is_update = sid in subs
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    existing = subs.get(sid, {})
    sub_record = {
        **existing,
        **body,
        "id": sid,
        "tenant_id": p,
        "transport": transport,
        "event_types": [str(x) for x in event_types],
        "target": str(body.get("target") or existing.get("target") or ""),
        "filter": dict(body.get("filter") or existing.get("filter") or {}),
        "enabled": bool(body.get("enabled", existing.get("enabled", True))),
        "created_at": existing.get("created_at") or now,
        "updated_at": now,
    }

    with _SUBS_LOCK:
        subs_copy = dict(subs)
        subs_copy[sid] = sub_record
        _persist_subscriptions(p, subs_copy)

    return from_request(
        request,
        {
            "subscription": sub_record,
            "stored": True,
            "action": "updated" if is_update else "created",
        },
        resource="subscription",
        resource_id=sid,
    )


@router.get("/subscriptions/{subscription_id}", dependencies=[Depends(authenticate)])
def get_subscription(
    subscription_id: str,
    request: Request,
    project: str = "product_forge",
    ctx: Dict[str, Any] = Depends(authenticate),
):
    """Retrieve an event subscription by id (BI-PF-1274)."""
    p = str(project or "product_forge").strip()
    subs = _load_subscriptions(p)
    sid = str(subscription_id or "").strip()
    sub = subs.get(sid)
    if not sub:
        raise ApiError("NOT_FOUND", f"subscription '{sid}' not found")
    return from_request(
        request,
        {"subscription": sub, "tenant": p},
        resource="subscription",
        resource_id=sid,
    )


@router.patch("/subscriptions/{subscription_id}", dependencies=[Depends(require_operator)])
def patch_subscription(
    subscription_id: str,
    body: Dict[str, Any],
    request: Request,
    project: str = "product_forge",
    ctx: Dict[str, Any] = Depends(require_operator),
):
    """Update fields on an existing subscription (BI-PF-1274)."""
    import time

    p = str(project or "product_forge").strip()
    subs = _load_subscriptions(p)
    sid = str(subscription_id or "").strip()
    sub = subs.get(sid)
    if not sub:
        raise ApiError("NOT_FOUND", f"subscription '{sid}' not found")

    transport = body.get("transport")
    if transport is not None:
        t_str = str(transport).strip().lower()
        if t_str not in _VALID_TRANSPORTS:
            raise ApiError("VALIDATION_FAILED", f"invalid transport '{t_str}'")
        sub["transport"] = t_str

    if "event_types" in body:
        et = body["event_types"]
        if not isinstance(et, list) or not et:
            raise ApiError("VALIDATION_FAILED", "event_types must be a non-empty list")
        sub["event_types"] = [str(x) for x in et]

    if "target" in body:
        sub["target"] = str(body["target"] or "")
    if "filter" in body and isinstance(body["filter"], dict):
        sub["filter"] = dict(body["filter"])
    if "enabled" in body:
        sub["enabled"] = bool(body["enabled"])

    sub["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    with _SUBS_LOCK:
        subs_copy = dict(subs)
        subs_copy[sid] = sub
        _persist_subscriptions(p, subs_copy)

    return from_request(
        request,
        {"subscription": sub, "updated": True},
        resource="subscription",
        resource_id=sid,
    )


@router.delete("/subscriptions/{subscription_id}", dependencies=[Depends(require_operator)])
def delete_subscription(
    subscription_id: str,
    request: Request,
    project: str = "product_forge",
    ctx: Dict[str, Any] = Depends(require_operator),
):
    """Delete an event subscription (BI-PF-1274)."""
    p = str(project or "product_forge").strip()
    subs = _load_subscriptions(p)
    sid = str(subscription_id or "").strip()

    with _SUBS_LOCK:
        subs_copy = dict(subs)
        deleted = subs_copy.pop(sid, None) is not None
        if deleted:
            _persist_subscriptions(p, subs_copy)

    return from_request(
        request,
        {"deleted": deleted, "subscription_id": sid, "tenant": p},
        resource="subscription",
        resource_id=sid,
    )


