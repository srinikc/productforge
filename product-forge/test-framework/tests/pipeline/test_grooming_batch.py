"""BI-PF-1194: batch grooming (groom-all / review / approve-all).

Deterministic-path coverage (no live model): batch sizing, resumability, dry-run no-writes, the review
view, and approve-all clean-vs-flagged behavior (incl. --force).
"""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import backlog, grooming  # noqa: E402
from core.paths import PRODUCTS_DIR  # noqa: E402

_PROJ = "_test_groom_batch"


def _clean():
    shutil.rmtree(os.path.join(str(PRODUCTS_DIR), _PROJ), ignore_errors=True)


def _mk(title):
    return backlog.add_epic("project", _PROJ, title, body="x", tag="TST")["id"]


def _reset(iid):
    # add_epic auto-grooms deterministically on entry; reset to simulate an ungroomed item
    backlog.set_analysis("project", _PROJ, iid, status="NOT_ANALYZED", analysis={}, analyzed_by="")


def _status(iid):
    return (backlog.get("project", _PROJ, iid).get("analysis") or {}).get("status")


def test_default_batch_from_config():
    assert grooming.default_batch() >= 1
    assert grooming.guidelines().get("batch_size") == grooming.default_batch()


def test_groom_all_batches_and_resumes_skipping_complete():
    _clean()
    try:
        ids = [_mk(f"Item {n}") for n in range(3)]
        for iid in ids:
            _reset(iid)
        r = grooming.groom_all("project", _PROJ, mode="deterministic", batch=2)
        assert r["count"] == 3 and r["mode"] == "deterministic" and r["batch"] == 2
        assert set(r["groomed"]) == set(ids)
        for iid in ids:
            assert _status(iid) == "IN_PROGRESS"
        # approve one -> COMPLETE is skipped unless --force
        grooming.decide("project", _PROJ, ids[0], "APPROVE")
        r2 = grooming.groom_all("project", _PROJ, mode="deterministic", batch=2)
        assert r2["count"] == 2 and ids[0] not in r2["groomed"]
        r3 = grooming.groom_all("project", _PROJ, mode="deterministic", batch=2, force=True)
        assert r3["count"] == 3 and ids[0] in r3["groomed"]
    finally:
        _clean()


def test_groom_all_dry_makes_no_writes():
    _clean()
    try:
        iid = _mk("Dry item")
        _reset(iid)
        r = grooming.groom_all("project", _PROJ, mode="deterministic", dry=True)
        assert r["dry"] is True and r["count"] == 1
        assert r["items"][0]["id"] == iid
        assert _status(iid) == "NOT_ANALYZED"  # unchanged
    finally:
        _clean()


def test_review_lists_groomed_but_undecided():
    _clean()
    try:
        iid = _mk("Review item")
        _reset(iid)
        grooming.groom("project", _PROJ, iid, mode="deterministic")
        r = grooming.review("project", _PROJ)
        assert any(i["id"] == iid for i in r["items"])
    finally:
        _clean()


def test_approve_all_clean_then_force_for_flagged():
    _clean()
    try:
        clean = _mk("Clean item")
        backlog.set_analysis("project", _PROJ, clean, status="IN_PROGRESS",
                             analysis={"confidence": "high"}, analyzed_by="deterministic")
        # AI duplication_findings are ADVISORY -> must NOT block approval (BI-PF-1198)
        advisory = _mk("Advisory-dup item")
        backlog.set_analysis("project", _PROJ, advisory, status="IN_PROGRESS",
                             analysis={"confidence": "high", "duplication_findings": ["BI-X"]},
                             analyzed_by="deterministic")
        flagged = _mk("Low-confidence item")
        backlog.set_analysis("project", _PROJ, flagged, status="IN_PROGRESS",
                             analysis={"confidence": "low"}, analyzed_by="deterministic")

        r = grooming.decide_all("project", _PROJ, "APPROVE")
        assert clean in r["approved"]
        assert advisory in r["approved"]          # duplication_findings does NOT block
        assert flagged not in r["approved"]       # low-confidence does
        assert any(f["id"] == flagged for f in r["flagged"])
        assert _status(clean) == "COMPLETE"
        assert _status(flagged) == "IN_PROGRESS"

        r2 = grooming.decide_all("project", _PROJ, "APPROVE", force=True)
        assert flagged in r2["approved"]
        assert _status(flagged) == "COMPLETE"
    finally:
        _clean()


def test_approve_all_dry_does_not_change_status():
    _clean()
    try:
        iid = _mk("Dry approve")
        backlog.set_analysis("project", _PROJ, iid, status="IN_PROGRESS",
                             analysis={"confidence": "high"}, analyzed_by="deterministic")
        r = grooming.decide_all("project", _PROJ, "APPROVE", dry=True)
        assert iid in r["approved"] and r["dry"] is True
        assert _status(iid) == "IN_PROGRESS"
    finally:
        _clean()
