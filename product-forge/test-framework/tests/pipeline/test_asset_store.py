"""BI-0187: media ingest + segmentation/tiling + asset store (fail-closed)."""
import os
import shutil
import struct
import sys
import tempfile
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import asset_store as asx  # noqa: E402

_PROJECT = "_test_bi_0187"


def _pdir():
    from core.paths import ROOT
    return os.path.join(str(ROOT), "products", _PROJECT)


def _png(path, w=64, h=64):
    try:
        from PIL import Image
        Image.new("RGB", (w, h), (10, 20, 30)).save(path)
        return True
    except Exception:
        return False


def _wav(path, seconds=0.1, rate=8000):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))


def test_add_image_dedup_and_metadata():
    d = _pdir()
    tmp = tempfile.mkdtemp()
    try:
        os.makedirs(d, exist_ok=True)
        p = os.path.join(tmp, "a.png")
        if not _png(p):
            return  # PIL absent in env: image probe degrades; covered by degrade test
        a1 = asx.add(d, path=p, type_="image")
        assert a1["asset_id"].startswith("AS-") and a1["type"] == "image"
        assert a1["sha256"] and a1["bytes"] > 0
        assert a1["metadata"].get("dimensions") == [64, 64]
        # dedupe: same bytes => same asset id
        a2 = asx.add(d, path=p, type_="image")
        assert a2["asset_id"] == a1["asset_id"]
    finally:
        shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(tmp, ignore_errors=True)


def test_wav_segmentation_and_to_media():
    d = _pdir()
    tmp = tempfile.mkdtemp()
    try:
        os.makedirs(d, exist_ok=True)
        p = os.path.join(tmp, "clip.wav")
        _wav(p, seconds=0.3)
        a = asx.add(d, path=p, type_="audio", split=True)
        assert a["type"] == "audio"
        assert a["metadata"].get("sample_rate") == 8000
        assert a["metadata"].get("duration", 0) > 0
        # segment_s default 60s > 0.3s => no segments, but to_media works on original
        media = asx.to_media(d, a)
        assert media and media[0]["type"] == "audio"
        assert "audio" in asx.modalities(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(tmp, ignore_errors=True)


def test_missing_source_returns_error_not_raise():
    d = _pdir()
    try:
        os.makedirs(d, exist_ok=True)
        r = asx.add(d, path=os.path.join(d, "nope.png"))
        assert r.get("error") == "no_source"
    finally:
        shutil.rmtree(d, ignore_errors=True)
