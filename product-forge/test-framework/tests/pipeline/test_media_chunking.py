"""BI-PF-0288: media chunking + markdown asset-ref resolution."""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import pytest  # noqa: E402
from core import media_context as mc  # noqa: E402
from core.paths import ROOT  # noqa: E402

_PROJECT = "_test_media_chunk"


def _pdir():
    return os.path.join(str(ROOT), "products", _PROJECT)


def _clean():
    shutil.rmtree(_pdir(), ignore_errors=True)


def _image_asset():
    d = _pdir()
    os.makedirs(d, exist_ok=True)
    try:
        from PIL import Image
    except Exception:
        pytest.skip("PIL not available")
    src = os.path.join(d, "s.png")
    Image.new("RGB", (24, 24), (5, 5, 5)).save(src)
    from core import asset_store as asx
    a = asx.add(d, path=src, type_="image")
    os.remove(src)
    return a


def test_markdown_link_resolves_to_asset_id():
    a = _image_asset()
    try:
        text = f"see ![diagram](assets/{a['asset_id']}/original.png) here"
        refs = mc._referenced_assets(text)
        assert a["asset_id"] in refs
    finally:
        _clean()


def test_bare_as_token_still_resolves():
    a = _image_asset()
    try:
        assert a["asset_id"] in mc._referenced_assets(f"ref {a['asset_id']}")
    finally:
        _clean()


def test_chunk_media_bounds_to_budget():
    parts = [{"bytes": 100000}, {"bytes": 100000}, {"bytes": 100000}]
    # each part estimates ~250 tokens (floor); a 300-token budget fits exactly one
    out = mc.chunk_media("_", parts, budget_tokens=300)
    assert 1 <= len(out) < len(parts)
    # tiny budget that no single part fits -> [] (summary fallback)
    assert mc.chunk_media("_", [{"bytes": 10_000_000}], budget_tokens=1) == []


def test_over_budget_falls_back_to_summary_via_for_agent():
    a = _image_asset()
    try:
        os.environ["PIPELINE_MEDIA_CONTEXT"] = "native"
        os.environ["PIPELINE_MEDIA_BUDGET_TOKENS"] = "1"   # nothing fits
        try:
            parts, summary, toks = mc.for_agent(_pdir(), "media-analyst",
                                                "google/gemini-3.1-flash-image")
            assert parts == []           # over budget -> summary only, never overflow
            assert "MEDIA ASSETS" in summary
        finally:
            os.environ.pop("PIPELINE_MEDIA_CONTEXT", None)
            os.environ.pop("PIPELINE_MEDIA_BUDGET_TOKENS", None)
    finally:
        _clean()


def test_non_media_agent_gets_referenced_asset_only():
    a = _image_asset()
    try:
        assert mc.select_assets(_pdir(), "implement", "nothing") == []
        got = mc.select_assets(_pdir(), "implement", f"![x](assets/{a['asset_id']}/original.png)")
        assert [g["asset_id"] for g in got] == [a["asset_id"]]
    finally:
        _clean()
