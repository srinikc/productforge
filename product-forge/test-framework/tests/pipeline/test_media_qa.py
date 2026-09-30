"""BI-0191: media QA validators (probe/perceptual/degrade; no-op without media; findings shape)."""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import pytest  # noqa: E402
from core import media_qa as q  # noqa: E402
from core.paths import ROOT  # noqa: E402

_PROJECT = "_test_media_qa"


def _pdir():
    return os.path.join(str(ROOT), "products", _PROJECT)


def _clean():
    shutil.rmtree(_pdir(), ignore_errors=True)


def test_no_media_is_noop():
    _clean()
    r = q.validate_project(_pdir())
    assert r["noop"] is True and r["ok"] is True
    _clean()


def test_zero_byte_asset_fails_probe():
    checks = q.probe({"asset_id": "AS-x", "type": "image", "bytes": 0, "metadata": {}})
    size = [c for c in checks if c["name"] == "size"][0]
    assert size["ok"] is False


def test_good_image_passes_and_findings_empty():
    d = _pdir()
    os.makedirs(d, exist_ok=True)
    try:
        from PIL import Image
    except Exception:
        pytest.skip("PIL not available")
    src = os.path.join(d, "g.png")
    Image.new("RGB", (32, 32), (200, 100, 50)).save(src)
    from core import asset_store as asx
    asx.add(d, path=src, type_="image")
    os.remove(src)
    r = q.validate_project(d)
    assert r["noop"] is False
    # good single image: no hard findings
    assert all(c["ok"] is not False for a in r["assets"] for c in a["checks"])
    _clean()


def test_missing_tool_degrades_not_pass_or_raise():
    # loudness with no file + ffmpeg maybe absent -> never raises; degraded-safe
    res = q.loudness(os.path.join(_pdir(), "nope.wav"))
    assert isinstance(res, list) and res
    assert res[0]["name"] == "loudness"


def test_perceptual_flags_blank_frame():
    d = _pdir()
    os.makedirs(os.path.join(d, "assets", "AS-t-1", "frames"), exist_ok=True)
    try:
        from PIL import Image
    except Exception:
        pytest.skip("PIL not available")
    # two identical blank frames => duplicate/blank flagged
    for i in range(2):
        Image.new("RGB", (16, 16), (128, 128, 128)).save(
            os.path.join(d, "assets", "AS-t-1", "frames", f"f{i}.png"))
    asset = {"asset_id": "AS-t-1", "type": "video", "children": [
        {"kind": "frame", "path": "assets/AS-t-1/frames/f0.png"},
        {"kind": "frame", "path": "assets/AS-t-1/frames/f1.png"}]}
    checks = q.perceptual_continuity(asset, d)
    perc = [c for c in checks if c["name"] == "perceptual"][0]
    assert perc["ok"] is False and "blank" in perc["detail"] or "duplicate" in perc["detail"]
    _clean()
