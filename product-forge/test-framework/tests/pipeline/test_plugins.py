"""BI-0200: plugin/registry framework (drop-in registration + fail-closed resolve + composition)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import plugins as pl  # noqa: E402
from core import pipeline_composition as pc  # noqa: E402
from core.paths import ROOT  # noqa: E402


def _reset():
    pl._save({"version": 1, "plugins": {}})


def test_register_and_resolve_tool_plugin_no_core_edit():
    _reset()
    r = pl.register("echo", "tool", "adapters.plugins.example:build_tool",
                    config={"name": "echo_plugin"})
    assert r["ok"]
    res = pl.resolve("echo")
    assert res["ok"] and res["kind"] == "tool"
    assert res["port"]["spec"]["name"] == "echo_plugin"
    # the handler runs (no network, no core edit)
    assert res["port"]["handler"]({"text": "hi"}, ".")["output"] == "echo: hi"
    _reset()


def test_unknown_kind_and_adapter_fail_closed():
    _reset()
    assert pl.register("bad", "nonsense", "x:y")["ok"] is False
    pl.register("u", "tool", "does.not.exist:build")
    assert pl.resolve("u")["ok"] is False
    assert pl.resolve("nope")["ok"] is False
    _reset()


def test_missing_requires_fail_closed():
    _reset()
    pl.register("needs", "tool", "adapters.plugins.example:build_tool", requires=["absent-dep"])
    r = pl.resolve("needs")
    assert r["ok"] is False and "missing_requires" in r["error"]
    _reset()


def test_stage_plugin_feeds_composition_without_new_path():
    _reset()
    pl.register("ex-stage", "stage", "adapters.plugins.example:build_stage",
                config={"stage_id": "0x-example", "after": "0a", "name": "Example"})
    contribs = pl.stage_contributions()
    assert contribs and contribs[0]["key"] == "ex-stage"
    base = json.loads((Path(ROOT) / "pipeline-definition.json").read_text(encoding="utf-8"))
    comp = pc.effective_definition(base, packs=contribs)
    assert "0x-example" in comp["stages"]
    _reset()


def test_disabled_plugins_excluded_and_validate():
    _reset()
    pl.register("t", "tool", "adapters.plugins.example:build_tool")
    assert pl.validate()["enabled"] == 1
    pl.set_enabled("t", False)
    assert pl.validate()["enabled"] == 0
    assert pl.list_plugins(enabled_only=True) == []
    _reset()
