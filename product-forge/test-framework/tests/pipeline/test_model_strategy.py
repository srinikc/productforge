"""BI-0192/BI-0210: two-phase model & capability strategy gate (no-op + media e2e)."""
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import model_strategy as ms  # noqa: E402
from core.paths import ROOT  # noqa: E402

_PROJECT = "_test_bi_0192"


def _pdir():
    return os.path.join(str(ROOT), "products", _PROJECT)


def _write_profile(mods):
    d = _pdir()
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "capabilities." + "json"), "w", encoding="utf-8") as f:
        json.dump({"required_capabilities": mods, "enabled_packs": mods}, f)


def _clean():
    shutil.rmtree(_pdir(), ignore_errors=True)


def test_plain_text_is_noop_and_writes_nothing():
    _clean()
    res = ms.gate_a(_pdir())
    assert res.get("noop") is True
    assert not os.path.exists(ms.report_path(_pdir()))     # nothing written
    assert ms.gate_b(_pdir()).get("noop") is True
    _clean()


def test_media_idea_gate_a_enables_packs_and_generator():
    _clean()
    _write_profile(["image", "video"])
    res = ms.gate_a(_pdir())
    assert not res.get("noop")
    ga = res["gate_a"]
    assert "image" in ga["enabled_packs"] and "video" in ga["enabled_packs"]
    kinds = {a["modality"]: a for a in ga["assignments"]}
    assert kinds["video"]["kind"] == "generator"
    assert kinds["video"]["generator"]                       # a real generator id chosen
    _clean()


def test_gate_a_recomposition_injects_4m_into_dag():
    _clean()
    _write_profile(["video"])
    ms.gate_a(_pdir())
    # recomposition uses the project profile -> video pack with 4m stage
    from core import pipeline_composition as pc
    base = json.load(open(str(Path(ROOT) / "pipeline-definition.json"), encoding="utf-8"))
    comp = pc.effective_definition(base, _pdir())
    assert "4m" in comp["stages"]
    _clean()


def test_gate_b_refines_and_apply_is_opt_in():
    _clean()
    _write_profile(["image"])
    ms.gate_a(_pdir())
    res = ms.gate_b(_pdir())
    assert not res.get("noop")
    assert "gate_b" in res
    # default mode is 'warn' => no overrides written
    ms.apply(_pdir())
    data = ms.load_report(_pdir())
    assert (data.get("applied") or {}).get("mode") == "warn"
    assert not (data.get("applied") or {}).get("overrides")
    _clean()


def test_idempotent_reruns():
    _clean()
    _write_profile(["image"])
    a1 = ms.gate_a(_pdir())
    a2 = ms.gate_a(_pdir())
    assert a1["gate_a"]["enabled_packs"] == a2["gate_a"]["enabled_packs"]
    _clean()
