"""BI-0201: framework-agnostic agent cards (no default .opencode dependency)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import agent_spec as A  # noqa: E402


def test_resolver_prefers_canonical_agents_dir():
    ids = A.list_agent_ids()
    assert len(ids) >= 60
    p = A.resolve_card_path(ids[0])
    assert p and p.endswith(".agent.json")
    assert A.source_kind(p) == "spec"


def test_no_default_opencode_read():
    # default resolution must never return a .opencode path
    for aid in A.list_agent_ids():
        p = A.resolve_card_path(aid)
        assert p is None or ".opencode" not in p.replace("\\", "/")
    assert A.allow_legacy() is False


def test_card_for_reports_provenance():
    c = A.card_for("design")
    assert c["found"] is True and c["source"] == "spec"
    assert isinstance(c["card"], dict)


def test_neutral_cards_dir_is_honored(tmp_path, monkeypatch):
    neutral = Path(A.cards_dir())
    made = False
    try:
        neutral.mkdir(parents=True, exist_ok=True)
        card = neutral / "_probe_agent.md"
        if not card.exists():
            card.write_text("---\nagent_id: _probe_agent\n---\n\n## 0. METADATA\n- x\n", encoding="utf-8")
            made = True
        p = A.resolve_card_path("_probe_agent")
        assert p and A.source_kind(p) == "cards"
    finally:
        if made:
            try:
                (neutral / "_probe_agent.md").unlink()
            except Exception:
                pass


def test_legacy_only_with_flag(monkeypatch):
    monkeypatch.setenv("ALLOW_OPENCODE_LEGACY", "1")
    assert A.allow_legacy() is True
    # resolver may now reach legacy, but neutral still wins for real agents
    p = A.resolve_card_path("design")
    assert A.source_kind(p) == "spec"


def test_renderers_load_without_opencode():
    from core import agent_card_loader, agent_rules, schema_validator
    # agent_card_loader defaults to neutral agents dir (may be empty of .md; must not error)
    agent_card_loader.AgentCardLoader().load_all()
    # agent_rules lists + parses from neutral specs (JSON rendered to card md)
    ids = agent_rules.list_all_agents()
    assert len(ids) >= 60
    parsed = agent_rules.parse_agent_md("design")
    assert parsed is not None
    # schema_validator validates an agent from the neutral spec
    res = schema_validator.validate_agent_md("design")
    assert res is not None
