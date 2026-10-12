"""BI-PF-1257: durable-state checkpoint - allowlist correctness + clean/no-remote no-ops."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from core import state_checkpoint as sc  # noqa: E402
from core import vcs  # noqa: E402


def test_is_durable_allowlist():
    durable = [
        "data/backlog/items/BI-X.json",
        "product-forge/data/backlog/items/BI-X.json",
        "data/backlog/open.json",
        "data/backlog/closed.json",
        "data/backlog/counters.json",
        "data/backlog/history/BI-X.jsonl",
        "issues/items/IS-PF-finding",
        "issues/open.json",
        "config/id-blocks.json",
        "data/portfolio/portfolio-registry.json",
    ]
    for p in durable:
        assert sc._is_durable(p), p
    # ephemeral runtime stores must NOT be checkpointed
    ephemeral = [
        "events.jsonl", "product-forge/events.jsonl", "quality-gate.json",
        "validation/validation-runs.json", "github/pr-record",
        "data/provider-health.json", "data/portfolio/portfolio-state.json",
        "products/default/run-artifact", "test-framework/results/qir-report",
        "core/state_checkpoint.py",
    ]
    for p in ephemeral:
        assert not sc._is_durable(p), p


def test_checkpoint_skips_without_remote(monkeypatch):
    class _V:
        def __init__(self, *a, **k):
            pass

        def is_repo(self):
            return True

        def has_remote(self):
            return False

    monkeypatch.setattr(vcs, "VCSManager", _V)
    r = sc.checkpoint("x")
    assert r.get("ok") is True and r.get("skipped") == "no remote"


def test_checkpoint_skips_when_clean(monkeypatch):
    class _V:
        def __init__(self, *a, **k):
            pass

        def is_repo(self):
            return True

        def has_remote(self):
            return True

    monkeypatch.setattr(vcs, "VCSManager", _V)
    monkeypatch.setattr(sc, "durable_changes", lambda: [])
    r = sc.checkpoint("x")
    assert r.get("ok") is True and r.get("skipped") == "clean"
