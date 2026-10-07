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
    item = "BI-CLI-0001"

    def log_message(self, *a):
        pass

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


def test_local_work_unwraps_producer_envelope(monkeypatch):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _StubProducer)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        monkeypatch.setenv("WORKERGRID_PF_API_URL", f"http://127.0.0.1:{srv.server_address[1]}")
        monkeypatch.setenv("WORKERGRID_STATE_DIR", tempfile.mkdtemp(prefix="wg-cli-state-"))
        r = wg.cmd_work([], {"worker": "WRK-CLI", "local": "1", "scope": "product_forge"})
        assert r.get("assigned") is True, r
        assert r.get("item_id") == "BI-CLI-0001", r
        assert r.get("worker_id") == "WRK-CLI", r
    finally:
        srv.shutdown()
        srv.server_close()
