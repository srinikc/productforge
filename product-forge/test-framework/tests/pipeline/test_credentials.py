"""BI-0207: provider credential + budget registry."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from core import credentials as C  # noqa: E402


def test_key_for_reads_process_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-123")
    assert C.key_for("openrouter") == "test-key-123"
    assert C.has("openrouter") is True


def test_missing_key_is_empty(monkeypatch):
    monkeypatch.delenv("OPENCODE_ZEN_API_KEY", raising=False)
    # unknown/empty -> resolves the default env var, absent -> ""
    assert C.key_for("opencode-go") == ""


def test_provider_metadata():
    assert C.provider_kind("openrouter") == "aggregator"
    assert C.provider_kind("openai") == "direct"
    assert "tts" in C.required_for("elevenlabs")
    assert "video" in C.required_for("fal")


def test_missing_for_kinds(monkeypatch):
    for p in ("FAL_KEY", "REPLICATE_API_TOKEN", "KIE_API_KEY"):
        monkeypatch.delenv(p, raising=False)
    miss = dict((prov, env) for prov, env in C.missing_for(["video"]))
    assert "fal" in miss and miss["fal"] == "FAL_KEY"


def test_budget_caps(monkeypatch):
    # uncapped by default -> ok
    ok, reason = C.check_budget("openrouter", spent_usd=999, run_spent_usd=999)
    assert ok is True and reason == ""

    monkeypatch.setattr(C, "_cache", {"budget": {"per_run_cap_usd": 10, "per_provider_cap_usd": 5}})
    ok, reason = C.check_budget("openrouter", spent_usd=1, run_spent_usd=11)
    assert ok is False and "per-run" in reason
    ok, reason = C.check_budget("openrouter", spent_usd=6, run_spent_usd=1)
    assert ok is False and "per-provider" in reason
    ok, reason = C.check_budget("openrouter", spent_usd=3, run_spent_usd=3)
    assert ok is True


def test_status_redacts_values(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "supersecret")
    st = C.status()
    assert st["providers"]["openrouter"]["key_set"] is True
    assert "supersecret" not in str(st)
