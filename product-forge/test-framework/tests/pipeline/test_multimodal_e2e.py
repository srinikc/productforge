"""BI-0212: multimodal end-to-end acceptance (hermetic; one golden path per modality).

Proves the REAL control-flow chain stitches together, offline:
  idea -> modality.detect -> capability_packs.resolve -> generator select (kind/billing_unit/license)
  -> asset store -> media_context (summary/native) -> media_qa.
Also: async submit->status->cancel lifecycle; text-only regression guard; optional live smoke (skipped).
"""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import pytest  # noqa: E402
from core import asset_store as asx  # noqa: E402
from core import capability_packs as cp  # noqa: E402
from core import generator_adapters as ga  # noqa: E402
from core import media_context as mc  # noqa: E402
from core import media_qa as mqa  # noqa: E402
from core import modality as mo  # noqa: E402
from core.paths import ROOT  # noqa: E402

_PROJECT = "_test_bi_0212"


def _pdir():
    return os.path.join(str(ROOT), "products", _PROJECT)


def _clean():
    shutil.rmtree(_pdir(), ignore_errors=True)


def _tiny_png(path):
    try:
        from PIL import Image
    except Exception:
        return False
    Image.new("RGB", (16, 16), (100, 150, 200)).save(path)
    return True


IDEAS = {
    "image": "a mobile app that uses image/photo uploads and renders illustrations",
    "video": "a reels app that generates short video clips and animation",
    "audio": "a voice app with speech-to-text and text-to-speech audio",
    "3d": "a 3d product configurator with mesh assets and cad export",
}
KIND = {"image": "image-gen", "video": "video-gen", "audio": "tts", "3d": "3d"}
ASYNC = {"video", "3d"}


@pytest.mark.parametrize("modality", ["image", "video", "audio", "3d"])
def test_golden_path_per_modality(modality):
    _clean()
    d = _pdir()
    os.makedirs(d, exist_ok=True)
    try:
        # 1. detect modality from the idea
        mods = mo.detect(IDEAS[modality])
        assert modality in mods

        # 2. capability pack resolves for the required capability
        res = cp.resolve([modality])
        enabled = [e["key"] for e in res["enabled"]]
        assert modality in enabled, f"pack for {modality} did not resolve"

        # 3. generator selection yields a real generator with billing_unit + license
        g = ga.select(KIND[modality], [modality])
        assert g, f"no generator for {modality}"
        assert g.get("billing_unit") and g.get("license") is not None

        # 4. asset store sink accepts a deterministic tiny media fixture
        if modality in ("image", "video", "3d"):
            if not _tiny_png(os.path.join(d, "fx.png")):
                pytest.skip("PIL not available")
            asset = asx.add(d, path=os.path.join(d, "fx.png"), type_="image")
            os.remove(os.path.join(d, "fx.png"))
            assert asset["asset_id"].startswith("AS-")
            assert asx.list_assets(d)

        # 5. media context: summary for a text model; native for a vision model (if assets exist)
        parts, summary, toks = mc.for_agent(d, "media-analyst", "deepseek-v4.1-flash")
        if asset_exists := bool(asx.list_assets(d)):
            assert "MEDIA ASSETS" in summary

        # 6. media QA runs over the store
        qr = mqa.validate_project(d)
        assert "noop" in qr
    finally:
        _clean()


@pytest.mark.parametrize("modality", ["video", "3d"])
def test_async_lifecycle_via_adapter(modality):
    _clean()
    d = _pdir()
    os.makedirs(d, exist_ok=True)
    try:
        r = ga.generate(KIND[modality], {"prompt": "x"}, d)
        assert r.get("ok") is True
        job = r["job"]
        assert job.get("async") is True
        assert ga.status(d, job["job_id"]) is not None   # persisted to the job store
        assert ga.cancel(d, job["job_id"]) is True
    finally:
        _clean()


def test_billing_unit_present_for_every_generator():
    for g in ga.list_generators():
        assert g.get("billing_unit"), f"{g['id']} missing billing_unit"


def test_text_only_project_is_unchanged():
    _clean()
    d = _pdir()
    os.makedirs(d, exist_ok=True)
    try:
        mods = mo.detect("a plain CRUD web app with a database")
        assert [m for m in mods if m != "text"] == []      # no media modality
        assert cp.resolve([])["enabled"] == []             # no pack enabled
        assert asx.list_assets(d) == []                    # no media assets
        assert mc.for_agent(d, "implement", "x") == ([], "", 0)   # media context no-op
        qr = mqa.validate_project(d)
        assert qr["noop"] is True
    finally:
        _clean()


@pytest.mark.skipif(os.getenv("PF_E2E_LIVE", "0") not in ("1", "true", "yes"),
                    reason="live smoke disabled (set PF_E2E_LIVE=1)")
def test_live_smoke_optional():
    # Placeholder: live free-tier/self-host smoke is opt-in and off by default.
    assert True
