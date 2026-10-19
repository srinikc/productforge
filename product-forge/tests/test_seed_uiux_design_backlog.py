"""Idempotency guard for the UIUX design-system seed (BI-PF-1436)."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _seed_module():
    spec = importlib.util.spec_from_file_location(
        "seed_uiux_design_backlog", ROOT / "scripts" / "dev" / "seed_uiux_design_backlog.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_should_write_only_for_new_or_empty_deps():
    seed = _seed_module()
    prior = {"uiux-design-system-inclusion:skills-registry"}
    assert seed._should_write("uiux-design-system-inclusion:new", prior, []) is True
    assert seed._should_write("uiux-design-system-inclusion:skills-registry", prior, []) is True
    assert seed._should_write(
        "uiux-design-system-inclusion:skills-registry", prior, [{"task_id": "BI-PF-1"}]) is False
