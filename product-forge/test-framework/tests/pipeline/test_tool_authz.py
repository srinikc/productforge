"""F0-5 (PF-004/BV-C02, PF-227): fail-closed tool authz + path containment."""
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.pipeline_executor import PipelineExecutor  # noqa: E402
from core.paths import products  # noqa: E402


def _executor():
    ex = PipelineExecutor.__new__(PipelineExecutor)
    ex.agent_specs = {}
    ex.project_dir = "."
    ex.tool_registry = types.SimpleNamespace(
        execute=lambda *a, **k: types.SimpleNamespace(ok=True, to_dict=lambda: {"ok": True}),
        schemas=lambda *a, **k: [])
    ex.tool_cache = None
    return ex


def test_missing_agent_spec_denies_tool():
    r = _executor().execute_agent_tool("ghost", "run_command", {})
    assert r["ok"] is False and "denied" in r["error"].lower()


def test_tool_not_in_allowlist_denies():
    spec = types.SimpleNamespace(tools=["read_file"])
    ex = _executor()
    ex.agent_specs = {"design": spec}
    r = ex.execute_agent_tool("design", "run_command", {})
    assert r["ok"] is False and "not permitted" in r["error"].lower()


def test_path_containment_blocks_traversal():
    for bad in ("../evil", "a/b", "..", "/abs"):
        try:
            products(bad)
            assert False, f"should have rejected {bad!r}"
        except ValueError:
            pass
    assert "MyProject" in str(products("MyProject", "backlog"))
