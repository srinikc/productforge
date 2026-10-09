"""BI-PF: `/pf product` delegates to the canonical runner scripts/run_pipeline.py (arg mapping)."""
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")


def _load_pf():
    spec = importlib.util.spec_from_file_location("pf_cli", ROOT / "scripts" / "pf.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _cap(monkeypatch, pf):
    box = {}

    class _R:
        returncode = 0

    def _run(cmd, **k):
        box["cmd"] = cmd
        return _R()

    monkeypatch.setattr(pf.subprocess, "run", _run)
    return box


def test_new_idea_slug(monkeypatch):
    pf = _load_pf()
    box = _cap(monkeypatch, pf)
    pf.cmd_product(["new", "an idea", "--tier", "kctier"])
    assert box["cmd"][1].replace("\\", "/").endswith("scripts/run_pipeline.py")
    assert box["cmd"][2:] == ["new", "an-idea", "--idea", "an idea", "--tier", "kctier"]


def test_new_explicit_project(monkeypatch):
    pf = _load_pf()
    box = _cap(monkeypatch, pf)
    pf.cmd_product(["new", "myproj", "--idea", "an idea"])
    assert box["cmd"][2:] == ["new", "myproj", "--idea", "an idea"]


def test_continue_passthrough(monkeypatch):
    pf = _load_pf()
    box = _cap(monkeypatch, pf)
    pf.cmd_product(["continue", "proj"])
    assert box["cmd"][2:] == ["continue", "proj"]


def test_fix_maps_to_enhance(monkeypatch):
    pf = _load_pf()
    box = _cap(monkeypatch, pf)
    pf.cmd_product(["fix", "proj", "make it prod ready"])
    assert box["cmd"][2:] == ["enhance", "proj", "--goal", "make it prod ready"]
