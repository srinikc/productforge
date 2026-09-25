"""
Tests for core/model_fit.py (BI-0076): probe tier models, report agent compatibility
(OK / AT_RISK / INCOMPATIBLE), recommend a same-tier substitution, and default to
applying the recommendation when the human does not answer.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import core.model_fit as mf  # noqa: E402

TIER = {
    "provider": "openrouter",
    "api_endpoint": "https://openrouter.ai/api/v1/chat/completions",
    "models": {
        "good-model": {"provider": "openrouter"},
        "bad-model": {"provider": "openrouter"},
    },
    "agents": {
        "design": {"model": "bad-model"},
        "architect": {"model": "good-model"},
    },
}


def test_tier_specs_groups_agents_by_model():
    specs = mf.tier_specs(TIER)
    assert set(specs) == {"good-model", "bad-model"}
    assert specs["bad-model"]["agents"] == ["design"]
    assert specs["good-model"]["agents"] == ["architect"]


def test_empty_content_model_is_incompatible_and_substituted():
    def probe(model, provider, endpoint, max_tokens):
        if model == "bad-model":
            return {"ok": False, "content_len": 0, "error": "empty content"}
        return {"ok": True, "content_len": 40}

    report = mf.run(TIER, probe)
    by_agent = {e["agent"]: e for e in report["entries"]}
    assert by_agent["design"]["status"] == mf.STATUS_INCOMPATIBLE
    assert by_agent["design"]["recommended_action"] == {"kind": "substitute", "model": "good-model"}
    assert by_agent["architect"]["status"] == mf.STATUS_OK
    assert report["summary"]["incompatible"] == 1


def test_default_applies_recommendation_when_unanswered():
    def probe(model, provider, endpoint, max_tokens):
        return ({"ok": False, "content_len": 0, "error": "empty"}
                if model == "bad-model" else {"ok": True, "content_len": 40})

    report = mf.apply_state(mf.run(TIER, probe), "")  # blank = default
    assert report["decision"] == "apply-recommendation"
    assert report["applied"]["design"]["source"] == "recommended"
    assert report["applied"]["design"]["model"] == "good-model"


def test_keep_answer_keeps_original_model():
    def probe(model, provider, endpoint, max_tokens):
        return ({"ok": False, "content_len": 0, "error": "empty"}
                if model == "bad-model" else {"ok": True, "content_len": 40})

    report = mf.apply_state(mf.run(TIER, probe), "keep")
    assert report["decision"] == "keep"
    assert report["applied"]["design"]["source"] == "human-keep"
    assert report["applied"]["design"]["model"] == "bad-model"


def test_report_roundtrip(tmp_path):
    report = mf.run(TIER, lambda *a: {"ok": True, "content_len": 40})
    mf.save_report(str(tmp_path), report)
    got = mf.load_report(str(tmp_path))
    assert got["summary"] == report["summary"]
