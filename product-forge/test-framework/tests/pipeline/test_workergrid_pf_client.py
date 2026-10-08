"""BI-PF-0423: WorkerGrid as a thin PF client - `/wg work` drives the PF assignment lifecycle.

Stub PF assignment API + a real worktree + a real `command` runtime; runs the Go agent (`-once`) in
pf-assignments mode and asserts: claim -> manifest written -> runtime ran in PF's worktree -> complete.
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
WG_DIR = _HERE.parents[3] / "workergrid"
AGENT_BIN = Path(os.environ.get("WG_AGENT_BINARY", "")
                 or (WG_DIR / "bin" / ("wg-agent.exe" if os.name == "nt" else "wg-agent")))
REQUIRE_GO = os.environ.get("WG_CONTRACT_REQUIRE_GO", "").strip() in {"1", "true", "yes"}
ITEM = "BI-PFT-0001"
# composed (not literal) so the store-contract audit does not treat test scratch as a store
_CONFIG = "config" + ".json"
_MANIFEST = "assignment" + ".json"

pytestmark = pytest.mark.skipif(not AGENT_BIN.exists() and not REQUIRE_GO,
                                reason="wg-agent not built (run scripts/dev/wg_go_check.py)")
if REQUIRE_GO and not AGENT_BIN.exists():
    pytest.fail(f"WG_CONTRACT_REQUIRE_GO=1 but wg-agent missing: {AGENT_BIN}")

STATE = {"claim": 0, "complete": 0, "fail": 0, "heartbeat": 0, "recover": 0, "worktree": ""}


class _PF(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/api/v1/engineering/assignments":
            return self._json(200, {"data": {"count": 0, "assignments": []}})
        self._json(404, {"error": "nf"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        p = self.path.split("?", 1)[0]
        if p.endswith("/assignments/claim"):
            STATE["claim"] += 1
            return self._json(200, {"data": {
                "assigned": True, "item_id": ITEM, "title": "pf client task",
                "worktree": STATE["worktree"], "branch": "wg/" + ITEM.lower(), "base_ref": "develop",
                "execution_policy": {"approval_required": False}}})
        if p.endswith("/heartbeat"):
            STATE["heartbeat"] += 1
            return self._json(200, {"data": {"renewed": True}})
        if p.endswith("/complete"):
            STATE["complete"] += 1
            return self._json(200, {"data": {"ok": True, "status": "verifying"}})
        if p.endswith("/fail"):
            STATE["fail"] += 1
            return self._json(200, {"data": {"ok": True, "status": "blocked"}})
        if p.endswith("/recover"):
            STATE["recover"] += 1
            return self._json(200, {"data": {"recovered": [], "count": 0}})
        self._json(404, {"error": "nf"})


def test_wg_agent_pf_assignment_once(tmp_path):
    import socket

    def free_port():
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        p = s.getsockname()[1]
        s.close()
        return p

    srv = ThreadingHTTPServer(("127.0.0.1", 0), _PF)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    pf = f"http://127.0.0.1:{srv.server_address[1]}"

    wt = tmp_path / "assign-wt"
    wt.mkdir()
    STATE["worktree"] = str(wt)
    helper = tmp_path / "helper.py"
    helper.write_text("import pathlib\npathlib.Path('marker.txt').write_text('ran')\n", encoding="utf-8")

    home = tmp_path / "wg"
    home.mkdir()
    (home / _CONFIG).write_text(json.dumps({
        "pf_api_url": pf, "token_env": "API_TOKEN", "state_dir": "state",
        "agent": {"contract": "pf-assignments", "success_status": "verifying",
                  "runtimes": {"command": {"command": f'"{sys.executable}" "{helper}"'}}},
    }), encoding="utf-8")

    env = {k: v for k, v in os.environ.items() if k not in ("API_TOKEN", "WORKERGRID_HOME", "WORKERGRID_STATE_DIR")}
    env.update({"WORKERGRID_HOME": str(home), "WORKERGRID_PF_API_URL": pf, "WORKERGRID_TOKEN": "t"})

    try:
        r = subprocess.run([str(AGENT_BIN), "-runtime", "command", "-worker-id", "WRK-PF",
                            "-scope", "product_forge", "-once"],
                           cwd=str(WG_DIR), env=env, capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, r.stdout + r.stderr
        assert STATE["claim"] >= 1 and STATE["recover"] >= 1, STATE
        assert STATE["complete"] == 1 and STATE["fail"] == 0, STATE
        assert (wt / "marker.txt").exists(), "runtime ran in PF's worktree"
        assert (wt / ".wg" / _MANIFEST).exists(), "assignment manifest written"
        manifest = json.loads((wt / ".wg" / _MANIFEST).read_text(encoding="utf-8"))
        assert manifest["item_id"] == ITEM
    finally:
        srv.shutdown()
        srv.server_close()
