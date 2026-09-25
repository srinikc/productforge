#!/usr/bin/env python3
"""
Product Forge — Pipeline Dashboard (from scratch, pipeline-owned).

A standalone, zero-dependency dashboard that reads the pipeline/QA state files
and exposes them as JSON APIs + a vanilla-JS UI. Two apps by design:
  - this pipeline dashboard (pipeline lifecycle: stages, agents, builds, targets, delivery)
  - the QA console (test-framework/dashboard: tests, cycles, defects, QIR, Go/No-Go)

Run:  python dashboard/server.py [--port 3020] [--host 127.0.0.1]
API:  /api/projects /api/quality/status /api/pipeline/status /api/qir /api/gonogo
"""
import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRODUCTS = os.path.join(ROOT, "products")
TF = os.path.join(ROOT, "test-framework")
STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
sys.path.insert(0, ROOT)

DEFAULT_PORT = 3020


def _rj(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _projects():
    try:
        return sorted(d for d in os.listdir(PRODUCTS)
                      if os.path.isdir(os.path.join(PRODUCTS, d)) and not d.startswith("."))
    except Exception:
        return []


def _pdir(project):
    return os.path.join(PRODUCTS, project)


def _results(project):
    return os.path.join(TF, "results", project)


def quality_status(project):
    q = _rj(os.path.join(_results(project), "qir.json"), {}) or {}
    g = _rj(os.path.join(_results(project), "go-no-go.json"), {}) or {}
    sr = _rj(os.path.join(_results(project), "spec-review.json"), {}) or {}
    ins = _rj(os.path.join(_results(project), "insights.json"), {}) or {}
    dec = str(g.get("decision") or "").upper()
    rag = {"NO-GO": "red", "GO-WITH-RISK": "yellow", "GO": "green"}.get(dec, q.get("band", "unknown"))
    try:
        from core.defect_loop import open_defects
        od = len(open_defects(project))
    except Exception:
        od = None
    return {"project": project, "rag": rag, "decision": g.get("decision"),
            "qir": {"number": q.get("number"), "band": q.get("band"), "trend": q.get("trend")},
            "spec_review": sr.get("summary", {}), "insights": ins.get("summary", {}),
            "open_defects": od, "top_risks": (g.get("rationale") or [])[:5],
            "matrix": g.get("matrix", [])}


def pipeline_status(project):
    st = _rj(os.path.join(_pdir(project), "pipeline-state.json"), {}) or {}
    live = _rj(os.path.join(_pdir(project), "agents-live.json"), {}) or {}
    stages = st.get("stages", {}) or {}
    return {"project": project, "complete": st.get("pipeline_complete"),
            "current_stage": st.get("current_stage"), "started_at": st.get("started_at"),
            "completed_at": st.get("completed_at"), "total_tokens": st.get("total_tokens"),
            "total_cost": st.get("total_cost"),
            "stages": [{"id": k, "status": (v or {}).get("status"),
                        "started_at": (v or {}).get("started_at"),
                        "completed_at": (v or {}).get("completed_at")}
                       for k, v in stages.items()],
            "live_agents": live if isinstance(live, dict) else {}}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, (bytes, bytearray)) else json.dumps(body, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        p = urlparse(self.path)
        path, q = p.path, parse_qs(p.query)
        # v1 aliases (structure contract: one API surface)
        if path.startswith("/api/v1/backlog"):
            path = path.replace("/api/v1/backlog", "/api/backlog", 1)
        if path == "/api/forge/plan":
            try:
                from core import forge_store
                return self._send(200, forge_store.read_plan())
            except Exception as e:
                return self._send(200, {"error": str(e)})
        if path == "/api/forge/state":
            try:
                from core import forge_store
                return self._send(200, forge_store.read_state())
            except Exception as e:
                return self._send(200, {"error": str(e)})
        project = (q.get("project") or ["e2e-free"])[0]
        if path == "/api/projects":
            return self._send(200, _projects())
        if path == "/api/quality/status":
            return self._send(200, quality_status(project))
        if path == "/api/pipeline/status":
            return self._send(200, pipeline_status(project))
        if path == "/api/qir":
            return self._send(200, _rj(os.path.join(_results(project), "qir.json"), {}))
        if path == "/api/gonogo":
            return self._send(200, _rj(os.path.join(_results(project), "go-no-go.json"), {}))
        if path == "/api/capacity":
            try:
                from core.capacity import status as cap_status
                return self._send(200, cap_status())
            except Exception as e:
                return self._send(200, {"error": str(e)})
        if path == "/api/intake/instructions":
            try:
                from core import intake_api
                store = intake_api.get_store()
                return self._send(200, {"source": (q.get("source") or ["generic"])[0],
                                        "store": type(store).__name__,
                                        "post": "JSON {title, scope, project, kind, value}"})
            except Exception as e:
                return self._send(200, {"error": str(e)})
        if path == "/api/ws/events":
            try:
                from core.websocket_manager import WSEventType
                return self._send(200, {"event_types": [v for k, v in vars(WSEventType).items()
                                                        if not k.startswith("_") and isinstance(v, str)]})
            except Exception as e:
                return self._send(200, {"error": str(e)})
        if path == "/api/backlog":
            try:
                from core import backlog
                scope = (q.get("scope") or ["project"])[0]
                proj = (q.get("project") or [None])[0]
                return self._send(200, {"open": backlog.list_open(scope, proj),
                                        "stats": backlog.stats(scope, proj)})
            except Exception as e:
                return self._send(200, {"error": str(e)})
        if path == "/api/backlog/stale":
            try:
                from core import backlog
                days = int((q.get("days") or ["7"])[0])
                scope = (q.get("scope") or [""])[0]
                proj = (q.get("project") or [None])[0]
                return self._send(200, {"stale": backlog.stale(days, scope, proj)})
            except Exception as e:
                return self._send(200, {"error": str(e)})
        if path == "/api/backlog/closed":
            try:
                from core import backlog
                scope = (q.get("scope") or ["project"])[0]
                proj = (q.get("project") or [None])[0]
                return self._send(200, {"closed": backlog.list_closed(scope, proj)})
            except Exception as e:
                return self._send(200, {"error": str(e)})
        if path == "/api/persona":
            try:
                from core.persona import load as persona_load, brief
                return self._send(200, {"persona": persona_load(project), "brief": brief(project)})
            except Exception as e:
                return self._send(200, {"error": str(e)})
        if path == "/api/intake/instructions":
            try:
                from core.intake import instructions
                return self._send(200, {"instructions": instructions((q.get("source") or ["generic"])[0])})
            except Exception as e:
                return self._send(200, {"error": str(e)})
        if path == "/api/portfolio":
            try:
                from core.portfolio import status_rows
                return self._send(200, {"projects": status_rows()})
            except Exception as e:
                return self._send(200, {"error": str(e)})
        if path in ("/", "/index.html"):
            return self._send(200, _read_static("index.html"), "text/html")
        if path.startswith("/static/"):
            return self._send(200, _read_static(path[len("/static/"):]), _ctype(path))
        self._send(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        if path.startswith("/api/v1/backlog"):
            path = path.replace("/api/v1/backlog", "/api/backlog", 1)
        try:
            n = int(self.headers.get("Content-Length", 0) or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            body = {}
        if path == "/api/run":
            return self._send(200, _spawn_run(body, enhance=False))
        if path == "/api/enhance":
            return self._send(200, _spawn_run(body, enhance=True))
        if path == "/api/intake":
            try:
                from core.intake import ingest
                src = str(body.get("source") or "generic")
                payload = body.get("payload") or body
                return self._send(200, ingest(src, payload, body.get("scope"), body.get("project")))
            except Exception as e:
                return self._send(200, {"error": str(e)})
        if path == "/api/backlog":
            try:
                from core import backlog
                scope = body.get("scope") or "project"
                proj = body.get("project")
                if body.get("title"):
                    epic = backlog.add_epic(scope, proj, title=body["title"],
                                            body=body.get("body", ""),
                                            source=body.get("source", "dashboard"),
                                            type_=body.get("kind", "feature"),
                                            value=int(body.get("value", 3)),
                                            effort=int(body.get("effort", 3)),
                                            risk=int(body.get("risk", 2)),
                                            moscow=body.get("moscow", "Should"))
                    return self._send(200, epic)
                return self._send(200, {"open": backlog.list_open(scope, proj)})
            except Exception as e:
                return self._send(200, {"error": str(e)})
        if path.startswith("/api/backlog/"):
            return self._send(200, _backlog_action(path, body))
        if path == "/api/portfolio/start":
            try:
                from core.portfolio import run_supervisor
                return self._send(200, {"started": True, "note": "call run_portfolio.py start"})
            except Exception as e:
                return self._send(200, {"error": str(e)})
        self._send(404, {"error": "not found"})


def _read_static(rel):
    try:
        with open(os.path.join(STATIC, rel), "rb") as f:
            return f.read()
    except Exception:
        return b"# not found"


def _ctype(rel):
    return {"html": "text/html", "js": "application/javascript",
            "css": "text/css", "json": "application/json"}.get(rel.rsplit(".", 1)[-1], "text/plain")


def _spawn_run(body: dict, enhance: bool = False) -> dict:
    """Start a project run (or enhance) as a detached process; log to pipeline-run.log."""
    import subprocess
    project = str(body.get("project") or "")
    if not project:
        return {"error": "project required"}
    cmd = [sys.executable, "-u", os.path.join(ROOT, "scripts", "run_pipeline.py")]
    if enhance:
        cmd += ["enhance", project]
        if body.get("goal"):
            cmd += ["--goal", str(body["goal"])]
        if body.get("no_run"):
            cmd += ["--no-run"]
    else:
        cmd += ["--project", project]
    if body.get("tier"):
        cmd += ["--tier", str(body["tier"])]
    if body.get("auto"):
        cmd += ["--auto"]
    if body.get("idea") and not enhance:
        cmd += ["--idea", str(body["idea"])]
    try:
        os.makedirs(_pdir(project), exist_ok=True)
        log = open(os.path.join(_pdir(project), "pipeline-run.log"), "a", encoding="utf-8")
        pr = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        return {"started": True, "pid": pr.pid, "cmd": " ".join(cmd)}
    except Exception as e:
        return {"error": str(e)}


def _backlog_action(path: str, body: dict) -> dict:
    """POST /api/backlog/<id>/<triage|accept|close|update>."""
    try:
        from core import backlog
        parts = [p for p in path.split("/") if p]  # ['api','backlog','<id>','<action>']
        if len(parts) < 3:
            return {"error": "id required"}
        eid = parts[2]
        action = parts[3] if len(parts) > 3 else "update"
        scope = body.get("scope") or "project"
        proj = body.get("project")
        if action == "triage":
            return backlog.triage(scope, proj, eid,
                                  recommendation=body.get("recommendation", ""),
                                  value=body.get("value"), effort=body.get("effort"),
                                  risk=body.get("risk"), moscow=body.get("moscow"))
        if action == "accept":
            return backlog.accept(scope, proj, eid, when=body.get("when", "later"),
                                  by=body.get("by", "hil"))
        if action == "close":
            return backlog.update(scope, proj, eid, status=body.get("status", "done"),
                                  _note=body.get("note", ""))
        return backlog.update(scope, proj, eid, **body)
    except Exception as e:
        return {"error": str(e)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()
    try:
        from core.websocket_manager import setup_ws_events
        setup_ws_events()
    except Exception:
        pass
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f"Pipeline dashboard: http://{a.host}:{a.port}  (projects={len(_projects())})")
    srv.serve_forever()


if __name__ == "__main__":
    main()
