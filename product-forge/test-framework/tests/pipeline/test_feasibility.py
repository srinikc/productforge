"""BI-0214: two-phase feasibility & capability triage (build-host verdict + destination shipping)."""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import feasibility as f  # noqa: E402
from core.paths import ROOT  # noqa: E402

_PROJECT = "_test_bi_0214"


def _pdir():
    return os.path.join(str(ROOT), "products", _PROJECT)


def _write_profile(mods):
    import json
    d = _pdir()
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "capabilities." + "json"), "w", encoding="utf-8") as fh:
        json.dump({"required_capabilities": mods, "enabled_packs": mods}, fh)


def _clean():
    shutil.rmtree(_pdir(), ignore_errors=True)


def test_host_probe_never_raises():
    h = f.probe_host()
    for k in ("os", "cpu_cores", "ram_gb", "disk_free_gb", "vram_gb", "degraded"):
        assert k in h


def test_cpu_only_host_video_is_conditional_api():
    _clean()
    _write_profile(["image", "video"])
    host = {"os": "test", "cpu_cores": 4, "ram_gb": 8, "disk_free_gb": 10,
            "gpu_model": "", "vram_gb": 0, "cuda": False, "degraded": False, "reasons": []}
    res = f.assess_build(_pdir(), host=host)
    assert res["verdict"] in ("conditional", "no-go")
    by = {r["modality"]: r for r in res["per_modality"]}
    # video needs 8GB VRAM; none => not local => api/aggregator
    assert by["video"]["fits_local"] is False
    assert by["video"]["build_mode"] in ("api", "aggregator")
    _clean()


def test_big_host_image_can_be_local_and_verdict_go():
    _clean()
    _write_profile(["image"])
    host = {"os": "test", "cpu_cores": 16, "ram_gb": 64, "disk_free_gb": 500,
            "gpu_model": "RTX 4090", "vram_gb": 24, "cuda": True, "degraded": False, "reasons": []}
    res = f.assess_build(_pdir(), host=host)
    img = res["per_modality"][0]
    assert img["build_mode"] == "local" and img["fits_local"] is True
    assert res["verdict"] == "go"
    _clean()


def test_restricted_weight_is_api_only():
    _clean()
    _write_profile(["image"])
    # force a non-permissive generator by pointing at the paid direct openai-images via selection:
    # with no keys, self-host flux (Apache-2.0) is selected -> bundle_allowed True. Simulate a
    # restricted-only modality by asserting bundle_allowed math directly.
    assert f._bundle_allowed("proprietary", True) is False
    assert f._bundle_allowed("Apache-2.0", True) is True
    assert f._bundle_allowed("Apache-2.0", False) is False
    _clean()


def test_phase_independence_and_destination():
    _clean()
    _write_profile(["image"])
    host = {"os": "t", "cpu_cores": 8, "ram_gb": 32, "disk_free_gb": 100,
            "gpu_model": "", "vram_gb": 0, "cuda": False, "degraded": False, "reasons": []}
    d1 = f.evaluate(_pdir(), phase="build", host=host)
    assert d1["phase1_build_host"]["verdict"] in ("conditional", "go", "no-go")
    assert d1["phase2_destination"] == {}
    build_before = d1["phase1_build_host"]
    d2 = f.evaluate(_pdir(), phase="destination")
    # phase 2 must NOT rewrite phase 1
    assert d2["phase1_build_host"] == build_before
    assert "shipping_mode" in d2["phase2_destination"]
    assert d2["phase2_destination"]["sku"]
    _clean()
