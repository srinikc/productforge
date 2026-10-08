"""BI-PF-0435: human-approved consolidation - fold unique content + close the duplicate (preserved)."""
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from core import backlog, grooming  # noqa: E402
from core.paths import PRODUCTS_DIR  # noqa: E402

_PROJ = "_test_grooming_consolidate"


def _clean():
    shutil.rmtree(os.path.join(str(PRODUCTS_DIR), _PROJ), ignore_errors=True)


def _seed(title: str) -> str:
    return backlog.add_epic("project", _PROJ, title, body=title, tag="TST")["id"]


def test_consolidate_folds_unique_and_closes_duplicate():
    _clean()
    try:
        a = _seed("add csv export to the reports dashboard")
        b = _seed("add csv export to the reports dashboard and email digest")
        ia, ib = backlog.get("project", _PROJ, a), backlog.get("project", _PROJ, b)
        prop = grooming._build_proposal(ia, [ib])            # groom would store this
        _a = dict(ia.get("analysis") or {})
        _a["consolidation_proposal"] = prop
        backlog.update("project", _PROJ, a, analysis=_a)

        res = grooming.decide("project", _PROJ, a, "CONSOLIDATE", by="tester")
        assert res["applied"] is True and res["consolidated"] == [b], res

        ia2, ib2 = backlog.get("project", _PROJ, a), backlog.get("project", _PROJ, b)
        assert "email digest" in (ia2.get("body") or ""), "unique content folded into the canonical"
        assert backlog.qualify("project", _PROJ, b) in (ia2.get("links") or {}).get("consolidated_from", [])
        assert ib2["status"] == "duplicate", ib2["status"]
        assert backlog.qualify("project", _PROJ, a) in (ib2.get("links") or {}).get("duplicate_of", [])
        assert any(d.get("decision") == "CONSOLIDATE" for d in (ia2.get("decisions") or []))
    finally:
        _clean()


def test_consolidate_without_proposal_is_noop():
    _clean()
    try:
        a = _seed("zzq unique standalone item")
        res = grooming.decide("project", _PROJ, a, "CONSOLIDATE")
        assert res["applied"] is False, res
        assert backlog.get("project", _PROJ, a)["status"] != "duplicate"
    finally:
        _clean()
