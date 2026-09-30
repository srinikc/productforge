"""BI-0199: OTel GenAI spans (incl. multimodal) — mapping + emit; no content/bytes leak."""
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import otel  # noqa: E402
from core.paths import ROOT  # noqa: E402

_PROJECT = "_test_otel_genai"


def _pdir():
    return os.path.join(str(ROOT), "products", _PROJECT)


def _clean():
    shutil.rmtree(_pdir(), ignore_errors=True)


def test_gen_ai_attributes_mapping():
    ev = {"type": "gen_ai_call", "provider": "openai", "model": "gpt-x",
          "input_tokens": 12, "output_tokens": 7, "media_requested": 3, "media_attached": 2,
          "input_modalities": ["image", "audio"], "billing_unit": "image", "kind": "chat"}
    a = otel.gen_ai_attributes(ev)
    assert a["gen_ai.system"] == "openai"
    assert a["gen_ai.request.model"] == "gpt-x"
    assert a["gen_ai.usage.input_tokens"] == 12
    assert a["gen_ai.request.media.attached"] == 2
    assert a["gen_ai.input.modalities"] == ["image", "audio"]


def test_to_span_includes_gen_ai_for_call_events():
    sp = otel.to_span({"type": "gen_ai_call", "provider": "p", "output_modalities": ["image"],
                       "billing_unit": "image"})
    assert sp["name"] == "gen_ai_call"
    assert sp["attributes"]["gen_ai.output.modalities"] == ["image"]
    assert sp["attributes"]["gen_ai.usage.billing_unit"] == "image"


def test_llm_emit_produces_span_without_content():
    _clean()
    d = _pdir()
    os.makedirs(d, exist_ok=True)
    try:
        from core import events as ev
        ev.emit(d, "gen_ai_call", agent="design", stage="1", provider="opencode-go",
                model="mimo-v2.5", operation="chat", input_tokens=100, output_tokens=50,
                media_requested=1, media_attached=1, input_modalities=["image"])
        spans = otel.spans(d)
        call = [s for s in spans if s["name"] == "gen_ai_call"]
        assert call, "no gen_ai_call span emitted"
        attrs = call[0]["attributes"]
        assert attrs["gen_ai.system"] == "opencode-go"
        assert attrs["gen_ai.usage.input_tokens"] == 100
        # no content/bytes leaked anywhere in the span
        blob = json.dumps(call[0]).lower()
        assert "prompt" not in blob and "data:" not in blob and "base64" not in blob
    finally:
        _clean()


def test_generator_emit_media_span():
    _clean()
    d = _pdir()
    os.makedirs(d, exist_ok=True)
    try:
        from core import generator_adapters as ga
        ga.generate("video-gen", {"prompt": "x"}, d)   # emits gen_ai_call (media kind)
        spans = otel.spans(d)
        media = [s for s in spans if s["attributes"].get("gen_ai.output.modalities")]
        assert media, "no media gen_ai span"
        assert media[0]["attributes"]["gen_ai.output.modalities"] == ["video"]
    finally:
        _clean()


def test_export_disabled_is_noop():
    _clean()
    os.environ.pop("PIPELINE_OTEL", None)
    assert otel.export(_pdir()) == ""
    _clean()
