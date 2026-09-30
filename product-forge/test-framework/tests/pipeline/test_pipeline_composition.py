"""BI-0213: capability-gated pipeline composition (identity guard + anchor insert + roster)."""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import pipeline_composition as pc  # noqa: E402
from core.paths import ROOT  # noqa: E402

_BASE = json.load(open(str(Path(ROOT) / "pipeline-definition.json"), encoding="utf-8"))


def test_no_pack_is_byte_identical_identity():
    assert pc.effective_definition(_BASE) is _BASE           # same object, untouched
    assert pc.effective_definition(_BASE, packs=[]) is _BASE
    assert pc.effective_definition(_BASE, packs=[{"key": "none"}]) is _BASE


def test_video_pack_inserts_4m_after_4_0_and_rewires():
    vid = [{"key": "video",
            "stages": [{"id": "4m", "after": "4-0", "ideal_flow": ["media-generator", "media-editor"],
                        "depends_on": ["4-0"], "optional": True}],
            "agents": [], "validators": [], "validator_stages": ["5", "6"]}]
    comp = pc.effective_definition(_BASE, packs=vid)
    ks = list(comp["stages"].keys())
    assert "4m" in ks
    assert ks.index("4m") == ks.index("4-0") + 1             # right after anchor
    assert comp["stages"]["4m"]["depends_on"] == ["4-0"]
    assert comp["stages"]["4a"]["depends_on"] == ["4m"]      # dependent rewired
    # existing required stages intact
    assert comp["stages"]["0a"]["ideal_flow"] == _BASE["stages"]["0a"]["ideal_flow"]
    # base not mutated
    assert "4m" not in _BASE["stages"]


def test_unknown_anchor_is_fail_closed_no_change():
    bad = [{"key": "video", "stages": [{"id": "9z", "after": "does-not-exist",
                                        "ideal_flow": ["x"]}], "agents": [], "validators": []}]
    comp = pc.effective_definition(_BASE, packs=bad)
    assert "9z" not in comp["stages"]
    assert comp.get("_composition", {}).get("warnings")


def test_roster_append_validators_and_agents():
    vid = [{"key": "video", "stages": [], "agents": ["media-generator"],
            "agent_stages": ["4m"], "validators": ["media-qa"], "validator_stages": ["5", "6"]}]
    roster = pc.effective_agents({"4m": [], "5": ["security"], "6": ["validate"]}, vid)
    assert "media-generator" in roster["4m"]
    assert "media-qa" in roster["5"] and "security" in roster["5"]
    assert "media-qa" in roster["6"]


def test_disabling_pack_leaves_no_residue():
    vid = [{"key": "video", "stages": [{"id": "4m", "after": "4-0"}], "agents": [], "validators": []}]
    on = pc.effective_definition(_BASE, packs=vid)
    off = pc.effective_definition(_BASE, packs=[])
    assert "4m" in on["stages"] and "4m" not in off["stages"]
    assert list(off["stages"].keys()) == list(_BASE["stages"].keys())


def test_dag_consumes_composed_definition_cleanly():
    vid = [{"key": "video", "stages": [{"id": "4m", "after": "4-0", "ideal_flow": ["media-generator"],
                                        "depends_on": ["4-0"]}], "agents": [], "validators": []}]
    comp = pc.effective_definition(copy.deepcopy(_BASE), packs=vid)
    from core.dag_executor import DAGExecutor
    dag = DAGExecutor(comp)
    assert "4m" in dag.states
    ready = dag.get_ready_stages()
    assert "0" in ready  # first stage still ready
