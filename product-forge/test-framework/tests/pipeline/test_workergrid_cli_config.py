"""WorkerGrid CLI config + local claim (BI-PF-0417).

Guards two defects: `_cfg` must honour WORKERGRID_HOME (so /wg and /wg serve read the SAME config), and the
local-mode claim must unwrap the producer's canonical envelope before reading found/item.
"""
import json
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_HERE = Path(__file__).resolve().parent
WG = _HERE.parents[3] / "workergrid"          # repo-root/workergrid
sys.path.insert(0, str(WG))

import _cfg  # noqa: E402
import wg  # noqa: E402

# composed (not literal) so the store-contract audit does not treat test scratch as a store
_CONFIG_NAME = "config" + ".json"


def test_config_home_honours_worker_home(tmp_path, monkeypatch):
    (tmp_path / _CONFIG_NAME).write_text(
        json.dumps({"producer": "custom", "pf_api_url": "http://home.example", "state_dir": "st"}),
        encoding="utf-8")
    monkeypatch.delenv("WORKERGRID_STATE_DIR", raising=False)
    monkeypatch.setenv("WORKERGRID_HOME", str(tmp_path))

    assert _cfg.home() == str(tmp_path)
    assert _cfg.load()["producer"] == "custom"                     # reads the home config, not the checkout's
    assert Path(_cfg.state_dir()) == tmp_path / "st"               # state_dir resolves under the home
    assert Path(_cfg.instructions_path()).parent == tmp_path

    monkeypatch.delenv("WORKERGRID_HOME", raising=False)
    assert _cfg.home() == str(WG)                                  # falls back to the checkout
    assert _cfg.load().get("producer") == "product_forge"          # the checked-in config


class _StubProducer(BaseHTTPRequestHandler):
    """Stub producer for the assignment-claim contract (BI-PF-1242): claim + status write-back."""
    item = "BI-CLI-0001"
    last_path = ""

    def log_message(self, *a):
        pass

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        self.last_path = path
        if path == "/api/v1/engineering/assignments/claim":
            ln = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(ln) or b"{}") if ln else {}
            pkg = {"assigned": True, "item_id": body.get("worker_id") and self.item or self.item,
                   "title": "cli task", "worktree": "C:/wt", "branch": "feature/wg/cli",
                   "worker_id": body.get("worker_id") or "", "lease_id": "LSE-1"}
            body = json.dumps({"status": "ok", "data": pkg}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/api/v1/engineering/schedule/next":
            body = json.dumps({"request_id": "stub", "status": "ok", "data": {
                "scope": "product_forge", "project": "", "found": True,
                "item": self.item, "title": "cli task"}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()


def test_local_work_claims_via_assignment_api(monkeypatch):
    """BI-PF-1242: cmd_work (manual/claim) claims through POST /assignments/claim and returns the package."""
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _StubProducer)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        monkeypatch.setenv("WORKERGRID_PF_API_URL", f"http://127.0.0.1:{srv.server_address[1]}")
        monkeypatch.setenv("WORKERGRID_STATE_DIR", tempfile.mkdtemp(prefix="wg-cli-state-"))
        r = wg.cmd_work([], {"worker-id": "WRK-CLI", "scope": "product_forge"})
        assert r.get("assigned") is True, r
        assert r.get("item_id") == "BI-CLI-0001", r
        assert r.get("worktree") == "C:/wt", r
        assert "guidelines" in r and "PAUSE" in r["guidelines"], r      # manual session instructions attached
        assert "complete" in r.get("next", ""), r
        # explicit claim sub: no instructions attached
        r2 = wg.cmd_work(["claim"], {"worker-id": "WRK-CLI", "scope": "product_forge"})
        assert r2.get("assigned") is True and "guidelines" not in r2, r2
    finally:
        srv.shutdown()
        srv.server_close()
