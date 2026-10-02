"""ENG-8: shared-path reservations + merge gate + integration API."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
os.environ.setdefault("API_ALLOW_ANON", "1")

import contextlib

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.app import app  # noqa: E402
from core import paths as _paths  # noqa: E402

_SCRATCH = "_test_eng8"


def _force_rmtree(p) -> None:
    p = Path(p)
    if not p.exists():
        return
    for root, _dirs, files in os.walk(p, topdown=False):
        for name in files:
            with contextlib.suppress(Exception):
                os.chmod(os.path.join(root, name), 0o700)
    shutil.rmtree(p, ignore_errors=True)


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def resv_file(tmp_path, monkeypatch):
    monkeypatch.setenv("PF_RESERVATIONS_FILE", str(tmp_path / "reservations.json"))
    yield


@pytest.fixture()
def git_project():
    d = Path(_paths.PRODUCTS_DIR) / _SCRATCH
    wtr = Path(_paths.PRODUCTS_DIR) / (_SCRATCH + "-worktrees")
    _force_rmtree(wtr)
    _force_rmtree(d)
    d.mkdir(parents=True, exist_ok=True)

    def g(*a):
        subprocess.run(["git", *a], cwd=str(d), capture_output=True, text=True)

    g("init", "-q")
    g("config", "user.email", "t@local")
    g("config", "user.name", "t")
    (d / "README.md").write_text("x\n", encoding="utf-8")
    g("add", "-A")
    g("commit", "-q", "-m", "init")
    yield _SCRATCH
    _force_rmtree(wtr)
    _force_rmtree(d)


def test_reservations_acquire_conflict_release(client, resv_file):
    r = client.post("/api/v1/reservations", json={"resource": "core/x.py", "task_id": "T1"})
    assert r.status_code == 200
    conflict = client.post("/api/v1/reservations", json={"resource": "core/x.py", "task_id": "T2"})
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "CONFLICT"
    lst = client.get("/api/v1/reservations")
    assert lst.status_code == 200
    assert any(x["resource"] == "core/x.py" for x in lst.json()["data"])
    rel = client.post("/api/v1/reservations/release", json={"resource": "core/x.py"})
    assert rel.status_code == 200


def test_shared_paths_endpoint(client):
    r = client.get("/api/v1/reservations/shared-paths")
    assert r.status_code == 200
    assert "core" in r.json()["data"]["config"]["components"]


def test_merge_gate_and_integration(client, git_project):
    mg = client.get("/api/v1/validation/merge-gate", params={"scope": "project", "project": git_project})
    assert mg.status_code == 200
    assert mg.json()["data"]["can_merge"] is False  # no evidence -> blocked
    q = client.get("/api/v1/validation/merge-gate/queue", params={"scope": "project", "project": git_project})
    assert q.status_code == 200
    integ = client.post("/api/v1/validation/integration",
                        json={"scope": "project", "project": git_project})
    assert integ.status_code == 200
    assert integ.json()["data"]["result"] in ("PASS", "FAIL", "BLOCKED")
