"""ENG-6: Common Validation Engine profiles + run API."""
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

_SCRATCH = "_test_validation_engine_api"


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


def test_validation_profiles(client):
    r = client.get("/api/v1/validation/profiles")
    assert r.status_code == 200
    profs = r.json()["data"]["profiles"]
    assert {"FEATURE_PR", "INTEGRATION", "DOGFOOD", "RELEASE"} <= set(profs)


def test_validation_engine_run(client, git_project):
    body = {"scope": "project", "project": git_project, "profile": "FEATURE_PR"}
    r = client.post("/api/v1/validation/run", json=body)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["result"] in ("PASS", "FAIL", "BLOCKED")
    assert d["target_resolved"]["ok"] is True
    assert "checks" in d
    runs = client.get("/api/v1/validation/runs", params={"scope": "project", "project": git_project})
    assert runs.status_code == 200
    assert any(x["run_id"] == d["run_id"] for x in runs.json()["data"])


def test_feature_pr_validation(client, git_project):
    body = {"scope": "project", "project": git_project, "use_worktree": True}
    r = client.post("/api/v1/validation/feature-pr", json=body)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["result"] in ("PASS", "FAIL", "BLOCKED")
    assert d["auto_repair"] is False
    assert "changed_files" in d and "impact" in d and "github_evidence" in d["checks"]


def test_validation_engine_unknown_profile(client, git_project):
    r = client.post("/api/v1/validation/run",
                    json={"scope": "project", "project": git_project, "profile": "NOPE"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_FAILED"
