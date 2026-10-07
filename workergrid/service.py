"""WorkerGrid coordinator service (stdlib HTTP; no deps). Stage 2b.

A running service holding the **shared** coordination state (workers, leases). Workers and operators query it
over host:port + bearer token. It reads *work* from a producer's backlog API and assigns it (claim + lease).

Endpoints (JSON):
  POST /workers/register {worker_id?, runtime, capabilities[], role}
  GET  /workers | GET /workers/{id}
  POST /workers/{id}/heartbeat {status, current_assignment}
  POST /workers/{id}/unregister
  POST /work {worker_id, runtime?, scope?, project?}          -> claim next eligible item + lease
  POST /leases/{id}/renew | /leases/{id}/release | /leases/recover
  GET  /status
Auth: Authorization: Bearer <token> (token from config token_env; if unset, anonymous allowed for dev).
Run: ``python workergrid/wg.py serve``.
"""
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _cfg  # noqa: E402
import client  # noqa: E402
import store  # noqa: E402


def _token() -> str:
    cfg = _cfg.load()
    return os.environ.get(str(cfg.get("token_env") or "API_TOKEN"), "").strip() \
        or os.environ.get("WORKERGRID_TOKEN", "").strip()


class Handler(BaseHTTPRequestHandler):
    server_version = "WorkerGrid/2b"

    def log_message(self, *a):  # quieter
        pass

    def _send(self, code: int, obj) -> None:
        body = json.dumps(obj, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth_ok(self) -> bool:
        tok = _token()
        if not tok:
            return True  # dev: no token configured
        h = self.headers.get("Authorization", "")
        return h == f"Bearer {tok}"

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8")) or {}
        except Exception:
            return {}

    def _route(self, method: str) -> None:
        if not self._auth_ok():
            return self._send(401, {"error": "unauthorized"})
        p = self.path.split("?", 1)[0]
        body = self._body() if method == "POST" else {}

        if p == "/status" and method == "GET":
            return self._send(200, {"workers": len(store.list_workers()),
                                    "leases": len(store.list_leases()),
                                    "producer": client._base()})
        if p == "/workers" and method == "GET":
            return self._send(200, {"workers": store.list_workers()})
        if p == "/workers/register" and method == "POST":
            return self._send(200, store.register(str(body.get("worker_id") or ""),
                                                  runtime=str(body.get("runtime") or ""),
                                                  capabilities=body.get("capabilities") or [],
                                                  role=str(body.get("role") or "")))
        m = re.match(r"^/workers/([^/]+)$", p)
        if m and method == "GET":
            w = store.get(m.group(1))
            return self._send(200 if w else 404, w or {"error": "not found"})
        m = re.match(r"^/workers/([^/]+)/heartbeat$", p)
        if m and method == "POST":
            return self._send(200, store.heartbeat(m.group(1), status=str(body.get("status") or ""),
                                                   current_assignment=str(body.get("current_assignment") or "")))
        m = re.match(r"^/workers/([^/]+)/unregister$", p)
        if m and method == "POST":
            return self._send(200, store.unregister(m.group(1)))
        if p == "/work" and method == "POST":
            return self._send(200, self._assign(body))
        m = re.match(r"^/leases/([^/]+)/renew$", p)
        if m and method == "POST":
            return self._send(200, store.renew(m.group(1)))
        m = re.match(r"^/leases/([^/]+)/release$", p)
        if m and method == "POST":
            return self._send(200, store.release(m.group(1)))
        if p == "/leases/recover" and method == "POST":
            return self._send(200, store.recover_expired())
        return self._send(404, {"error": "not found"})

    def _assign(self, body: dict) -> dict:
        wid = str(body.get("worker_id") or "")
        if not wid or not store.get(wid):
            return {"assigned": False, "reason": "worker not registered"}
        scope = str(body.get("scope") or "product_forge")
        project = str(body.get("project") or "")
        r = client.next_item(scope, project)
        data = r.get("data") or {}
        item = data.get("item")
        if not r.get("ok") or not data.get("found") or not item:
            return {"assigned": False, "reason": "no eligible work"}
        lease = store.claim(item, wid, runtime=str(body.get("runtime") or ""))
        if not lease.get("claimed"):
            return {"assigned": False, "reason": lease.get("reason", "lease denied")}
        out = {"assigned": True, "item_id": item, "title": data.get("title"),
               "worker_id": wid, "assignment_id": lease.get("assignment_id"),
               "expires_at": lease.get("expires_at")}
        # pickup contract from the producer (optional): what the worker carries (ADR-0002)
        for k in ("pidl_context", "execution_policy"):
            if data.get(k) is not None:
                out[k] = data[k]
        return out

    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")


def run(host: str = "", port: int = 0) -> int:
    cfg = _cfg.load()
    host = host or str(cfg.get("service_host") or "127.0.0.1")
    port = int(port or cfg.get("service_port") or 8790)
    srv = ThreadingHTTPServer((host, port), Handler)
    print(f"WorkerGrid service on http://{host}:{port} (producer={client._base()})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
