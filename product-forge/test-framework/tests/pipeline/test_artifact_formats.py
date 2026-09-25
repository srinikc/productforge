"""Tests for the dynamic artifact-format policy (BI-0110). Offline; emitters monkeypatched."""
import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import core.artifact_formats as af


def _cfg(**over):
    base = {"default": ["md"], "by_agent": {}, "by_kind": {},
            "project_overrides": {}, "capability_fallback": True}
    base.update(over)
    return base


def test_t1_default_and_agent_extras(monkeypatch):
    monkeypatch.setattr(af, "_load_config", lambda: _cfg(
        by_agent={"design": ["md", "pdf", "html"]}))
    monkeypatch.setattr(af, "_emitter_available", lambda f: True)
    assert af.formats_for("p", "unknown", "1", "", "body") == ["md"]
    out = af.formats_for("p", "design", "3", "", "body")
    assert out[0] == "md"
    assert "pdf" in out and "html" in out


def test_t2_unavailable_emitter_dropped(monkeypatch):
    monkeypatch.setattr(af, "_load_config", lambda: _cfg(
        by_agent={"design": ["md", "pdf", "docx"]}))
    monkeypatch.setattr(af, "_emitter_available", lambda f: f == "md")
    assert af.formats_for("p", "design", "3", "", "body") == ["md"]
    res = af.emit("p", str(Path("nope.md")), ["md", "docx"], "body")
    assert "error" in res["docx"]


def test_t3_content_heuristics(monkeypatch):
    table = "| a | b |\n|---|---|\n| 1 | 2 |\n"
    mermaid = "```mermaid\ngraph TD; A-->B;\n```"
    assert "xlsx" in af.content_candidates(table)
    assert "svg" in af.content_candidates(mermaid)
    assert af.content_candidates("plain prose") == []
    monkeypatch.setattr(af, "_load_config", lambda: _cfg())
    monkeypatch.setattr(af, "_emitter_available", lambda f: True)
    assert "xlsx" in af.formats_for("p", "a", "1", "", table)
    assert "svg" in af.formats_for("p", "a", "1", "", mermaid)


def test_t4_emit_no_fabrication(tmp_path, monkeypatch):
    md = tmp_path / "a-output.md"
    content = "# Title\n\nBody line\n"
    md.write_text(content, encoding="utf-8")
    monkeypatch.setattr(af, "_emitter_available", lambda f: True)

    def boom(*a, **k):
        raise RuntimeError("lib missing")

    monkeypatch.setitem(af._EMITTERS, "docx", boom)
    res = af.emit("p", str(md), ["md", "html", "docx"], content, agent_id="a")
    assert res["md"] == str(md)
    assert isinstance(res["html"], str) and os.path.exists(res["html"])
    assert "error" in res["docx"]
    assert not (tmp_path / "a-output.docx").exists()


def test_t5_project_overrides_precedence(monkeypatch):
    cfg = _cfg(by_agent={"design": ["md", "pdf"]},
               project_overrides={"proj": ["md", "docx"]})
    monkeypatch.setattr(af, "_load_config", lambda: cfg)
    monkeypatch.setattr(af, "_emitter_available", lambda f: True)
    assert af.formats_for("proj", "design", "3", "", "x") == ["md", "docx"]
    assert "pdf" in af.formats_for("other", "design", "3", "", "x")
    cfg["project_overrides"]["proj2"] = {"by_agent": {"design": ["md", "pptx"]}}
    assert af.formats_for("proj2", "design", "3", "", "x") == ["md", "pptx"]
