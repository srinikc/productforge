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
