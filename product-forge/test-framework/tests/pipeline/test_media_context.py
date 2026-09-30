"""BI-PF-0287: media context — native parts vs summary, token accounting, e2e threading."""
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import pytest  # noqa: E402
from core import media_context as mc  # noqa: E402
from core.paths import ROOT  # noqa: E402

_PROJECT = "_test_media_ctx"


def _pdir():
    return os.path.join(str(ROOT), "products", _PROJECT)


def _clean():
    shutil.rmtree(_pdir(), ignore_errors=True)


def _add_image_asset():
    """Create a real PNG asset via asset_store (PIL if available)."""
    d = _pdir()
    os.makedirs(d, exist_ok=True)
    try:
        from PIL import Image
    except Exception:
        pytest.skip("PIL not available")
    src = os.path.join(d, "src.png")
    Image.new("RGB", (32, 32), (1, 2, 3)).save(src)
    from core import asset_store as asx
    a = asx.add(d, path=src, type_="image")
    os.remove(src)
    return a


def test_no_assets_is_noop():
    _clean()
    assert mc.for_agent(_pdir(), "media-analyst", "x") == ([], "", 0)
    _clean()


def test_summary_mode_for_text_model():
    _clean()
    _add_image_asset()
    parts, summary, toks = mc.for_agent(_pdir(), "media-analyst", "deepseek-v4.1-flash")
    assert parts == []                       # text-only model: no native parts
    assert "MEDIA ASSETS" in summary and "AS-" in summary
    assert toks == 0
    _clean()


def test_native_mode_for_vision_model():
    _clean()
    _add_image_asset()
    os.environ["PIPELINE_MEDIA_CONTEXT"] = "native"
    try:
        parts, summary, toks = mc.for_agent(_pdir(), "media-analyst",
                                            "google/gemini-3.1-flash-image")
        assert parts, "vision model should receive native image parts"
        assert parts[0]["type"] == "image"
        assert toks > 0
    finally:
        os.environ.pop("PIPELINE_MEDIA_CONTEXT", None)
        _clean()


def test_estimate_tokens_positive_for_parts():
    assert mc.estimate_tokens([{"bytes": 100000}]) > 0
    assert mc.estimate_tokens([]) == 0


def test_referenced_asset_only_for_non_media_agent():
    _clean()
    a = _add_image_asset()
    # a non-media agent with no refs gets nothing; with the ref in upstream text it gets the asset
    assert mc.select_assets(_pdir(), "implement", "no refs here") == []
    got = mc.select_assets(_pdir(), "implement", f"see {a['asset_id']} for the design")
    assert [x["asset_id"] for x in got] == [a["asset_id"]]
    _clean()


def test_agent_runner_forwards_media_e2e():
    """The agent_runner wrapper must forward `media=` to llm_client (the missing link)."""
    from core.orchestrator.agent_runner import AgentRunnerMixin

    class _FakeLLM:
        def __init__(self):
            self.seen = None

        def _call_llm(self, prompt, agent_id, stage_id, pin_model="", media=None):
            self.seen = media
            return "ok", {}

    r = AgentRunnerMixin.__new__(AgentRunnerMixin)
    r.llm = _FakeLLM()
    parts = [{"type": "image", "path": "x.png"}]
    r._call_llm("p", "media-analyst", "4m", media=parts)
    assert r.llm.seen == parts

