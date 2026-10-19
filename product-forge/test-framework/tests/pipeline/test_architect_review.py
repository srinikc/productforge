"""BI-PF-1427: Gate 2.5 architect-review helper - structured findings parsing."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.dev import architect_review as ar  # noqa: E402


def test_parse_review_sections():
    text = (
        "### BLOCKER\n- secret in log\n"
        "### MAJOR\n- no test for the new path\n"
        "### MINOR\n- naming\n"
        "### NIT\n- spacing\n"
        "### SUMMARY\n- overall fine once blocker fixed\n"
    )
    r = ar.parse_review(text)
    assert r["BLOCKER"] == ["secret in log"]
    assert r["MAJOR"] == ["no test for the new path"]
    assert r["MINOR"] == ["naming"]
    assert r["NIT"] == ["spacing"]
    assert r["SUMMARY"] == ["overall fine once blocker fixed"]


def test_parse_review_empty():
    r = ar.parse_review("no findings")
    assert all(r[s] == [] for s in ar.SEVERITIES)


def test_iter_findings_canonical_order():
    f = {"NIT": ["n1"], "BLOCKER": ["b1", "b2"], "MINOR": ["m1"], "MAJOR": ["j1"]}
    assert list(ar.iter_findings(f)) == [
        ("BLOCKER", "b1"), ("BLOCKER", "b2"), ("MAJOR", "j1"), ("MINOR", "m1"), ("NIT", "n1"),
    ]


def test_pending_blocking_only_blocks_blocker_and_major():
    f = {"BLOCKER": ["b"], "MAJOR": ["j"], "MINOR": ["m"], "NIT": ["n"]}
    # all pending -> the two high severities block; total/pending count all
    total, pending, blocking = ar.pending_blocking(f, {})
    assert (total, pending) == (4, 4)
    assert [s for _, s, _ in blocking] == ["BLOCKER", "MAJOR"]

    disp = {"1": {"status": "actioned"}, "2": {"status": "deferred"}, "3": {"status": "PENDING"}}
    total, pending, blocking = ar.pending_blocking(f, disp)
    assert (total, pending, blocking) == (4, 2, [])
    # a pending MINOR/NIT never blocks
    assert blocking == []

