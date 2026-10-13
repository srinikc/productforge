"""BI-PF-1319: grooming/regroom finalize every item OR surface an explicit decision request - never strand."""
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from core import backlog, grooming  # noqa: E402
from core.paths import PRODUCTS_DIR  # noqa: E402

_P = "_test_groom_resolution"
_GOOD = ("## Problem / why\nthe thing breaks\n## Goal\nfix it\n## In scope\nthe fix\n"
         "## Acceptance criteria\nit works\n## Approach\npatch it\n")


def _clean():
    shutil.rmtree(os.path.join(str(PRODUCTS_DIR), _P), ignore_errors=True)


def _reset(iid):
    # a created item is auto-approved (BI-PF-1282); force the un-groomed state to exercise grooming
    backlog.set_analysis("project", _P, iid, status="NOT_ANALYZED", analysis={}, analyzed_by="")


def _req(iid):
    return (backlog.get_epic("project", _P, iid).get("analysis") or {}).get("decision_request") or {}


def test_missing_info_becomes_decision_request():
    _clean()
    try:
        iid = backlog.add_epic("project", _P, "thin item", body="", tag="TST")["id"]
        _reset(iid)
        grooming.groom("project", _P, iid, mode="deterministic")
        r = _req(iid)
        assert r.get("needed") is True, r
        assert "missing_info" in (r.get("reasons") or []), r
        assert r.get("ask"), r
    finally:
        _clean()


def test_unmet_dep_becomes_decision_request():
    _clean()
    try:
        a = backlog.add_epic("project", _P, "dep A", body=_GOOD, tag="TST")["id"]
        b = backlog.add_epic("project", _P, "needs A", body=_GOOD, tag="TST")["id"]
        backlog.set_dependencies("project", _P, b,
                                 dependencies=[{"task_id": a, "type": "REQUIRES", "required_state": "COMPLETE"}])
        _reset(b)
        grooming.groom("project", _P, b, mode="deterministic")
        assert "unmet_deps" in (_req(b).get("reasons") or []), _req(b)
    finally:
        _clean()


def test_groom_all_leaves_no_silent_in_progress():
    _clean()
    try:
        ids = [backlog.add_epic("project", _P, f"thin {i}", body="", tag="TST")["id"] for i in range(3)]
        for i in ids:
            _reset(i)
        grooming.groom_all("project", _P, mode="deterministic")
        for it in backlog.list_open("project", _P, order=False):
            if backlog.is_epic(it):
                continue
            a = it.get("analysis") or {}
            if str(a.get("status") or "NOT_ANALYZED") in ("IN_PROGRESS", "NOT_ANALYZED"):
                assert (a.get("decision_request") or {}).get("needed") is True, (it["id"], a.get("status"))
    finally:
        _clean()


def test_groom_all_rerun_finalizes_or_surfaces():
    _clean()
    try:
        ids = [backlog.add_epic("project", _P, f"thin {i}", body="", tag="TST")["id"] for i in range(2)]
        for i in ids:
            _reset(i)
        grooming.groom_all("project", _P, mode="deterministic")
        grooming.groom_all("project", _P, mode="deterministic")   # re-run must not strand
        for row in grooming.stranded("project", _P)["items"]:
            assert row.get("ask"), row
    finally:
        _clean()


def test_decide_clears_request_and_completes():
    _clean()
    try:
        iid = backlog.add_epic("project", _P, "thin item", body="", tag="TST")["id"]
        _reset(iid)
        grooming.groom("project", _P, iid, mode="deterministic")
        assert _req(iid).get("needed") is True
        grooming.decide("project", _P, iid, "APPROVE")
        a = backlog.get_epic("project", _P, iid).get("analysis") or {}
        assert a.get("status") == "COMPLETE"
        assert _req(iid).get("needed") is False
    finally:
        _clean()


def test_approve_clean_item_completes_and_clears():
    _clean()
    try:
        iid = backlog.add_epic("project", _P, "clean item", body=_GOOD, tag="TST")["id"]
        backlog.set_analysis("project", _P, iid, status="IN_PROGRESS",
                             analysis={"confidence": "high"}, analyzed_by="deterministic")
        grooming.decide_all("project", _P, "APPROVE")
        a = backlog.get_epic("project", _P, iid).get("analysis") or {}
        assert a.get("status") == "COMPLETE", a
        assert _req(iid).get("needed") is False
    finally:
        _clean()


def test_review_includes_decision_request():
    _clean()
    try:
        iid = backlog.add_epic("project", _P, "thin item", body="", tag="TST")["id"]
        _reset(iid)
        grooming.groom("project", _P, iid, mode="deterministic")
        row = next(x for x in grooming.review("project", _P)["items"] if x["id"] == iid)
        assert row.get("decision_request") is not None
    finally:
        _clean()
