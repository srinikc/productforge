"""BI-PF-0419: external-worker assignment lifecycle (per-item claim + lease + API).

Core: claim_next is keyed by ITEM (not project) so N items in one project run in parallel; no double-claim;
capacity cap; renew/complete/fail/release/recover. API: the assignment endpoints require the `worker` role and
return the assignment package (worktree created at claim).
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from core import backlog, grooming, job_manager, capacity  # noqa: E402
from core.paths import PRODUCTS_DIR  # noqa: E402

_PROJ = "_test_assign_api"


def _clean():
    shutil.rmtree(os.path.join(str(PRODUCTS_DIR), _PROJ), ignore_errors=True)
    shutil.rmtree(os.path.join(str(PRODUCTS_DIR), _PROJ + "-worktrees"), ignore_errors=True)
    try:
        c = job_manager._db()
        c.execute("DELETE FROM jobs WHERE project=?", (_PROJ,))
        c.commit()
        c.close()
    except Exception:
        pass


def _seed(n):
    ids = []
    for k in range(n):
        iid = backlog.add_epic("project", _PROJ, f"assignment item {k}", tag="TST")["id"]
        grooming.decide("project", _PROJ, iid, "APPROVE")
        ids.append(iid)
    return ids


def test_claim_next_is_per_item_parallel():
    _clean()
    try:
        _seed(3)
        r1 = job_manager.claim_next("project", _PROJ, worker="w1")
        r2 = job_manager.claim_next("project", _PROJ, worker="w2")
        assert r1["claimed"] and r2["claimed"], (r1, r2)
        assert r1["item"] != r2["item"], "two items in ONE project claimed in parallel"
        assert (backlog.get("project", _PROJ, r1["item"])["execution"]["worker_id"] == "w1")
    finally:
        _clean()


def test_no_double_claim_and_release_requeues():
    _clean()
    try:
        (iid,) = _seed(1)
        assert job_manager.claim_next("project", _PROJ, worker="w1")["claimed"] is True
        assert job_manager.claim_next("project", _PROJ, worker="w2")["claimed"] is False
        assert job_manager.release("project", _PROJ, iid)["released"] is True
        assert job_manager.claim_next("project", _PROJ, worker="w2")["claimed"] is True
    finally:
        _clean()


def test_capacity_cap_denies_extra_assignment(monkeypatch):
    _clean()
    try:
        monkeypatch.setattr(capacity, "max_parallel_assignments", lambda: 2)
        _seed(3)
        assert job_manager.claim_next("project", _PROJ, worker="w1")["claimed"] is True
        assert job_manager.claim_next("project", _PROJ, worker="w2")["claimed"] is True
        r3 = job_manager.claim_next("project", _PROJ, worker="w3")
        assert r3["claimed"] is False and "assignment slot" in r3["reason"], r3
    finally:
        _clean()


def test_complete_fail_release_clear_the_lease():
    _clean()
    try:
        _seed(2)
        a = job_manager.claim_next("project", _PROJ, worker="w1")["item"]
        assert job_manager.complete("project", _PROJ, a)["status"] == "verifying"
        exa = backlog.get("project", _PROJ, a)["execution"]
        assert exa["worker_id"] == "" and exa["lease_expires_at"] == ""

        b = job_manager.claim_next("project", _PROJ, worker="w2")["item"]
        assert job_manager.fail("project", _PROJ, b, reason="boom")["status"] == "blocked"
        assert backlog.get("project", _PROJ, b)["status"] == "blocked"
    finally:
        _clean()


def _init_repo(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True, capture_output=True)
    (path / "README.md").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "init"],
                   cwd=path, check=True, capture_output=True)


def test_assignment_api_roundtrip_and_worker_role(monkeypatch):
    _clean()
    monkeypatch.setenv("API_ALLOW_ANON", "1")
    monkeypatch.setenv("WORKERGRID_PF_API_URL", "")
    from fastapi.testclient import TestClient
    from api.app import app
    client = TestClient(app)
    try:
        proj_dir = Path(str(PRODUCTS_DIR)) / _PROJ
        _init_repo(proj_dir)
        _seed(1)

        # claim -> assignment package with a worktree
        r = client.post("/api/v1/engineering/assignments/claim",
                        json={"scope": "project", "project": _PROJ, "worker_id": "WRK-A"})
        assert r.status_code == 200, r.text
        pkg = r.json()["data"]
        assert pkg["assigned"] is True and pkg["item_id"] and pkg["worktree"], pkg
        assert Path(pkg["worktree"]).exists(), pkg["worktree"]

        item = pkg["item_id"]
        assert client.post(f"/api/v1/engineering/assignments/{item}/heartbeat",
                           json={"scope": "project", "project": _PROJ}).json()["data"]["renewed"] is True
        done = client.post(f"/api/v1/engineering/assignments/{item}/complete",
                           json={"scope": "project", "project": _PROJ}).json()["data"]
        assert done["ok"] is True and done["status"] == "verifying"
    finally:
        _clean()


def test_assignment_api_requires_worker_role(monkeypatch):
    monkeypatch.delenv("API_ALLOW_ANON", raising=False)
    monkeypatch.setenv("API_TOKEN", "t")
    from fastapi.testclient import TestClient
    from api.app import app
    client = TestClient(app)
    # no worker/operator role -> forbidden
    r = client.post("/api/v1/engineering/assignments/claim", json={},
                    headers={"Authorization": "Bearer t"})
    assert r.status_code == 403, r.text
    # worker role -> passes auth (then fails for a non-repo project, which is fine)
    r2 = client.post("/api/v1/engineering/assignments/claim",
                     json={"scope": "project", "project": "_test_assign_api"},
                     headers={"Authorization": "Bearer t", "X-Roles": "worker"})
    assert r2.status_code in (200, 404, 409), r2.text
