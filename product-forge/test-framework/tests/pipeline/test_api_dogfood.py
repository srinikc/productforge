"""ENG-9: DOGFOOD execution API (dry, fail-closed)."""
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
from core import dogfood as _dog  # noqa: E402
from core import paths as _paths  # noqa: E402

_SCRATCH = "_test_dogfood_api"


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
def git_project():
    d = Path(_paths.PRODUCTS_DIR) / _SCRATCH
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
    _force_rmtree(d)


def test_dogfood_dry(client, git_project):
    r = client.post("/api/v1/validation/dogfood",
                    json={"scope": "project", "project": git_project, "dry": True})
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["result"] in _dog.STATES
    assert d["result"] != "PASS"          # dry is never a full pass
    assert d["run_id"].startswith("dog-")
    assert d["baseline"]["ok"] is True


def test_dogfood_unknown_project(client):
    r = client.post("/api/v1/validation/dogfood",
                    json={"scope": "project", "project": "nope-xyz", "dry": True})
    assert r.status_code == 404
