"""EDP-04 (BI-PF-1296): the data-plane threat register validates and the gate catches gaps.

Exercises ``scripts/dev/data_plane_threat_check.py`` against the shipped register and against
deliberately-broken copies (missing category, non-resolving owner, missing version).
"""
import copy
import importlib.util
import os
import sys

import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_SPEC = importlib.util.spec_from_file_location(
    "data_plane_threat_check", os.path.join(_ROOT, "scripts", "dev", "data_plane_threat_check.py"))
dpt = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(dpt)


def test_shipped_register_is_valid():
    assert dpt.validate(dpt._load()) == []


def test_missing_category_is_caught():
    reg = dpt._load()
    reg["threats"] = [t for t in reg["threats"] if t["id"] != "egress"]
    probs = dpt.validate(reg)
    assert any("egress" in p for p in probs)


def test_dangling_owner_is_caught():
    reg = copy.deepcopy(dpt._load())
    reg["threats"][0]["owner"] = "does/not/exist.py"
    probs = dpt.validate(reg)
    assert any("owner does not resolve" in p for p in probs)


def test_missing_version_is_caught():
    reg = dpt._load()
    reg.pop("version", None)
    probs = dpt.validate(reg)
    assert any("version" in p for p in probs)


def test_render_lists_all_categories():
    doc = dpt.render(dpt._load())
    for cat in dpt._REQUIRED:
        assert cat in doc


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
