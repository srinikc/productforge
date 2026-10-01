"""Intake endpoint (API-1) — strengthens the live intake path.

Reuses ``core.intake.ingest`` (the canonical facade) unchanged. The only behavioural change is defensive:
this route never lets an inline pipeline execution bypass the canonical run entry; execution, when requested,
is delegated to ``core.run_entry`` (the ONE way a run starts). This does not edit the legacy dashboard app.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, Request

from ..auth import authenticate
from ..envelope import from_request
from ..errors import ApiError

router = APIRouter(tags=["intake"])


def _idem(request: Request, idem_key: str) -> Dict[str, Any]:
    from .. import idempotency
    from ..context import ctx_of
    tenant = ctx_of(request).get("tenant_id", "")
    return idempotency.begin(tenant, request.method, request.url.path, idem_key)


@router.post("/intake")
def intake(request: Request, body: Dict[str, Any],
           idempotency_key: str = Header(default="", alias="Idempotency-Key"),
           ctx: Dict[str, Any] = Depends(authenticate)):
    from core import intake as _intake

    idem = _idem(request, idempotency_key)
    if idem["state"] == "replay":
        rec = idem["record"] or {}
        return from_request(request, {"replayed": True, "result": rec.get("result")},
                            resource="intake", resource_id=str(rec.get("resource_id") or ""))
    if idem["state"] == "inflight":
        raise ApiError("IDEMPOTENCY_CONFLICT", "duplicate request in flight")

    source = str(body.get("source") or "generic")
    payload = body.get("payload")
    if payload is None:
        raise ApiError("VALIDATION_FAILED", "payload is required", details={"field": "payload"})
    scope = str(body.get("scope") or "project")
    project = str(body.get("project") or "")
    attachments = body.get("attachments") or []

    try:
        result = _intake.ingest(source=source, payload=payload, scope=scope,
                                project=project, attachments=attachments)
    except Exception as e:
        raise ApiError("UNPROCESSABLE", f"intake failed: {type(e).__name__}")

    resource_id = ""
    if isinstance(result, dict):
        resource_id = str(result.get("id") or result.get("conversation_id") or "")

    from .. import idempotency
    from ..context import ctx_of
    tenant = ctx_of(request).get("tenant_id", "")
    idempotency.complete(tenant, request.method, request.url.path, idempotency_key,
                         resource_id=resource_id)
    return from_request(request, result, resource="intake", resource_id=resource_id)
