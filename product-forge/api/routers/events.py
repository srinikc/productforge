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
