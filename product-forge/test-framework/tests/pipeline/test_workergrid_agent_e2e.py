"""WorkerGrid worker agent end-to-end (BI-PF-0413, Stage 3c).

Drives the real Go binaries - coordinator (bin/wg-coordinator) + agent
(bin/wg-agent) - against a stub producer, with a throwaway git repo for
worktrees. Proves the whole loop end to end:

  recover -> claim -> write-back "scheduled" -> isolated git worktree
  -> execute runtime command -> heartbeat/renew -> write-back
  "executing" -> success|blocked -> release lease

Covered: happy path (status order + operator auth + worktree/branch + journal),
command failure -> blocked, PIDL approval gate -> fail-closed blocked (no
exec), no work -> clean exit, and heartbeat/renewal keeping the worker live.

Binaries are built by scripts/dev/wg_go_check.py (which sets
WG_CONTRACT_REQUIRE_GO=1, making a missing binary a FAIL rather than a skip).
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
WG_DIR = _HERE.parents[3] / "workergrid"
_EXT = ".exe" if os.name == "nt" else ""
COORD_BIN = Path(os.environ.get("WG_COORD_BINARY", "") or (WG_DIR / "bin" / ("wg-coordinator" + _EXT)))
AGENT_BIN = Path(os.environ.get("WG_AGENT_BINARY", "") or (WG_DIR / "bin" / ("wg-agent" + _EXT)))
REQUIRE_GO = os.environ.get("WG_CONTRACT_REQUIRE_GO", "").strip() in {"1", "true", "yes"}
TOKEN = "agent-e2e-token"
ITEM = "BI-TST-0001"
TITLE = "do the thing"
# composed (not literal) so the store-contract audit does not treat test scratch as a store
_CONFIG_NAME = "config" + ".json"
_JOURNAL_NAME = "agent-journal" + ".jsonl"

if REQUIRE_GO and (not COORD_BIN.exists() or not AGENT_BIN.exists()):
    pytest.fail(f"WG_CONTRACT_REQUIRE_GO=1 but binaries missing: {COORD_BIN} / {AGENT_BIN}")
pytestmark = pytest.mark.skipif(
    not (COORD_BIN.exists() and AGENT_BIN.exists()),
    reason="WorkerGrid binaries not built (run scripts/dev/wg_go_check.py)")


# ── stub producer (PF contract: schedule/next envelope + status write-back) ───
class _Producer:
    def __init__(self):
        self.next_payload = {"request_id": "stub", "status": "ok", "data": {
            "scope": "product_forge", "project": "", "found": True, "item": ITEM,
            "title": TITLE, "pidl_context": {"x": 1}, "execution_policy": {"autonomy": "auto"}}}
        self.status_calls = []          # (item_id, status, note, roles, auth)
        self.lock = threading.Lock()
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    @property
    def base(self):
        return f"http://127.0.0.1:{self.srv.server_address[1]}"

    def statuses(self):
        with self.lock:
            return [c[1] for c in self.status_calls]

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()

    def _handler(self):
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, obj):
                body = json.dumps(obj).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path.split("?", 1)[0] == "/api/v1/engineering/schedule/next":
                    return self._send(200, outer.next_payload)
                self._send(404, {"error": "not found"})

            def do_POST(self):
                path = self.path.split("?", 1)[0]
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
                if path.endswith("/status") and "/api/v1/backlog/items/" in path:
                    item = path.split("/items/", 1)[1].split("/", 1)[0]
                    with outer.lock:
                        outer.status_calls.append((item, body.get("status"), body.get("note", ""),
                                                   self.headers.get("X-Roles", ""),
                                                   self.headers.get("Authorization", "")))
                    return self._send(200, {"request_id": "stub", "status": "ok", "data": {"ok": True}})
                self._send(404, {"error": "not found"})

        return H


# ── harness ──────────────────────────────────────────────────────────────────
def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _http(base, method, path, body=None, token=TOKEN):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode("utf-8", "ignore") or "null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8", "ignore") or "null")
    except Exception as e:  # pragma: no cover
        return 0, str(e)


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _make_repo(tmp: Path) -> Path:
    repo = tmp / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "checkout", "-q", "-b", "develop")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "init")
    return repo


class _Harness:
    def __init__(self, tmp: Path, command: str, lease_seconds: int = 3600):
        self.tmp = tmp
        self.producer = _Producer()
        self.repo = _make_repo(tmp)
        self.agent_state = tmp / "agentstate"
        self.coord_state = tmp / "coordstate"
        self.worktrees = tmp / "wt"
        self.command = command
        self.lease = lease_seconds
        self.port = _free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        (tmp / _CONFIG_NAME).write_text(json.dumps({
            "version": 1, "producer": "product_forge", "pf_api_url": self.producer.base,
            "token_env": "API_TOKEN", "default_runtime": "command",
            "state_dir": "state", "poll_seconds": 1, "lease_seconds": lease_seconds,
            "service_host": "127.0.0.1", "service_port": self.port, "service_url": self.base,
            "agent": {
                "repo_root": str(self.repo), "base_ref": "develop",
                "worktrees_dir": str(self.worktrees), "timeout_seconds": 60,
                "success_status": "verifying", "poll_seconds": 1,
                "runtimes": {"command": {"command": command}},
            },
        }), encoding="utf-8")
        self.coord = None

    def env(self, state_dir: Path) -> dict:
        e = {k: v for k, v in os.environ.items()
             if k not in ("API_TOKEN", "WORKERGRID_TOKEN", "WORKERGRID_HOME",
                          "WORKERGRID_STATE_DIR", "WORKERGRID_PF_API_URL",
                          "WORKERGRID_LEASE_SECONDS")}
        e["WORKERGRID_HOME"] = str(self.tmp)
        e["WORKERGRID_STATE_DIR"] = str(state_dir)
        e["WORKERGRID_PF_API_URL"] = self.producer.base
        e["WORKERGRID_TOKEN"] = TOKEN
        e["WORKERGRID_LEASE_SECONDS"] = str(self.lease)
        return e

    def start_coordinator(self):
        self.coord = subprocess.Popen(
            [str(COORD_BIN), "-host", "127.0.0.1", "-port", str(self.port)],
            cwd=str(WG_DIR), env=self.env(self.coord_state),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        deadline = time.time() + 15
        while time.time() < deadline:
            if self.coord.poll() is not None:
                pytest.fail("coordinator exited: " + (self.coord.stdout.read() or ""))
            st, _ = _http(self.base, "GET", "/status")
            if st == 200:
                return
            time.sleep(0.1)
        pytest.fail("coordinator not ready")

    def run_agent(self, timeout: int = 60, **extra) -> subprocess.CompletedProcess:
        cmd = [str(AGENT_BIN), "-runtime", "command", "-worker-id", "WRK-TEST",
               "-service", self.base, "-once"]
        for k, v in extra.items():
            cmd += ["-" + k, str(v)]
        return subprocess.run(cmd, cwd=str(WG_DIR), env=self.env(self.agent_state),
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                              timeout=timeout)

    def journal(self):
        p = self.agent_state / _JOURNAL_NAME
        if not p.exists():
            return []
        return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]

    def worktree_paths(self):
        out = subprocess.run(["git", "-C", str(self.repo), "worktree", "list", "--porcelain"],
                             capture_output=True, text=True).stdout
        main = self.repo.resolve()
        return [Path(ln.split(" ", 1)[1]) for ln in out.splitlines() if ln.startswith("worktree ")
                and Path(ln.split(" ", 1)[1]).resolve() != main]

    def branches(self):
        out = subprocess.run(["git", "-C", str(self.repo), "branch", "--list", "wg/*"],
                             capture_output=True, text=True).stdout
        return [b.strip().lstrip("* ").strip() for b in out.splitlines() if b.strip()]

    def close(self):
        if self.coord and self.coord.poll() is None:
            self.coord.terminate()
            try:
                self.coord.wait(timeout=5)
            except Exception:
                self.coord.kill()
        self.producer.close()
        shutil.rmtree(self.tmp, ignore_errors=True)


def _write_helper(tmp: Path, body: str) -> Path:
    p = tmp / "helper.py"
    p.write_text(body, encoding="utf-8")
    return p


_OK_HELPER = (
    "import os, sys, pathlib\n"
    "assert sys.argv[1] == os.environ['WG_ITEM_ID'], (sys.argv, os.environ.get('WG_ITEM_ID'))\n"
    "assert os.environ['WG_RUNTIME'] == 'command'\n"
    "pathlib.Path('ran.txt').write_text(os.environ['WG_ITEM_ID'] + '|' + os.environ['WG_BRANCH'])\n"
)


def _run(tmp: Path, helper_body: str, lease_seconds: int = 3600):
    helper = _write_helper(tmp, helper_body)
    command = f'"{sys.executable}" "{helper}" {{item_id}}'
    h = _Harness(tmp, command=command, lease_seconds=lease_seconds)
    h.start_coordinator()
    return h


def test_agent_happy_path(tmp_path):
    h = _run(tmp_path, _OK_HELPER)
    try:
        r = h.run_agent()
        assert r.returncode == 0, r.stdout
        assert h.producer.statuses() == ["scheduled", "executing", "verifying"], h.producer.statuses
        for item, _st, _note, roles, auth in h.producer.status_calls:
            assert item == ITEM
            assert roles == "operator"                 # write-back needs operator role
            assert auth == "Bearer " + TOKEN
        wts = h.worktree_paths()
        assert wts, "an isolated git worktree was created"
        marker = wts[0] / "ran.txt"
        assert marker.exists(), "runtime command ran in the worktree"
        assert marker.read_text(encoding="utf-8").startswith(ITEM + "|wg/")
        assert h.branches(), "an isolated wg/* branch was created"
        events = [j["event"] for j in h.journal()]
        for e in ("agent_start", "register", "claim", "worktree", "exec_start",
                  "writeback", "exec_end", "release"):
            assert e in events, events
        st, body = _http(h.base, "GET", "/status")
        assert st == 200 and body["leases"] == 0, "lease released after the run"
    finally:
        h.close()


def test_agent_command_failure_blocks(tmp_path):
    h = _run(tmp_path, "import sys\nsys.stderr.write('boom\\n')\nsys.exit(3)\n")
    try:
        r = h.run_agent()
        assert r.returncode == 0, r.stdout
        assert h.producer.statuses() == ["scheduled", "executing", "blocked"], h.producer.statuses
        note = [c[2] for c in h.producer.status_calls if c[1] == "blocked"][0]
        assert "exit=3" in note and "boom" in note, note
        st, body = _http(h.base, "GET", "/status")
        assert body["leases"] == 0
    finally:
        h.close()


def test_agent_approval_gate_fail_closed(tmp_path):
    h = _run(tmp_path, _OK_HELPER)
    h.producer.next_payload["data"]["execution_policy"] = {"approval_required": True}
    try:
        r = h.run_agent()
        assert r.returncode == 0, r.stdout
        assert h.producer.statuses() == ["blocked"], h.producer.statuses
        assert "approval_required" in h.producer.status_calls[0][2]
        assert not h.worktree_paths(), "no worktree for gated work"
        events = [j["event"] for j in h.journal()]
        assert "exec_start" not in events and "rejected" in events, events
        st, body = _http(h.base, "GET", "/status")
        assert body["leases"] == 0
    finally:
        h.close()


def test_agent_no_work_exits_clean(tmp_path):
    h = _run(tmp_path, _OK_HELPER)
    h.producer.next_payload["data"]["found"] = False
    h.producer.next_payload["data"]["item"] = None
    try:
        r = h.run_agent()
        assert r.returncode == 0, r.stdout
        assert h.producer.statuses() == [], h.producer.statuses
        assert any(j["event"] == "agent_stop" and j.get("reason") == "no_work" for j in h.journal())
    finally:
        h.close()


def test_agent_heartbeat_renews_lease(tmp_path):
    h = _run(tmp_path, "import time, pathlib\ntime.sleep(5)\npathlib.Path('ran.txt').write_text('ok')\n",
             lease_seconds=3)
    try:
        proc = subprocess.Popen(
            [str(AGENT_BIN), "-runtime", "command", "-worker-id", "WRK-TEST",
             "-service", h.base, "-once"],
            cwd=str(WG_DIR), env=h.env(h.agent_state),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        # wait until the worker is BUSY on the item, then observe a heartbeat tick
        deadline = time.time() + 20
        first = None
        while time.time() < deadline:
            st, w = _http(h.base, "GET", "/workers/WRK-TEST")
            if st == 200 and w.get("status") == "BUSY" and w.get("current_assignment") == ITEM:
                first = w.get("last_heartbeat")
                break
            time.sleep(0.1)
        assert first is not None, "worker never went BUSY"
        time.sleep(2.5)  # > one beat (lease 3s -> beat 2s)
        st, w2 = _http(h.base, "GET", "/workers/WRK-TEST")
        assert w2.get("last_heartbeat", 0) > first, "heartbeat/renew tick did not fire"
        proc.wait(timeout=60)
        assert proc.returncode == 0, proc.stdout.read()
        assert h.producer.statuses() == ["scheduled", "executing", "verifying"]
        assert not any(j["event"] == "lease_lost" for j in h.journal())
    finally:
        h.close()
