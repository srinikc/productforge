"""BI-0186: multimodal LLM plumbing — media parts gated by model input_modalities (fail-closed)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import multimodal as mm  # noqa: E402


def _vision():
    # a catalog model that accepts image input
    return "google/gemini-3.1-flash-image"


def _textonly():
    return "deepseek-v4.1-flash"


def test_media_attached_for_vision_model():
    content, dropped = mm.build(_vision(), "describe", [{"type": "image", "url": "http://x/a.png"}])
    assert isinstance(content, list)
    assert content[0]["type"] == "text"
    assert any(p["type"] == "image_url" for p in content)
    assert dropped == []


def test_media_dropped_for_text_only_model():
    content, dropped = mm.build(_textonly(), "describe", [{"type": "image", "url": "http://x/a.png"}])
    # fail-closed: text-only model => content stays a plain string, media dropped
    assert isinstance(content, str)
    assert len(dropped) == 1 and dropped[0]["modality"] == "image"


def test_no_media_is_unchanged_string():
    content, dropped = mm.build(_vision(), "just text", None)
    assert content == "just text"
    assert dropped == []


def test_oversized_and_unreadable_are_dropped():
    parts, dropped = mm.parts_for(_vision(), [
        {"type": "image", "path": "no/such/file.png"},
        {"type": "image", "path": "does-not-matter.png", "data": ""},
    ])
    # both fail to load -> dropped (fail-closed), never raised
    assert parts == []
    assert len(dropped) == 2


def test_audio_part_shape():
    p = mm.part_payload({"part_type": "input_audio", "value": "data:audio/wav;base64,AAAA"})
    assert p["type"] == "input_audio" and p["input_audio"]["data"] == "AAAA"
    assert p["input_audio"]["format"] == "wav"
