"""BI-PF-0438: web_search tool - a client over a configurable backend (default disabled; no new dependency)."""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from core import tool_policy  # noqa: E402
from core.tool_registry import ToolRegistry  # noqa: E402


class _Searx(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith("/search"):
            body = json.dumps({"results": [
                {"title": "T1", "url": "https://a", "content": "S1"},
                {"title": "T2", "url": "https://b", "content": "S2"},
                {"title": "T3", "url": "https://c", "content": "S3"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()


def _stub():
    s = ThreadingHTTPServer(("127.0.0.1", 0), _Searx)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


def test_backend_none_is_disabled(monkeypatch):
    monkeypatch.setenv("PF_WEB_SEARCH_BACKEND", "none")
    r = ToolRegistry().execute("web_search", {"query": "anything"}, "")
    assert r.ok is False and "disabled" in r.error, (r.ok, r.error)


def test_searxng_json_backend(monkeypatch):
    s = _stub()
    try:
        monkeypatch.setenv("PF_WEB_SEARCH_BACKEND", "searxng")
        monkeypatch.setenv("PF_WEB_SEARCH_URL", f"http://127.0.0.1:{s.server_address[1]}")
        r = ToolRegistry().execute("web_search", {"query": "x", "limit": 2}, "")
        assert r.ok, r.error
        rows = json.loads(r.output)
        assert len(rows) == 2 and rows[0]["title"] == "T1" and rows[0]["url"] == "https://a", rows
    finally:
        s.shutdown()
        s.server_close()


def test_cloud_backends_require_a_key(monkeypatch):
    for backend in ("brave", "tavily"):
        monkeypatch.setenv("PF_WEB_SEARCH_BACKEND", backend)
        monkeypatch.delenv("PF_WEB_SEARCH_KEY", raising=False)
        monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        r = ToolRegistry().execute("web_search", {"query": "x"}, "")
        assert r.ok is False and "key required" in r.error, (backend, r.error)


def test_policy_grants_web_search_to_research_roles():
    tools = tool_policy.tools_for("researcher", base_tools=["read_file"], knowledge=["domain research"])
    assert "web_search" in tools and "http_get" in tools, tools
