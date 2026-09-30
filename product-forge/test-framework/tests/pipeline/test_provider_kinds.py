"""BI-0193: provider-kind abstraction + kind-aware routing (fail-closed)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import provider_kinds as pk  # noqa: E402


def test_kind_of_matches_credentials():
    for prov, kind in (("opencode-go", "direct"), ("openrouter", "aggregator"),
                       ("gemini", "direct"), ("fal", "aggregator")):
        assert pk.kind_of(prov) == kind, prov
    assert pk.kind_of("does-not-exist") == ""  # unknown => "" (fail-closed)


def test_order_candidates_annotates_kind_and_orders():
    cands = [
        {"model": "a", "provider": "openrouter"},   # aggregator
        {"model": "b", "provider": "opencode-go"},  # direct
        {"model": "c", "provider": "nope"},         # unknown -> kind=""
    ]
    out = pk.order_candidates(cands)          # default: annotate-only (blocking = model_gate)
    assert [c["model"] for c in out] == ["a", "b", "c"]
    assert out[0]["kind"] == "aggregator" and out[1]["kind"] == "direct" and out[2]["kind"] == ""

    strict = pk.order_candidates(cands, reject_unknown=True)   # strict fail-closed: drop unknown
    assert [c["model"] for c in strict] == ["a", "b"]

    pref = pk.order_candidates(cands, prefer_kind="direct")
    assert pref[0]["model"] == "b"


def test_supports_fail_closed():
    assert pk.supports("openai", "images") is True
    assert pk.supports("openai", "tools") is True
    assert pk.supports("opencode-go", "images") is False   # not declared
    assert pk.supports("nope", "chat") is False            # unknown provider
    assert pk.supports("openai", "bogus-feature") is False  # unknown feature


def test_headers_and_extract_content():
    h = pk.headers("opencode-go", "k", "sess")
    assert h["Authorization"] == "Bearer k" and h["x-opencode-session"] == "sess"
    h2 = pk.headers("openrouter", "k", "sess")
    assert "x-opencode-session" not in h2
    assert pk.extract_content("openai", {"choices": [{"message": {"content": "hi"}}]}) == "hi"
    assert pk.extract_content("openai", {}) == ""
