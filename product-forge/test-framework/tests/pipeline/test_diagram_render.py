"""Tests for core.diagram_render (offline: the HTTP seam is monkeypatched)."""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from core import diagram_render as dr


def _artifact(tmp_path, body):
    p = tmp_path / "design.md"
    p.write_text(body, encoding="utf-8")
    return str(p)


def test_extract_mermaid():
    text = "intro\n```mermaid\ngraph TD\nA-->B\n```\noutro"
    assert dr.extract_mermaid(text) == ["graph TD\nA-->B"]


def test_kroki_builds_url_and_writes_svg(monkeypatch, tmp_path):
    seen = []

    def fake_post(url, body, timeout=30):
        seen.append((url, body))
        return b"<svg xmlns='http://www.w3.org/2000/svg'><rect/></svg>"

    monkeypatch.setattr(dr, "_http_post", fake_post)
    monkeypatch.setenv("PIPELINE_DIAGRAM_RENDERER", "kroki")
    art = _artifact(tmp_path, "```mermaid\ngraph TD\nA-->B\n```")

    rep = dr.render(str(tmp_path), "1", art)

    assert rep["count"] == 1
    assert rep["renderer"] == "kroki"
    assert dr._kroki_url("svg") == "https://kroki.io/mermaid/svg"
    assert any(u == "https://kroki.io/mermaid/svg" for u, _ in seen)
    svgs = [p for p in rep["rendered"] if p.endswith(".svg")]
    assert len(svgs) == 1
    assert Path(svgs[0]).read_bytes().startswith(b"<svg")


def test_zero_blocks_reports_no_mermaid(monkeypatch, tmp_path):
    monkeypatch.setenv("PIPELINE_DIAGRAM_RENDERER", "kroki")
    art = _artifact(tmp_path, "plain markdown, no diagrams")

    rep = dr.render(str(tmp_path), "1", art)

    assert rep["count"] == 0
    assert rep["reason"] == "no mermaid blocks"
    assert "unavailable" not in rep["reason"]


def test_mmd_always_written_when_off(monkeypatch, tmp_path):
    def _boom(*a, **k):
        raise AssertionError("network must not be called")

    monkeypatch.setattr(dr, "_http_post", _boom)
    monkeypatch.setenv("PIPELINE_DIAGRAM_RENDERER", "off")
    art = _artifact(tmp_path, "```mermaid\nsequenceDiagram\nA->>B: hi\n```")

    rep = dr.render(str(tmp_path), "1", art)

    assert rep["count"] == 1
    assert rep["renderer"] == "unavailable"
    assert len(rep["mmd"]) == 1
    mmd = Path(rep["mmd"][0])
    assert mmd.exists()
    assert mmd.read_text(encoding="utf-8").strip().startswith("sequenceDiagram")
