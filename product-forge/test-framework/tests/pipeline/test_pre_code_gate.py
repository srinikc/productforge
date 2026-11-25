"""Unit tests for author-time pre-code Gate 1 guardrail (scripts/dev/pre_code_gate.py)."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from scripts.dev import pre_code_gate as pcg  # noqa: E402
from scripts.dev import gate_predicates as gp  # noqa: E402


def test_self_test_matrix_passes():
    assert pcg.self_test() == 0


def test_path_categorization():
    non_code_samples = [
        "data/backlog/items/BI-PF-1552.json",
        "product-forge/data/backlog/items/BI-PF-1552.json",
        "docs/ARCHITECTURE.md",
        "product-forge/docs/BACKLOG-SUMMARY.md",
        "engineering/reviews/BI-PF-1552-sha.json",
        "engineering/trails/BI-PF-1552.json",
        "issues/items/IS-PF-001.json",
        "engineering/changes.jsonl",
        "scratch/scratch.py",
        "README.md",
        ".gitignore",
    ]
    for p in non_code_samples:
        assert pcg.is_non_code_path(p) is True, f"expected {p} to be non-code"

    code_samples = [
        "core/scheduler.py",
        "product-forge/core/backlog.py",
        "go/worker/main.go",
        "test-framework/tests/pipeline/test_x.py",
        "migrations/001_init.sql",
        "api/routers/backlog.py",
        "config/env-flags.json",
    ]
    for p in code_samples:
        assert pcg.is_non_code_path(p) is False, f"expected {p} to be code"


def test_blocks_code_when_no_gate_approval():
    view = {
        "parsed_ok": True,
        "blocking": [],
        "dispositions": {},
        "review": {"sha": "sha_abc", "at": "2026-01-01T00:00:00+00:00"},
    }
    item_unapproved = {"id": "BI-PF-1000", "decisions": []}
    orig_sha = pcg.ar.design_sha
    pcg.ar.design_sha = lambda it: "sha_abc"
    try:
        ok, reason, code_files = pcg.evaluate(
            "feat/bi-pf-1000-feature",
            ["core/service.py"],
            item_override=item_unapproved,
            view_override=view,
        )
        assert ok is False
        assert reason == "NO_GATE_APPROVAL"
        assert code_files == ["core/service.py"]
    finally:
        pcg.ar.design_sha = orig_sha


def test_allows_code_when_gate1_approved():
    view = {
        "parsed_ok": True,
        "blocking": [],
        "dispositions": {"sig:1": {"status": "ACTIONED"}},
        "review": {"sha": "sha_abc", "at": "2026-01-01T00:00:00+00:00"},
    }
    digest = gp.findings_digest(view)
    item_approved = {
        "id": "BI-PF-1000",
        "decisions": [
            {
                "gate": 1,
                "decision": "APPROVE",
                "by": "hil:lead",
                "at": "2026-01-02T00:00:00+00:00",
                "findings_sha": "sha_abc",
                "findings_digest": digest,
                "seq": 1,
            }
        ],
    }
    orig_sha = pcg.ar.design_sha
    pcg.ar.design_sha = lambda it: "sha_abc"
    try:
        ok, reason, code_files = pcg.evaluate(
            "feat/bi-pf-1000-feature",
            ["core/service.py"],
            item_override=item_approved,
            view_override=view,
        )
        assert ok is True
        assert reason == "OK"
        assert code_files == []
    finally:
        pcg.ar.design_sha = orig_sha


def test_bypass_env_override():
    item_unapproved = {"id": "BI-PF-1000", "decisions": []}
    ok, reason, code_files = pcg.evaluate(
        "feat/bi-pf-1000-feature",
        ["core/service.py"],
        env={"PF_ALLOW_UNAPPROVED_CODE": "1"},
        item_override=item_unapproved,
        view_override=None,
    )
    assert ok is True
    assert reason == "BYPASS_ENV"
