"""BI-0224: deterministic renderer for structured (JSON-first) agent output."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import render as R  # noqa: E402


def test_extract_json_fenced_and_bare():
    assert R.extract_json('```json\n{"heading": "X"}\n```') == {"heading": "X"}
    assert R.extract_json('{"a": 1}') == {"a": 1}
    assert R.extract_json("not json at all") is None


def test_render_section_heading_bullets_text():
    md = R.render_section({"heading": "Scope", "text": "In scope.", "bullets": ["a", "b"]})
    assert md.startswith("## Scope")
    assert "In scope." in md and "- a" in md and "- b" in md


def test_render_payload_deterministic():
    p = {"title": "Spec", "sections": [{"heading": "One", "bullets": ["x"]},
                                       {"heading": "Two", "text": "t"}]}
    a = R.render_payload(p)
    b = R.render_payload(p)
    assert a == b and "# Spec" in a and "## One" in a and "## Two" in a
