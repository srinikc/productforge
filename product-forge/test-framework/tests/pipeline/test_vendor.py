"""BI-0202: neutral vendored tools — resolution order, no .opencode default, clear hint."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import vendor  # noqa: E402


def test_vendor_dir_is_neutral():
    vd = vendor.vendor_dir().replace("\\", "/")
    assert vd.endswith("/vendor")
    assert ".opencode" not in vd


def test_resolution_never_defaults_to_opencode(monkeypatch):
    monkeypatch.delenv("ALLOW_OPENCODE_TOOLS_LEGACY", raising=False)
    monkeypatch.delenv("PIPELINE_DRAWIO_CLI", raising=False)
    r = vendor.resolve_tool("drawio")
    if r["found"]:
        assert ".opencode" not in r["path"].replace("\\", "/")


def test_env_var_wins(tmp_path, monkeypatch):
    fake = tmp_path / "drawio_fake.exe"
    fake.write_text("x", encoding="utf-8")
    monkeypatch.setenv("PIPELINE_DRAWIO_CLI", str(fake))
    r = vendor.resolve_tool("drawio")
    assert r["found"] and r["source"] == "env" and r["path"] == str(fake)


def test_vendor_path_used_when_present(tmp_path, monkeypatch):
    monkeypatch.delenv("PIPELINE_DRAWIO_CLI", raising=False)
    monkeypatch.setattr(vendor, "vendor_dir", lambda: str(tmp_path))
    nested = tmp_path / "drawio"
    nested.mkdir()
    exe = nested / "draw.io.exe"
    exe.write_text("x", encoding="utf-8")
    r = vendor.resolve_tool("drawio")
    assert r["found"] and r["source"] == "vendor"


def test_legacy_only_with_flag(tmp_path, monkeypatch):
    monkeypatch.delenv("PIPELINE_DRAWIO_CLI", raising=False)
    monkeypatch.setattr(vendor, "vendor_dir", lambda: str(tmp_path / "empty"))
    monkeypatch.setattr(vendor.shutil, "which", lambda *a: None)
    monkeypatch.setattr(vendor, "_legacy_path", lambda name: str(tmp_path / "legacy.exe"))
    (tmp_path / "legacy.exe").write_text("x", encoding="utf-8")
    assert vendor.resolve_tool("drawio")["source"] != "legacy"  # default: no legacy
    monkeypatch.setenv("ALLOW_OPENCODE_TOOLS_LEGACY", "1")
    assert vendor.resolve_tool("drawio")["source"] == "legacy"


def test_missing_hint_is_neutral():
    h = vendor.missing_hint("drawio")
    assert "vendor/drawio" in h and "PIPELINE_DRAWIO_CLI" in h and ".opencode" not in h


def test_diagram_render_cli_uses_vendor(monkeypatch):
    from core import diagram_render as D
    monkeypatch.setattr(vendor, "resolve_tool",
                        lambda n: {"found": True, "path": "/neutral/drawio", "source": "vendor"})
    assert D._drawio_cli() == "/neutral/drawio"


def test_list_tools_shape():
    rows = vendor.list_tools()
    assert any(r["name"] == "drawio" for r in rows)
    assert all("found" in r and "source" in r for r in rows)
