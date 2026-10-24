"""Branch/item guard tests (BI-PF-1472)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

from branch_item_check import check  # noqa: E402


def test_match():
    assert check("feat/bi-pf-1308-x", "BI-PF-1308: work")[0]


def test_wrong_item_blocked():
    ok, why = check("feat/bi-pf-1308-x", "BI-PF-1471: work")
    assert not ok and "BI-PF-1471" in why


def test_missing_id_blocked():
    assert not check("feat/bi-pf-1308-x", "chore: no id")[0]


def test_merge_skipped():
    assert check("feat/bi-pf-1308-x", "Merge pull request #1")[0]


def test_branch_without_item_warns_only():
    assert check("develop", "BI-PF-1308: work")[0]
