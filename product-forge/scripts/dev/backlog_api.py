"""In-process Backlog API client (uses FastAPI TestClient against api.app:app).

Backlog writes stay API-only (through api/routers/backlog.py -> core.backlog single writer) but run IN-PROCESS:
NO server, NO URL/port, NO dependency on the local dev_server (:8010). Same endpoints, same guards (AC-at-create,
closure guard, envelope, revision guard).

Usage:
    from scripts.dev import backlog_api as ba
    item = ba.get_item("BI-PF-1234")
    ba.set_status("BI-PF-1234", "in_progress")
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

API = "/api/v1/backlog"


def _token() -> str:
    """Resolve the API token and ensure PF_API_TOKEN is set (the app reads it at request time)."""
    tok = os.environ.get("PF_API_TOKEN", "").strip()
    if not tok:
        try:
            tok = (ROOT / "data" / "local" / "dev-api-token").read_text(encoding="utf-8").strip()
        except Exception:
            tok = ""
        if tok:
            os.environ["PF_API_TOKEN"] = tok
    return tok


def client():
    """A TestClient over the real API app (in-process; no server, no URL/port)."""
    tok = _token()
    if not tok:
        # In-process internal caller with no token configured -> allow dev anon (same-process only).
        os.environ.setdefault("API_ALLOW_ANON", "1")
    from fastapi.testclient import TestClient
    from api.app import app
    return TestClient(app, headers={"Authorization": f"Bearer {tok}", "X-Roles": "operator"})


def _unwrap(resp):
    if resp.status_code >= 400:
        raise RuntimeError(f"API {resp.status_code}: {resp.text[:500]}")
    try:
        return resp.json().get("data")
    except Exception:
        return resp.text


def call(method: str, path: str, **kw):
    """Low-level: call an API path in-process. ``path`` is relative to /api/v1/backlog."""
    c = client()
    return _unwrap(getattr(c, method.lower())(f"{API}{path}", **kw))


def get_item(item_id: str, scope: str = "product_forge", project: str = "") -> dict:
    return call("get", f"/items/{item_id}", params={"scope": scope, "project": project}) or {}


def create_item(title: str, *, external_id: str = "", acceptance_criteria=None, epic: str = "",
                scope: str = "product_forge", project: str = "", **extra) -> dict:
    body = {"title": title, "external_id": external_id, "acceptance_criteria": list(acceptance_criteria or []),
            "scope": scope, "project": project, **extra}
    return call("post", "/items", json=body) or {}


def set_context(item_id: str, payload: dict, scope: str = "product_forge", project: str = "") -> dict:
    body = dict(payload)
    body.setdefault("scope", scope)
    body.setdefault("project", project)
    return call("post", f"/items/{item_id}/context", json=body) or {}


def set_api_impact(item_id: str, needs_api: bool, reason: str, routes=None,
                   scope: str = "product_forge", project: str = "") -> dict:
    body = {"needs_api": needs_api, "reason": reason, "routes": routes or [],
            "scope": scope, "project": project}
    return call("post", f"/items/{item_id}/api-impact", json=body) or {}


def set_status(item_id: str, status: str, scope: str = "product_forge", project: str = "", **extra) -> dict:
    body = {"status": status, "scope": scope, "project": project, **extra}
    return call("post", f"/items/{item_id}/status", json=body) or {}


def set_delivery(item_id: str, *, branch: str = "", merge_sha: str = "", commits=None, pr=None,
                 pr_url: str = "", scope: str = "product_forge", project: str = "") -> dict:
    body = {"branch": branch, "merge_sha": merge_sha, "commits": list(commits or []),
            "pr": str(pr or ""), "pr_url": pr_url, "scope": scope, "project": project}
    return call("post", f"/items/{item_id}/delivery", json=body) or {}


if __name__ == "__main__":
    import json as _json
    iid = sys.argv[1] if len(sys.argv) > 1 else "BI-PF-1429"
    print(_json.dumps(get_item(iid), indent=2)[:1200])
