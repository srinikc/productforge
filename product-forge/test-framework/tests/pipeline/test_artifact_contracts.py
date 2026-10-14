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


def test_kind_detection():
    assert contracts.detect_kind("edit video clips and export a timeline")["kind"] == "video"
    assert contracts.detect_kind("a simple todo list")["kind"] == "text"


def test_register_agent():
    assert contracts.agent_registered("design") is True
    assert contracts.agent_registered("ghost-agent-xyz") is False
    # invalid outputs -> validation fails and nothing is written
    r = contracts.register_agent("_test_agent_xyz", outputs=["ghost.artifact.xyz"])
    assert r["ok"] is False
    assert contracts.agent_registered("_test_agent_xyz") is False


def test_agent_registry():
    reg = contracts.agent_registry()
    assert len(reg) >= 60, f"expected >=60 agents, got {len(reg)}"
    sp = contracts.agent_spec("design")
    assert sp.get("outputs"), f"design spec must declare outputs: {sp}"
    cov = contracts.agent_coverage(["design", "ghost-agent-xyz"])
    assert cov["ok"] is False
    assert "ghost-agent-xyz" in cov["missing_agents"]


def test_validate_agent():
    ids = [c["artifact_id"] for c in contracts.resolve(agent="design", stage="1", kind="text")["contracts"]]
    assert ids, "design/1 should resolve contracts"
    secs = []
    for aid in ids:
        secs += contracts.contract(aid).get("required_sections") or []
    good = "\n".join(f"## {s}" for s in secs)
    r = contracts.validate_agent(agent="design", stage="1", kind="text", text=good)
    assert r["ok"] is True, r["failures"]
    assert set(r["checked"]) == set(ids)
    bad = contracts.validate_agent(agent="design", stage="1", kind="text", text="nothing here")
    assert bad["ok"] is False
    assert bad["failures"]


def test_format_and_limits_validation():
    # api.openapi: format=json -> invalid JSON fails; valid JSON with keys passes
    assert contracts.validate_artifact("api.openapi", "not json")["ok"] is False
    good = '{"openapi":"3.1.0","info":{"title":"x"},"paths":{}}'
    assert contracts.validate_artifact("api.openapi", good)["ok"] is True
    # requirements.srs: FR count limit enforced (regex count > max)
    req = contracts.contract("requirements.srs")
    body = "\n".join(f"## {s}" for s in req["required_sections"]) + "\n" + \
        "\n".join(f"FR-{i}" for i in range(1, 100))
    r = contracts.validate_artifact("requirements.srs", body)
    assert r["ok"] is False
    assert any("limit" in x for x in r["reasons"]), r["reasons"]


def test_budget_and_slider():
    b = contracts.budget(agent="design", stage="1", kind="text")
    assert b["total_max_tokens"] > 0, b
    r = contracts.resolve(agent="design", stage="1", kind="text", profile="small")
    assert r["size_multiplier"] == 0.5, r
    assert r["profile"] == "small"
    # contract items carry the given required sections + budget
    c0 = r["contracts"][0]
    assert c0.get("required_sections"), c0
    assert c0.get("budget"), c0


def test_product_wide_nfr_not_per_feature():
    # BI-PF-1373: NFR is product-wide (stated ONCE); the per-feature prompt must NOT ask for NFR ids.
    from core import agent_requirements as ar
    rng = ar.format_feature_range("F-1", ar.id_allocation(["F-1: a", "F-2: b"])["F-1"])
    assert "FR-" in rng and "US-" in rng, rng
    assert "NFR-" not in rng, rng
    assert "NFR" in ar.product_wide_prefixes(), ar.product_wide_prefixes()
    assert "NFR-1" in ar.product_wide_id_range(), ar.product_wide_id_range()


def test_dry_check_flags_restatement():
    clean = contracts.dry_check(product_wide=["non_functional_requirements"],
                                fragments=[{"id": "F-1", "text": "## F-1\nNFRs referenced (NFR-1..15)"}])
    assert clean["ok"] is True, clean
    bad = contracts.dry_check(product_wide=["non_functional_requirements"],
                              fragments=[{"id": "F-2",
                                          "text": "## F-2\n## Non-Functional Requirements\nNFR-1 latency"}])
    assert bad["ok"] is False, bad
    assert bad["violations"][0]["id"] == "F-2", bad


def test_outline_gate():
    # deterministic outline = the resolved contracts' required sections (union), as the wiring does
    res = contracts.resolve(agent="design", stage="1", kind="text")
    secs = []
    for ct in (res.get("contracts") or []):
        for s in (ct.get("required_sections") or []):
            if s not in secs:
                secs.append(s)
    outline = [{"section": s, "count": 1} for s in secs]
    r = contracts.outline_check(agent="design", stage="1", kind="text", outline=outline)
    assert r["verdict"] in ("under", "over", "no_budget"), r
    assert r["budget_lines"] > 0, r
    assert r["missing_sections"] == [], r          # all required sections supplied
    # a bare outline is missing required sections
    m = contracts.outline_check(agent="design", stage="1", kind="text",
                                outline=[{"section": "Not A Required Section", "count": 1}])
    assert m["missing_sections"], m


def test_budget_reconcile_is_advisory():
    # over the run budget -> verdict over + negative delta (never gates the run)
    over = contracts.reconcile(agent="design", stage="1", kind="text",
                               run_budget_seconds=60, work_estimate_seconds=600)
    assert over["verdict"] == "over", over
    assert over["delta_seconds"] < 0, over
    assert over["artifact_budget"]["max_tokens"] > 0, over
    # well under -> verdict under + positive delta
    under = contracts.reconcile(agent="design", stage="1", kind="text",
                                run_budget_seconds=600, work_estimate_seconds=120)
    assert under["verdict"] == "under", under
    assert under["delta_seconds"] > 0, under
    # 0 budget -> unlimited
    unl = contracts.reconcile(kind="text", run_budget_seconds=0, work_estimate_seconds=9999)
    assert unl["verdict"] == "unlimited", unl
    # run-level (no agent/stage) sums the full artifact set
    run = contracts.reconcile(kind="text", run_budget_seconds=600, work_estimate_seconds=120)
    assert run["artifact_budget"]["count"] >= 10, run
    assert run["run_budget_source"] == "explicit", run
