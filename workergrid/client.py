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
    return (os.environ.get("WORKERGRID_PF_API_URL", "").strip()
            or str(_cfg.load().get("pf_api_url") or "http://127.0.0.1:8000")).rstrip("/")


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
    req.add_header("X-Roles", os.environ.get("WORKERGRID_ROLES", "worker,operator"))
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


def eligible(scope: str = "product_forge", project: str = "", epic: str = "") -> dict:
    q = f"/api/v1/engineering/schedule/eligible?scope={scope}&project={project}"
    if epic:
        q += f"&epic={epic}"
    return call("GET", q)


def next_item(scope: str = "product_forge", project: str = "", epic: str = "") -> dict:
    q = f"/api/v1/engineering/schedule/next?scope={scope}&project={project}"
    if epic:
        q += f"&epic={epic}"
    return call("GET", q)


def set_status(item_id: str, status: str, note: str = "") -> dict:
    return call("POST", f"/api/v1/backlog/items/{item_id}/status", {"status": status, "note": note})


def backlog_list(scope: str = "product_forge", project: str = "") -> dict:
    return call("GET", f"/api/v1/backlog?scope={scope}&project={project}")


# ── Assignment lifecycle (ADR-0003: PF owns per-item assignment; BI-PF-1242) ──
def pf_data(env):
    """Unwrap the producer's canonical envelope one level: ``{status, data:{...}}`` -> the inner data."""
    if isinstance(env, dict) and "data" in env:
        d = env.get("data")
        if isinstance(d, dict):
            return d
    return env if isinstance(env, dict) else {}


def claim_assignment(scope: str = "product_forge", project: str = "", worker_id: str = "",
                     lease_seconds: int = 0, epic: str = "") -> dict:
    """Atomically claim the next eligible item; PF returns the assignment package (worktree/branch/context)."""
    body = {"scope": scope, "project": project, "worker_id": worker_id, "lease_seconds": lease_seconds}
    if epic:
        body["epic"] = epic
    return call("POST", "/api/v1/engineering/assignments/claim", body)


def complete_assignment(item_id: str, *, scope: str = "product_forge", project: str = "",
                        status: str = "verifying", note: str = "",
                        usage: dict | None = None) -> dict:
    """Report the assignment done (PF then runs its delivery lane: push -> PR -> merge -> push)."""
    body = {"scope": scope, "project": project, "status": status, "note": note}
    if usage:
        body["usage"] = usage
    return call("POST", f"/api/v1/engineering/assignments/{item_id}/complete", body)


def fail_assignment(item_id: str, *, scope: str = "product_forge", project: str = "",
                    reason: str = "", usage: dict | None = None) -> dict:
    body = {"scope": scope, "project": project, "reason": reason}
    if usage:
        body["usage"] = usage
    return call("POST", f"/api/v1/engineering/assignments/{item_id}/fail", body)


def release_assignment(item_id: str, *, scope: str = "product_forge", project: str = "",
                       reason: str = "released") -> dict:
    """Requeue the item (clears the lease; keeps the branch)."""
    return call("POST", f"/api/v1/engineering/assignments/{item_id}/release",
                {"scope": scope, "project": project, "reason": reason})


def heartbeat_assignment(item_id: str, *, scope: str = "product_forge", project: str = "",
                         lease_seconds: int = 0) -> dict:
    return call("POST", f"/api/v1/engineering/assignments/{item_id}/heartbeat",
                {"scope": scope, "project": project, "lease_seconds": lease_seconds})


def assignments(scope: str = "product_forge", project: str = "") -> dict:
    """Active assignments (workers -> items) read-model."""
    return call("GET", f"/api/v1/engineering/assignments?scope={scope}&project={project}")


# ── WorkerGrid service (coordinator) ────────────────────────────────────────
def service_url() -> str:
    cfg = _cfg.load()
    u = str(cfg.get("service_url") or "").strip()
    if u:
        return u.rstrip("/")
    return f"http://{cfg.get('service_host') or '127.0.0.1'}:{int(cfg.get('service_port') or 8790)}"


def svc(method: str, path: str, body: dict | None = None, timeout: int = 15) -> dict:
    """Call the WorkerGrid coordinator service. Returns ``{ok, status, data|error}`` (never raises)."""
    url = service_url() + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method.upper())
    req.add_header("Content-Type", "application/json")
    tok = _token()
    if tok:
        req.add_header("Authorization", f"Bearer {tok}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {"ok": True, "status": r.status, "data": _unwrap(r.read().decode("utf-8", errors="ignore"))}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "error": _unwrap(e.read().decode("utf-8", errors="ignore"))}
    except Exception as e:
        return {"ok": False, "status": 0, "error": f"{type(e).__name__}: {e}"}


def service_up() -> bool:
    return bool(svc("GET", "/status", timeout=2).get("ok"))
