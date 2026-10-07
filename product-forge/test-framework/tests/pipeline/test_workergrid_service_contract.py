"""WorkerGrid coordinator service contract (BI-PF-0412) - one suite, two implementations.

Pins the HTTP behavior of the coordinator service so the Go port (Stage 3a) can prove
parity: every test runs against the Python spike (workergrid/service.py, present until
cutover) AND the Go binary (workergrid/bin/wg-coordinator[.exe]).

Producer stub: the suite stands up a fake PF producer serving the canonical envelope of
GET /api/v1/engineering/schedule/next ({request_id, status, data:{found, item, ...}}) -
the shape that exposed the envelope-unwrap defect this suite guards (service._assign).

Impl selection:
  * python leg runs only while workergrid/service.py exists (dropped after cutover);
  * go leg skips when the binary is missing, unless WG_CONTRACT_REQUIRE_GO=1 (set by
    scripts/dev/wg_go_check.py after it builds) - then a missing binary FAILS.
Env knobs (both impls): WORKERGRID_STATE_DIR, WORKERGRID_PF_API_URL, WORKERGRID_TOKEN,
WORKERGRID_LEASE_SECONDS (negative TTL -> immediately-expired lease for recover tests).
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
WG_DIR = _HERE.parents[3] / "workergrid"          # repo-root/workergrid
GO_BIN = Path(os.environ.get("WG_GO_BINARY", "")
              or (WG_DIR / "bin" / ("wg-coordinator.exe" if os.name == "nt"
                                    else "wg-coordinator")))
REQUIRE_GO = os.environ.get("WG_CONTRACT_REQUIRE_GO", "").strip() in {"1", "true", "yes"}
TOKEN = "contract-token"
STUB_STATE = {"next": None}                        # payload served by the producer stub


def _impls():
    impls = []
    if (WG_DIR / "service.py").exists():
        impls.append("python")
    impls.append("go")
    return impls


# ── producer stub (canonical PF envelope) ─────────────────────────────────────
class _StubHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/api/v1/engineering/schedule/next":
            payload = STUB_STATE["next"]
            if payload is None:
                payload = {"request_id": "stub", "status": "ok", "data": {
                    "scope": "product_forge", "project": "", "found": False, "item": None}}
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()


@pytest.fixture(scope="module")
def stub():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _StubHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _http(base: str, method: str, path: str, body=None, token: str = TOKEN,
          raw: str = None):
    """-> (status:int, json|str|None). raw= sends that exact body string."""
    data = raw.encode("utf-8") if raw is not None else (
        json.dumps(body).encode("utf-8") if body is not None else None)
    req = urllib.request.Request(base + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            txt = r.read().decode("utf-8", errors="ignore")
            return r.status, (json.loads(txt) if txt else None)
    except urllib.error.HTTPError as e:
        txt = e.read().decode("utf-8", errors="ignore")
        return e.code, (json.loads(txt) if txt else None)
    except Exception as e:  # pragma: no cover - spawn/readiness issues
        return 0, str(e)


class _Service:
    def __init__(self, base: str, proc):
        self.base = base
        self.proc = proc

    def close(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except Exception:
                self.proc.kill()


def _spawn(impl: str, stub_base: str, token: str = TOKEN, lease: int = None) -> _Service:
    if impl == "python":
        if not (WG_DIR / "service.py").exists():  # pragma: no cover
            pytest.skip("python spike removed (post-cutover)")
    else:
        if not GO_BIN.exists():
            if REQUIRE_GO:
                pytest.fail(f"go binary missing at {GO_BIN} (wg_go_check must build it)")
            pytest.skip("go binary not built (run scripts/dev/wg_go_check.py)")
    if impl == "go" and os.name != "nt":
        os.chmod(GO_BIN, 0o755) if GO_BIN.exists() else None

    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix=f"wgcontract-{impl}-"))
    port = _free_port()
    env = {k: v for k, v in os.environ.items()
           if k not in ("API_TOKEN", "WORKERGRID_TOKEN")}
    env["WORKERGRID_STATE_DIR"] = str(tmp)
    env["WORKERGRID_PF_API_URL"] = stub_base
    if token:
        env["WORKERGRID_TOKEN"] = token
    if lease is not None:
        env["WORKERGRID_LEASE_SECONDS"] = str(lease)

    if impl == "python":
        cmd = [sys.executable, str(WG_DIR / "service.py"),
               "--host", "127.0.0.1", "--port", str(port)]
    else:
        cmd = [str(GO_BIN), "-host", "127.0.0.1", "-port", str(port)]
    proc = subprocess.Popen(cmd, cwd=str(WG_DIR), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True)
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 15
    while time.time() < deadline:
        if proc.poll() is not None:
            out = proc.stdout.read() if proc.stdout else ""
            shutil.rmtree(tmp, ignore_errors=True)
            pytest.fail(f"{impl} service exited during startup: {out}")
        st, _ = _http(base, "GET", "/status", token=token)
        if st == 200:
            return _Service(base, proc)
        time.sleep(0.1)
    proc.terminate()
    shutil.rmtree(tmp, ignore_errors=True)
    pytest.fail(f"{impl} service did not become ready on {base}")


@pytest.fixture
def svc(request, stub):
    impl = request.param
    service = _spawn(impl, stub)
    yield service
    service.close()


IMPLS = _impls()
if not IMPLS:  # pragma: no cover
    pytest.skip("no service implementation available", allow_module_level=True)
if "go" in IMPLS and REQUIRE_GO and not GO_BIN.exists():
    pytest.fail(f"WG_CONTRACT_REQUIRE_GO=1 but go binary missing at {GO_BIN}")


def _ids(vals):
    return pytest.mark.parametrize("impl", vals, ids=vals)


# ── auth ─────────────────────────────────────────────────────────────────────
@_ids(IMPLS)
def test_auth_enforced_when_token_set(impl, stub):
    svc = _spawn(impl, stub)
    try:
        st, body = _http(svc.base, "GET", "/status", token=None)
        assert (st, body) == (401, {"error": "unauthorized"})
        st, body = _http(svc.base, "GET", "/status", token="wrong")
        assert (st, body) == (401, {"error": "unauthorized"})
        st, _ = _http(svc.base, "GET", "/status", token=TOKEN)
        assert st == 200
    finally:
        svc.close()


@_ids(IMPLS)
def test_anonymous_dev_mode_when_no_token(impl, stub):
    svc = _spawn(impl, stub, token=None)
    try:
        st, _ = _http(svc.base, "GET", "/status", token=None)
        assert st == 200
    finally:
        svc.close()


# ── status / routing ─────────────────────────────────────────────────────────
@_ids(IMPLS)
def test_status_shape_and_querystring(impl, stub):
    svc = _spawn(impl, stub)
    try:
        st, body = _http(svc.base, "GET", "/status?x=1")
        assert st == 200
        assert isinstance(body.get("workers"), int)
        assert isinstance(body.get("leases"), int)
        assert body.get("producer") == stub
        st, body = _http(svc.base, "GET", "/definitely-not-a-route")
        assert (st, body) == (404, {"error": "not found"})
    finally:
        svc.close()


# ── workers ──────────────────────────────────────────────────────────────────
@_ids(IMPLS)
def test_register_roundtrip_and_upsert(impl, stub):
    svc = _spawn(impl, stub)
    try:
        st, w = _http(svc.base, "POST", "/workers/register",
                      {"runtime": "opencode", "capabilities": ["python", "code"],
                       "role": "dev"})
        assert st == 200
        wid = w.get("worker_id")
        assert wid and wid.startswith("WRK-")
        assert w.get("runtime") == "opencode"
        assert w.get("capabilities") == "python,code"
        assert w.get("role") == "dev"
        assert w.get("status") == "ONLINE"
        assert w.get("current_assignment") == ""
        assert float(w.get("registered_at") or 0) > 0
        assert float(w.get("last_heartbeat") or 0) > 0

        st, g = _http(svc.base, "GET", f"/workers/{wid}")
        assert (st, g.get("worker_id")) == (200, wid)

        st, listing = _http(svc.base, "GET", "/workers")
        assert st == 200
        assert any(x.get("worker_id") == wid for x in listing.get("workers", []))

        # explicit id + upsert (re-register updates capabilities, keeps ONLINE)
        st, w2 = _http(svc.base, "POST", "/workers/register",
                       {"worker_id": "WRK-CT-1", "runtime": "opencode",
                        "capabilities": ["go"]})
        assert (st, w2.get("worker_id")) == (200, "WRK-CT-1")
        st, w3 = _http(svc.base, "POST", "/workers/register",
                       {"worker_id": "WRK-CT-1", "runtime": "opencode",
                        "capabilities": ["go", "sqlite"]})
        assert w3.get("capabilities") == "go,sqlite"
        assert w3.get("status") == "ONLINE"
    finally:
        svc.close()


@_ids(IMPLS)
def test_register_malformed_body_treated_as_empty(impl, stub):
    svc = _spawn(impl, stub)
    try:
        st, w = _http(svc.base, "POST", "/workers/register", raw="{not json")
        assert st == 200
        assert str(w.get("worker_id") or "").startswith("WRK-")
    finally:
        svc.close()


@_ids(IMPLS)
def test_heartbeat_known_and_unknown(impl, stub):
    svc = _spawn(impl, stub)
    try:
        st, hb = _http(svc.base, "POST", "/workers/WRK-NOPE/heartbeat", {"status": "IDLE"})
        assert (st, hb) == (200, {"ok": False, "reason": "unknown worker"})
        _http(svc.base, "POST", "/workers/register", {"worker_id": "WRK-HB", "runtime": "r"})
        st, hb = _http(svc.base, "POST", "/workers/WRK-HB/heartbeat",
                       {"status": "BUSY", "current_assignment": "BI-X"})
        assert (st, hb) == (200, {"ok": True, "worker_id": "WRK-HB"})
        _, g = _http(svc.base, "GET", "/workers/WRK-HB")
        assert (g.get("status"), g.get("current_assignment")) == ("BUSY", "BI-X")
    finally:
        svc.close()


@_ids(IMPLS)
def test_unregister(impl, stub):
    svc = _spawn(impl, stub)
    try:
        _http(svc.base, "POST", "/workers/register", {"worker_id": "WRK-DEL", "runtime": "r"})
        st, u = _http(svc.base, "POST", "/workers/WRK-DEL/unregister")
        assert (st, u) == (200, {"removed": True, "worker_id": "WRK-DEL"})
        st, _ = _http(svc.base, "GET", "/workers/WRK-DEL")
        assert st == 404
        st, u = _http(svc.base, "POST", "/workers/WRK-DEL/unregister")
        assert (st, u) == (200, {"removed": False, "worker_id": "WRK-DEL"})
    finally:
        svc.close()


# ── claim flow (producer envelope + lease) ───────────────────────────────────
def _envelope(item: str, title: str, found: bool = True, extra: dict = None):
    data = {"scope": "product_forge", "project": "", "found": found,
            "item": item, "title": title}
    if extra:
        data.update(extra)
    return {"request_id": "req-1", "correlation_id": "corr-1", "status": "ok",
            "resource": "engineering", "resource_id": "", "data": data,
            "links": {}, "warnings": [], "error": None}


@_ids(IMPLS)
def test_work_requires_registered_worker(impl, stub):
    svc = _spawn(impl, stub)
    try:
        st, a = _http(svc.base, "POST", "/work", {"worker_id": "WRK-MISSING"})
        assert (st, a) == (200, {"assigned": False, "reason": "worker not registered"})
    finally:
        svc.close()


@_ids(IMPLS)
def test_work_no_eligible_work(impl, stub):
    svc = _spawn(impl, stub)
    try:
        STUB_STATE["next"] = _envelope(None, None, found=False)
        _http(svc.base, "POST", "/workers/register", {"worker_id": "WRK-NOW", "runtime": "r"})
        st, a = _http(svc.base, "POST", "/work", {"worker_id": "WRK-NOW"})
        assert (st, a) == (200, {"assigned": False, "reason": "no eligible work"})
    finally:
        svc.close()


@_ids(IMPLS)
def test_work_assign_with_envelope_and_pidl_passthrough(impl, stub):
    svc = _spawn(impl, stub)
    try:
        STUB_STATE["next"] = _envelope("BI-CT-0001", "Contract task", extra={
            "priority_rank": 10,
            "pidl_context": {"profile_version": 12, "applicable_rules": ["PIDL-RULE-004"]},
            "execution_policy": {"autonomy": "allowed", "approval_required": False}})
        _http(svc.base, "POST", "/workers/register", {"worker_id": "WRK-A", "runtime": "opencode"})
        st, a = _http(svc.base, "POST", "/work", {"worker_id": "WRK-A"})
        assert st == 200
        assert a.get("assigned") is True
        assert a.get("item_id") == "BI-CT-0001"
        assert a.get("title") == "Contract task"
        assert a.get("worker_id") == "WRK-A"
        assert a.get("assignment_id") == "ASG-BI-CT-0001"
        assert float(a.get("expires_at") or 0) > time.time()
        # pickup contract passes through to the worker (ADR-0002)
        assert a.get("pidl_context") == {
            "profile_version": 12, "applicable_rules": ["PIDL-RULE-004"]}
        assert a.get("execution_policy") == {
            "autonomy": "allowed", "approval_required": False}
        # claim marks the worker BUSY with the assignment
        _, g = _http(svc.base, "GET", "/workers/WRK-A")
        assert (g.get("status"), g.get("current_assignment")) == ("BUSY", "BI-CT-0001")
    finally:
        svc.close()


@_ids(IMPLS)
def test_work_denied_when_already_leased(impl, stub):
    svc = _spawn(impl, stub)
    try:
        STUB_STATE["next"] = _envelope("BI-CT-0002", "Contended task")
        _http(svc.base, "POST", "/workers/register", {"worker_id": "WRK-B1", "runtime": "r"})
        _http(svc.base, "POST", "/workers/register", {"worker_id": "WRK-B2", "runtime": "r"})
        st, a1 = _http(svc.base, "POST", "/work", {"worker_id": "WRK-B1"})
        assert a1.get("assigned") is True
        st, a2 = _http(svc.base, "POST", "/work", {"worker_id": "WRK-B2"})
        assert st == 200
        assert a2.get("assigned") is False
        assert "already leased by" in str(a2.get("reason"))
    finally:
        svc.close()


@_ids(IMPLS)
def test_lease_renew_release_reclaim(impl, stub):
    svc = _spawn(impl, stub)
    try:
        STUB_STATE["next"] = _envelope("BI-CT-0003", "Renewable task")
        _http(svc.base, "POST", "/workers/register", {"worker_id": "WRK-R1", "runtime": "r"})
        _http(svc.base, "POST", "/workers/register", {"worker_id": "WRK-R2", "runtime": "r"})
        _http(svc.base, "POST", "/work", {"worker_id": "WRK-R1"})

        st, rn = _http(svc.base, "POST", "/leases/BI-CT-0003/renew")
        assert (st, rn) == (200, {"renewed": True, "item_id": "BI-CT-0003"})
        st, rn = _http(svc.base, "POST", "/leases/BI-UNKNOWN/renew")
        assert (st, rn) == (200, {"renewed": False, "item_id": "BI-UNKNOWN"})

        st, rl = _http(svc.base, "POST", "/leases/BI-CT-0003/release")
        assert (st, rl) == (200, {"released": True, "item_id": "BI-CT-0003"})
        # released worker goes IDLE, item becomes claimable by another worker
        _, g = _http(svc.base, "GET", "/workers/WRK-R1")
        assert (g.get("status"), g.get("current_assignment")) == ("IDLE", "")
        st, a2 = _http(svc.base, "POST", "/work", {"worker_id": "WRK-R2"})
        assert a2.get("assigned") is True and a2.get("item_id") == "BI-CT-0003"
    finally:
        svc.close()


@_ids(IMPLS)
def test_lease_recover_expired(impl, stub):
    # negative TTL -> the claim lands already-expired (deterministic, no sleeps)
    svc = _spawn(impl, stub, lease=-1)
    try:
        STUB_STATE["next"] = _envelope("BI-CT-EXP", "Expiring task")
        _http(svc.base, "POST", "/workers/register", {"worker_id": "WRK-E", "runtime": "r"})
        st, a = _http(svc.base, "POST", "/work", {"worker_id": "WRK-E"})
        assert a.get("assigned") is True
        st, rc = _http(svc.base, "POST", "/leases/recover")
        assert (st, rc) == (200, {"recovered": ["BI-CT-EXP"], "count": 1})
        _, g = _http(svc.base, "GET", "/workers/WRK-E")
        assert (g.get("status"), g.get("current_assignment")) == ("IDLE", "")
        # recovering again finds nothing
        st, rc = _http(svc.base, "POST", "/leases/recover")
        assert (st, rc) == (200, {"recovered": [], "count": 0})
    finally:
        svc.close()
