"""WorkerGrid Stage 3b (BI-PF-0414): PostgreSQL coordination store end-to-end.

Gated on ``WORKERGRID_PG_DSN`` (skipped without it, so the default gate stays
hermetic). Proves the multi-node value: two INDEPENDENT coordinator processes
with different state dirs, sharing one PostgreSQL store, see each other's
leases - which is what "multi-machine coordination" means.

Also covers the lease lifecycle over PG (claim conflict, renew, release) and
recovery of an expired lease. Item ids are unique per run so no cleanup of a
shared database is required.
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
WG_DIR = _HERE.parents[3] / "workergrid"
COORD_BIN = Path(os.environ.get("WG_COORD_BINARY", "")
                 or (WG_DIR / "bin" / ("wg-coordinator.exe" if os.name == "nt" else "wg-coordinator")))
REQUIRE_GO = os.environ.get("WG_CONTRACT_REQUIRE_GO", "").strip() in {"1", "true", "yes"}
TOKEN = "pg-e2e-token"
PG_DSN = os.environ.get("WORKERGRID_PG_DSN", "").strip()

pytestmark = [
    pytest.mark.skipif(not PG_DSN, reason="WORKERGRID_PG_DSN not set (PostgreSQL e2e skipped)"),
    pytest.mark.skipif(not COORD_BIN.exists() and not REQUIRE_GO,
                       reason="coordinator binary not built (run scripts/dev/wg_go_check.py)"),
]
if REQUIRE_GO and not COORD_BIN.exists():
    pytest.fail(f"WG_CONTRACT_REQUIRE_GO=1 but coordinator binary missing: {COORD_BIN}")


# ── stub producer ────────────────────────────────────────────────────────────
class _Producer:
    def __init__(self, item: str):
        self.item = item
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path.split("?", 1)[0] == "/api/v1/engineering/schedule/next":
                    body = json.dumps({"request_id": "stub", "status": "ok", "data": {
                        "scope": "product_forge", "project": "", "found": True,
                        "item": outer.item, "title": "pg test"}}).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self.send_response(404)
                self.end_headers()

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    @property
    def base(self):
        return f"http://127.0.0.1:{self.srv.server_address[1]}"

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


# ── coordinator spawn ────────────────────────────────────────────────────────
def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _http(base, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode("utf-8", "ignore") or "null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8", "ignore") or "null")
    except Exception as e:  # pragma: no cover
        return 0, str(e)


class _Coord:
    def __init__(self, producer_base: str, state_dir: str, lease: int):
        self.tmp = tempfile.mkdtemp(prefix="wgpg-")
        self.port = _free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        env = {k: v for k, v in os.environ.items()
               if k not in ("API_TOKEN", "WORKERGRID_TOKEN", "WORKERGRID_HOME", "WORKERGRID_STATE_DIR",
                            "WORKERGRID_PF_API_URL", "WORKERGRID_STORE_DRIVER", "WORKERGRID_STORE_DSN")}
        env.update({
            "WORKERGRID_HOME": self.tmp,          # no config.json here -> flags + env only
            "WORKERGRID_STATE_DIR": state_dir,
            "WORKERGRID_PF_API_URL": producer_base,
            "WORKERGRID_TOKEN": TOKEN,
            "WORKERGRID_STORE_DRIVER": "postgres",
            "WORKERGRID_STORE_DSN": PG_DSN,
            "WORKERGRID_LEASE_SECONDS": str(lease),
        })
        self.proc = subprocess.Popen(
            [str(COORD_BIN), "-host", "127.0.0.1", "-port", str(self.port)],
            cwd=str(WG_DIR), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        deadline = time.time() + 20
        while time.time() < deadline:
            if self.proc.poll() is not None:
                pytest.fail("coordinator exited: " + (self.proc.stdout.read() or ""))
            st, _ = _http(self.base, "GET", "/status")
            if st == 200:
                return
            time.sleep(0.1)
        pytest.fail("coordinator not ready (store=postgres)")

    def close(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except Exception:
                self.proc.kill()
        shutil.rmtree(self.tmp, ignore_errors=True)


def _state():
    return tempfile.mkdtemp(prefix="wgpgstate-")


def _status(base):
    st, body = _http(base, "GET", "/status")
    assert st == 200, body
    return body


def test_pg_shared_state_and_lease_lifecycle(tmp_path):
    item = "BI-PGT-" + uuid.uuid4().hex[:10].upper()
    producer = _Producer(item)
    a = b = None
    try:
        a = _Coord(producer.base, _state(), lease=3600)
        assert _http(a.base, "POST", "/workers/register",
                     {"worker_id": "WRK-PG-A", "runtime": "command"})[0] == 200
        st, r = _http(a.base, "POST", "/work", {"worker_id": "WRK-PG-A", "scope": "product_forge"})
        assert st == 200 and r["assigned"] is True, r

        # a SECOND, independent coordinator (different state dir) sees the lease
        b = _Coord(producer.base, _state(), lease=3600)
        assert _status(b.base)["leases"] >= 1, "shared PostgreSQL state not visible to the 2nd coordinator"
        assert _http(b.base, "POST", "/workers/register",
                     {"worker_id": "WRK-PG-B", "runtime": "command"})[0] == 200
        st, r2 = _http(b.base, "POST", "/work", {"worker_id": "WRK-PG-B", "scope": "product_forge"})
        assert r2["assigned"] is False and "already leased by WRK-PG-A" in r2["reason"], r2

        st, rn = _http(a.base, "POST", f"/leases/{item}/renew", {})
        assert st == 200 and rn["renewed"] is True, rn

        before = _status(a.base)["leases"]
        st, rel = _http(b.base, "POST", f"/leases/{item}/release", {})
        assert st == 200 and rel["released"] is True, rel
        assert _status(a.base)["leases"] == before - 1, "release via the 2nd coordinator did not free the lease"
    finally:
        for c in (a, b):
            if c:
                for w in ("WRK-PG-A", "WRK-PG-B"):
                    _http(c.base, "POST", f"/workers/{w}/unregister", {})
                c.close()
        producer.close()


def test_pg_recover_expired(tmp_path):
    item = "BI-PGT-" + uuid.uuid4().hex[:10].upper()
    producer = _Producer(item)
    c = None
    try:
        c = _Coord(producer.base, _state(), lease=-1)  # leases expire immediately
        assert _http(c.base, "POST", "/workers/register",
                     {"worker_id": "WRK-PG-R", "runtime": "command"})[0] == 200
        st, r = _http(c.base, "POST", "/work", {"worker_id": "WRK-PG-R", "scope": "product_forge"})
        assert st == 200 and r["assigned"] is True, r
        st, rec = _http(c.base, "POST", "/leases/recover", {})
        assert st == 200 and rec["count"] >= 1 and item in rec["recovered"], rec
    finally:
        if c:
            _http(c.base, "POST", "/workers/WRK-PG-R/unregister", {})
            c.close()
        producer.close()
