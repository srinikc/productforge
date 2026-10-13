"""Artifact Contract Registry: coverage, resolution, validation, refresh metadata."""
import glob
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from core import contracts  # noqa: E402


def test_registry_has_contracts():
    reg = contracts.load_registry()
    assert len(reg) >= 10
    for aid, c in reg.items():
        assert c.get("sections"), f"{aid} has no sections"
        assert (c.get("source") or {}).get("canonical_url"), f"{aid} has no source url"
        assert (c.get("license") or {}).get("spdx"), f"{aid} has no license"
        assert c.get("format_version"), f"{aid} has no format_version"


def test_every_agent_and_stage_is_covered():
    agents = []
    for f in glob.glob(str(ROOT / "agents" / "*.agent.json")):
        try:
            agents.append(json.load(open(f, encoding="utf-8-sig"))["id"])
        except Exception:
            pass
    assert agents, "no agents found"
    with open(ROOT / "pipeline-definition.json", encoding="utf-8-sig") as f:
        stages = list((json.load(f).get("stages") or {}).keys())
    cov = contracts.coverage(agents, stages)
    assert cov.get("ok") is True, f"coverage failed: {cov}"


def test_resolve_design_stage():
    r = contracts.resolve(agent="design", stage="1", kind="text")
    ids = {c["artifact_id"] for c in r["contracts"]}
    assert "requirements.srs" in ids
    assert "design.ux" in ids
    assert r["covered"] is True


def test_resolve_modality_by_kind():
    r = contracts.resolve(agent="media-generator", kind="video")
    ids = {c["artifact_id"] for c in r["contracts"]}
    assert "media.video" in ids
    assert "media.3d" not in ids


def test_resolve_unknown_agent_not_covered():
    r = contracts.resolve(agent="brand-new-agent-xyz")
    assert r["covered"] is False


def test_validate_artifact_detects_gaps():
    # a design.ux text missing most required sections + tiny -> must fail
    bad = contracts.validate_artifact("design.ux", "# Design\n\nshort")
    assert bad["ok"] is False
    assert bad["missing_sections"]
    # a text containing all sections -> passes section check
    c = contracts.contract("design.ux")
    good = "\n".join(f"## {s}\ncontent" for s in c["sections"])
    assert contracts.validate_artifact("design.ux", good)["ok"] is True


def test_validate_unknown_contract_fails_closed():
    assert contracts.validate_artifact("does.not.exist", "x")["ok"] is False
