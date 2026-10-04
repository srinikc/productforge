"""PFSSOT-P5 (BI-PF-0366): atomic claim + lease + recovery over the canonical backlog.

Also asserts IS-PF-0034 (single claimer): portfolio.enqueue/claim/finish delegate to job_manager.
"""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
os.environ.setdefault("PF_OFFLINE", "1")

from core import backlog, grooming, job_manager, portfolio  # noqa: E402
from core.paths import PRODUCTS_DIR  # noqa: E402

_PROJ = "_test_pfssot_p5"


def _clean():
    shutil.rmtree(os.path.join(str(PRODUCTS_DIR), _PROJ), ignore_errors=True)
    # job rows live in the shared portfolio DB; clear this project's row so tests are independent
    with __import__("contextlib").suppress(Exception):
        c = job_manager._db()
        c.execute("DELETE FROM jobs WHERE project=?", (_PROJ,))
        c.commit()
        c.close()


def _eligible_item(title="Feature A"):
    iid = backlog.add_epic("project", _PROJ, title, tag="TST")["id"]
    grooming.decide("project", _PROJ, iid, "APPROVE")
    return iid


def test_claim_lease_and_no_double_claim():
    _clean()
    try:
        iid = _eligible_item()
        r = job_manager.claim_next("project", _PROJ, worker="w1")
        assert r["claimed"] is True and r["item"] == iid
        assert r["lease_id"] and r["lease_expires_at"]
        ex = backlog.get("project", _PROJ, iid)["execution"]
        assert ex["worker_id"] == "w1" and ex["lease_id"] == r["lease_id"]
        # second worker must NOT get the same item
        r2 = job_manager.claim_next("project", _PROJ, worker="w2")
        assert r2["claimed"] is False
    finally:
        _clean()


def test_renew_and_release():
    _clean()
    try:
        iid = _eligible_item()
        job_manager.claim_next("project", _PROJ, worker="w1", lease_seconds=10)
        assert job_manager.renew_lease("project", _PROJ, iid, lease_seconds=999)["renewed"] is True
        assert job_manager.release("project", _PROJ, iid)["released"] is True
        ex = backlog.get("project", _PROJ, iid)["execution"]
        assert ex["worker_id"] == "" and ex["lease_id"] == ""
        # released -> claimable again
        assert job_manager.claim_next("project", _PROJ, worker="w2")["claimed"] is True
    finally:
        _clean()


def test_recover_expired_defaults_to_review():
    _clean()
    try:
        iid = _eligible_item()
        job_manager.claim_next("project", _PROJ, worker="w1")
        backlog.set_execution("project", _PROJ, iid, worker_id="w1",
                              lease_expires_at="2000-01-01T00:00:00")
        r = job_manager.recover_expired("project", _PROJ)
        assert r["count"] == 1 and r["policy"] == "REQUIRE_REVIEW"
        b = backlog.get("project", _PROJ, iid)
        assert b["status"] == "blocked" and b["execution"]["worker_id"] == ""
    finally:
        _clean()


def test_single_claimer_delegation():
    # IS-PF-0034: portfolio is a shim, not a second queue
    assert portfolio.claim.__module__ == "core.portfolio"
    r = portfolio.enqueue("_test_pfssot_p5_shim", priority=5, item_id="BI-X")
    assert r.get("project") == "_test_pfssot_p5_shim"
    # the job exists in job_manager's substrate
    assert job_manager._row(job_manager._db(), "_test_pfssot_p5_shim") is not None
    job_manager.finish("_test_pfssot_p5_shim", 0)
