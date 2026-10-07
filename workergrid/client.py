"""WorkerGrid → producer API client (thin HTTP; no third-party deps).

WorkerGrid is producer-agnostic: it reads *work* from a producer's API and writes execution status back.
For Product Forge the producer API base is ``pf_api_url`` (config.json). Auth: bearer token from
``token_env`` (default ``API_TOKEN``); if unset and the producer allows anonymous (dev), calls proceed.

This is the ONLY coupling to a producer: an HTTP contract. No producer code is imported.
"""
import json
import os
import urllib.error
import urllib.request

try:
    from . import _cfg  # type: ignore
except Exception:  # executed as a script
    import _cfg  # type: ignore


def _base() -> str:
    return str(_cfg.load().get("pf_api_url") or "http://127.0.0.1:8000").rstrip("/")


def _token() -> str:
    cfg = _cfg.load()
    return os.environ.get(str(cfg.get("token_env") or "API_TOKEN"), "").strip() \
        or os.environ.get("WORKERGRID_TOKEN", "").strip()


def call(method: str, path: str, body: dict | None = None, timeout: int = 30) -> dict:
    """Call the producer API. Returns ``{ok, status, data|error}`` (never raises)."""
    url = _base() + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method.upper())
    req.add_header("Content-Type", "application/json")
    tok = _token()
    if tok:
        req.add_header("Authorization", f"Bearer {tok}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", errors="ignore")
            return {"ok": True, "status": r.status, "data": _unwrap(raw)}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="ignore")
        return {"ok": False, "status": e.code, "error": _unwrap(raw)}
    except Exception as e:
        return {"ok": False, "status": 0, "error": f"{type(e).__name__}: {e}"}


def _unwrap(raw: str):
    try:
        return json.loads(raw)
    except Exception:
        return raw


def eligible(scope: str = "product_forge", project: str = "") -> dict:
    q = f"/api/v1/engineering/schedule/eligible?scope={scope}&project={project}"
    return call("GET", q)


def next_item(scope: str = "product_forge", project: str = "") -> dict:
    q = f"/api/v1/engineering/schedule/next?scope={scope}&project={project}"
    return call("GET", q)


def set_status(item_id: str, status: str, note: str = "") -> dict:
    return call("POST", f"/api/v1/backlog/items/{item_id}/status", {"status": status, "note": note})


def backlog_list(scope: str = "product_forge", project: str = "") -> dict:
    return call("GET", f"/api/v1/backlog?scope={scope}&project={project}")
