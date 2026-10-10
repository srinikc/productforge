"""BI-PF-0419: external-worker assignment lifecycle (per-item claim + lease + API).

Core: claim_next is keyed by ITEM (not project) so N items in one project run in parallel; no double-claim;
capacity cap; renew/complete/fail/release/recover. API: the assignment endpoints require the `worker` role and
return the assignment package (worktree created at claim).
"""
import os
import shutil
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
    # BI-PF-0442: use DISTINCT titles so this tests per-item PARALLELISM (BI-PF-0419), not claim-time dedup
    # (BI-PF-0422, covered by test_assignment_dedup.py). Near-identical titles are intentionally collapsed.
    titles = ["wire the payment webhook handler", "render the usage analytics graph",
              "harden the CSV import validator", "add the audit-log retention job"]
    ids = []
    for k in range(n):
        iid = backlog.add_epic("project", _PROJ, titles[k % len(titles)], tag="TST")["id"]
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


def test_claim_next_scoped_to_epic():
    """BI-PF-1222: claim_next(epic=) restricts the pick to that epic's children, not the whole backlog."""
    _clean()
    try:
        ep = backlog.add_epic("project", _PROJ, "Epic container", type_="epic", tag="TST")["id"]
        outside = backlog.add_epic("project", _PROJ, "outside work item alpha", tag="TST")["id"]
        child = backlog.add_epic("project", _PROJ, "child work item beta", epic=ep, tag="TST")["id"]
        grooming.decide("project", _PROJ, outside, "APPROVE")
        grooming.decide("project", _PROJ, child, "APPROVE")
        backlog.set_priority("project", _PROJ, outside, priority_rank=0)   # outside outranks the child
        backlog.set_priority("project", _PROJ, child, priority_rank=5)
        r = job_manager.claim_next("project", _PROJ, worker="w1", epic=ep)
        assert r["claimed"] and r["item"] == child, r
        assert backlog.get("project", _PROJ, child)["execution"]["worker_id"] == "w1"
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


# NOTE (BI-PF-0427): the API claim roundtrip can no longer be exercised with scope=project (the worker
# boundary is product_forge-only) and must NOT claim a real product_forge backlog item - so the API surface is
# covered by the scope-guard + role tests below, and the claim/lease/complete mechanism at the core level above.


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
    # worker role -> passes auth, then the scope guard rejects project (BI-PF-0427)
    r2 = client.post("/api/v1/engineering/assignments/claim",
                     json={"scope": "project", "project": "_test_assign_api"},
                     headers={"Authorization": "Bearer t", "X-Roles": "worker"})
    assert r2.status_code in (400, 422), r2.text


def test_worker_path_is_product_forge_only(monkeypatch):
    """BI-PF-0427: the worker/assignment path (API boundary) executes PF's own backlog only."""
    monkeypatch.setenv("API_ALLOW_ANON", "1")
    from fastapi.testclient import TestClient
    from api.app import app
    client = TestClient(app)
    r1 = client.post("/api/v1/engineering/assignments/claim",
                     json={"scope": "project", "project": _PROJ})
    assert r1.status_code in (400, 422), r1.text
    r2 = client.get(f"/api/v1/engineering/schedule/next?stage=execute&scope=project&project={_PROJ}")
    assert r2.status_code in (400, 422), r2.text


def test_complete_records_duration_for_time_tracking():
    """BI-PF-1237: complete() records execution.duration_seconds + attempt; backlog_status rolls up time."""
    _clean()
    try:
        (iid,) = _seed(1)
        assert job_manager.claim_next("project", _PROJ, worker="w1")["claimed"] is True
        res = job_manager.complete("project", _PROJ, iid)
        assert res["ok"] and "duration_seconds" in res
        ex = backlog.get("project", _PROJ, iid)["execution"]
        assert "duration_seconds" in ex and int(ex["duration_seconds"]) >= 0
        assert int(ex.get("attempt") or 0) == 1
        from core import scheduler
        st = scheduler.backlog_status("project", _PROJ)
        assert "time" in st["rollup"] and "total_seconds" in st["rollup"]["time"]
    finally:
        _clean()
