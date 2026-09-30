"""BI-0190: media agents load, have live knowledge bindings, and are pack-gated in composition."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import pipeline_composition as pc  # noqa: E402
from core.agent_spec import load_specs  # noqa: E402
from core.paths import ROOT  # noqa: E402

_MEDIA = ("media-analyst", "media-generator", "media-editor", "asset-librarian")


def test_media_specs_load():
    specs = load_specs(str(Path(ROOT) / "agents"))
    for a in _MEDIA:
        assert a in specs, f"missing spec for {a}"
        assert specs[a].id == a


def test_media_cards_present_and_consistent():
    for a in _MEDIA:
        assert (Path(ROOT) / ".opencode" / "agent" / f"{a}.md").exists()


def test_media_knowledge_bindings_resolve_to_live_guidelines():
    caps = json.loads((Path(ROOT) / "config" / "agent-capabilities.json").read_text(encoding="utf-8"))
    gdir = Path(ROOT) / "docs" / "guidelines"
    for a in _MEDIA:
        entry = (caps.get("agents") or {}).get(a)
        assert entry, f"{a} missing capability binding"
        layers = entry.get("knowledge") or []
        assert layers, f"{a} has no knowledge layers"
        # at least one declared layer maps to a live guideline dir
        live = [l for l in layers if (gdir / l).is_dir() and any((gdir / l).glob("*.md"))]
        assert live, f"{a} knowledge layers do not resolve to live guidelines: {layers}"


def test_pack_composition_appends_media_agents_only_when_enabled():
    base = json.loads((Path(ROOT) / "pipeline-definition.json").read_text(encoding="utf-8"))
    # no pack -> identity (no media agents injected)
    assert pc.effective_definition(base) is base
    # video pack -> 4m stage + media agents on the roster
    vid = [{"key": "video", "stages": [{"id": "4m", "after": "4-0",
                                        "ideal_flow": ["media-generator", "media-editor"],
                                        "depends_on": ["4-0"]}],
            "agents": ["media-generator", "media-editor"], "agent_stages": ["4m"],
            "validators": [], "validator_stages": []}]
    comp = pc.effective_definition(base, packs=vid)
    assert "4m" in comp["stages"]
    assert "media-generator" in comp["stages"]["4m"]["ideal_flow"]


def test_catalog_packs_reference_media_agents():
    packs = json.loads((Path(ROOT) / "config" / "capability-packs.json").read_text(encoding="utf-8"))
    for key in ("image", "video", "audio"):
        agents = (packs["packs"].get(key) or {}).get("agents") or []
        assert any(a in agents for a in _MEDIA), f"pack {key} does not reference media agents"
