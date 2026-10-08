"""BI-PF-0432: grooming marks near-duplicate items (advisory links.possible_duplicate_of).

Exercised at the marking unit (a scratch `_test_` project is intentionally excluded from `find_similar`'s
scope-wide scan - `_all_scopes` skips `_`-prefixed dirs), so the candidate set is supplied explicitly.
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


def test_mark_duplicates_marks_only_the_non_canonical():
    _clean()
    try:
        a = _seed("zzq dedup marker alpha widget")
        b = _seed("zzq dedup marker beta widget")
        ia = backlog.get("project", _PROJ, a)
        ctx = {"similar": [{"id": b, "scope": "project", "project": _PROJ, "ref": f"project:{_PROJ}:{b}",
                            "score": 0.7, "title": "zzq dedup marker beta widget"}]}
        marked = grooming._mark_duplicates("project", _PROJ, ia, ctx)
        assert len(marked) == 1, marked

        la = (backlog.get("project", _PROJ, a).get("links") or {}).get("possible_duplicate_of") or []
        lb = (backlog.get("project", _PROJ, b).get("links") or {}).get("possible_duplicate_of") or []
        assert bool(la) ^ bool(lb), f"exactly one marked: {la} / {lb}"
        marked_id, link = (a, la) if la else (b, lb)
        other = b if la else a
        canon_ref = backlog.qualify("project", _PROJ, other)
        assert link == [canon_ref], f"{marked_id} -> {link}, expected [{canon_ref}]"
    finally:
        _clean()


def test_no_candidates_no_marking():
    _clean()
    try:
        a = _seed("zzq dedup marker alpha widget")
        ia = backlog.get("project", _PROJ, a)
        assert grooming._mark_duplicates("project", _PROJ, ia, {"similar": []}) == []
        assert not (backlog.get("project", _PROJ, a).get("links") or {}).get("possible_duplicate_of")
    finally:
        _clean()
