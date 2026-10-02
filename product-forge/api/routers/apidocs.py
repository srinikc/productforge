"""API reference surface (BI-PF-0355): serve + render the canonical API reference.

Maps to ``core.api_docs`` (generated from the canonical OpenAPI). Read-only JSON + HTML; PDF/HTML rendering is
operator-gated. The reference is generated, never hand-edited.
"""
import os
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from ..auth import authenticate, require_operator
from ..envelope import from_request
from ..errors import ApiError

router = APIRouter(prefix="/apidocs", tags=["apidocs"])


@router.get(".json", dependencies=[Depends(authenticate)])
def apidocs_json(request: Request, ctx: dict[str, Any] = Depends(authenticate)):
    from core import api_docs
    return from_request(request, api_docs.reference(), resource="apidocs")


@router.get("", response_class=HTMLResponse, dependencies=[Depends(authenticate)])
def apidocs_html(ctx: dict[str, Any] = Depends(authenticate)):
    from core import api_docs
    return HTMLResponse(api_docs.render_html(api_docs.reference()))


@router.post("/render", dependencies=[Depends(require_operator)])
def render(body: dict[str, Any], request: Request,
           ctx: dict[str, Any] = Depends(require_operator)):
    from core import api_docs
    fmt = str(body.get("format") or "html").lower()
    if fmt == "html":
        path = api_docs.write_html()
        return from_request(request, {"format": "html", "path": os.path.relpath(path, _root())},
                            resource="apidocs", status="ok")
    if fmt == "pdf":
        out = os.path.join(os.path.dirname(api_docs.HTML_PATH), "api-reference.pdf")
        res = api_docs.render_pdf(out)
        if not res.get("ok"):
            raise ApiError("DEPENDENCY_UNAVAILABLE", res.get("reason") or "pdf unavailable")
        return from_request(request, {"format": "pdf", "path": os.path.relpath(res["path"], _root()),
                                      "backend": res.get("backend", "")},
                            resource="apidocs", status="ok")
    raise ApiError("VALIDATION_FAILED", "format must be html or pdf", details={"format": fmt})


def _root() -> str:
    from core.paths import ROOT
    return ROOT
