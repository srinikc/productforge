"""BI-PF-0432: grooming marks THIS item as a possible duplicate (advisory; same-project only).

Exercised at the marking unit: a scratch `_test_` project is excluded from `find_similar`'s scope-wide scan
(`_all_scopes` skips `_`-prefixed dirs), so the candidate set is supplied explicitly; and marking must NEVER
write across projects.
"""
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from core import backlog, grooming  # noqa: E402
from core.paths import PRODUCTS_DIR  # noqa: E402

_PROJ = "_test_grooming_dedup"


def _clean():
    shutil.rmtree(os.path.join(str(PRODUCTS_DIR), _PROJ), ignore_errors=True)


def _seed(title: str) -> str:
    return backlog.add_epic("project", _PROJ, title, body=title, tag="TST")["id"]


def _pair():
    a = _seed("zzq dedup marker alpha widget")
    b = _seed("zzq dedup marker beta widget")
    ia, ib = backlog.get("project", _PROJ, a), backlog.get("project", _PROJ, b)
    ordered = backlog.order_by_priority([ia, ib])
    return str(ordered[0]["id"]), str(ordered[1]["id"])   # (canonical, other)


def _link(iid):
    return (backlog.get("project", _PROJ, iid).get("links") or {}).get("possible_duplicate_of") or []


def test_marks_the_non_canonical_item():
    _clean()
    try:
        canon, other = _pair()
        ctx = {"similar": [{"id": canon, "scope": "project", "project": _PROJ, "score": 0.9, "title": "x"}]}
        marked = grooming._mark_duplicates("project", _PROJ, backlog.get("project", _PROJ, other), ctx)
        assert marked == [other], marked
        assert _link(other) == [backlog.qualify("project", _PROJ, canon)], _link(other)
        assert _link(canon) == [], "canonical untouched"
    finally:
        _clean()


def test_canonical_item_is_not_marked():
    _clean()
    try:
        canon, other = _pair()
        ctx = {"similar": [{"id": other, "scope": "project", "project": _PROJ, "score": 0.9}]}
        assert grooming._mark_duplicates("project", _PROJ, backlog.get("project", _PROJ, canon), ctx) == []
    finally:
        _clean()


def test_cross_project_candidates_are_never_marked():
    _clean()
    try:
        (a,) = [_seed("zzq dedup marker alpha widget")]
        ctx = {"similar": [{"id": "BI-0078", "scope": "project", "project": "ProductForge-Dashboard",
                            "score": 0.99}]}
        assert grooming._mark_duplicates("project", _PROJ, backlog.get("project", _PROJ, a), ctx) == []
    finally:
        _clean()


def test_low_score_is_not_marked():
    _clean()
    try:
        canon, other = _pair()
        ctx = {"similar": [{"id": canon, "scope": "project", "project": _PROJ, "score": 0.1}]}
        assert grooming._mark_duplicates("project", _PROJ, backlog.get("project", _PROJ, other), ctx) == []
    finally:
        _clean()
