"""BI-PF-0430: pre-commit branch guard - never commit feature work directly on develop/main."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from scripts.dev import branch_guard as bg  # noqa: E402


def test_decision_table():
    assert bg.evaluate("feature/x", False, False)[0] is True        # feature branch ok
    assert bg.evaluate("develop", False, False)[0] is False         # direct commit blocked
    assert bg.evaluate("main", False, False)[0] is False
    assert bg.evaluate("master", False, False)[0] is False
    assert bg.evaluate("develop", True, False)[0] is True           # merge commit allowed
    assert bg.evaluate("develop", False, True)[0] is True           # explicit override
    assert bg.evaluate("", False, False)[0] is True                 # detached HEAD (rebase)


def test_bookkeeping_only_allowed_on_protected():
    bk = ["product-forge/data/backlog/items/BI-X.json", "product-forge/docs/BACKLOG-SUMMARY.md"]
    assert bg.evaluate("develop", False, False, staged=bk)[0] is True     # provenance write allowed
    assert bg.evaluate("develop", False, False,
                       staged=bk + ["product-forge/core/scheduler.py"])[0] is False  # any feature file blocks
    assert bg.evaluate("develop", False, False, staged=[])[0] is False    # nothing staged -> block


def test_mixed_backlog_store_commit_blocked_anywhere():
    mixed = ["product-forge/data/backlog/items/BI-X.json", "product-forge/config/knowledge-registry.json"]
    ok, reason = bg.evaluate("feature/x", False, False, staged=mixed)     # even on a feature branch
    assert ok is False and "mixed commit" in reason
    assert bg.evaluate("feature/x", False, False, staged=["product-forge/core/x.py"])[0] is True
    assert bg.evaluate("feature/x", False, False,
                       staged=["product-forge/data/backlog/open.json"])[0] is True   # store-only ok


def test_main_exit_codes(monkeypatch):
    monkeypatch.setattr(bg, "current_branch", lambda: "develop")
    monkeypatch.setattr(bg, "is_merge_in_progress", lambda: False)
    monkeypatch.setattr(bg, "staged_paths", lambda: [])
    monkeypatch.delenv("PF_ALLOW_DIRECT_COMMIT", raising=False)
    assert bg.main() == 1
    monkeypatch.setattr(bg, "current_branch", lambda: "feature/ok")
    assert bg.main() == 0
