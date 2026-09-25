"""Per-feature artifact files (option 1B) for design / product-design-spec.

The sectioned generator already makes ONE LLM call per feature; this change
additionally writes ONE FILE PER FEATURE (plus an index) next to the merged
`<agent>-output.md`, which remains the unchanged downstream contract.

Guards:
  t1  per-feature agents emit N feature files + index.md matching the merged F-<n> sections.
  t2  the merged <agent>-output.md is still produced, unchanged in shape, and is the
      only entry in the returned artifact list (downstream contract intact).
  t3  regeneration removes stale feature files (idempotent within the stage features dir).

A stub LLM is injected (no network); the stub answers each per-section prompt with
exactly that section so the sectioned path runs end-to-end.
"""
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.pipeline_executor import PipelineExecutor  # noqa: E402


class _Prof:
    context_window = 100000
    max_output_tokens = 4000
    cost_per_1k_input = 0.0
    cost_per_1k_output = 0.0


class _Reg:
    def get_model(self, name):
        return _Prof()


def _token_info():
    return {
        "input_tokens": 1, "output_tokens": 1, "cached_tokens": 0,
        "reasoning_tokens": 0, "total_tokens": 2, "cost": 0.0,
        "selected_model": "stub-model", "selected_provider": "stub",
        "cost_per_1k_input": 0.0, "cost_per_1k_output": 0.0,
        "finish_reason": "stop", "truncated": False, "retries": 0,
        "continuations": 0, "fallback": False,
    }


_FEATURE_PROMPT = re.compile(r"WRITE ONLY the '## (F-\d+[^']*)' section now for this ONE feature")
_SECTION_PROMPT = re.compile(r"WRITE ONLY the '## ([^']*)' section now;")


def _write_plan(tmp_path, features):
    d = tmp_path / "TestProj"
    d.mkdir(parents=True, exist_ok=True)
    (d / "product-plan.json").write_text(
        json.dumps({"modules": [{"id": "M-1", "name": "Core", "features": features}]}),
        encoding="utf-8")


def _make_executor(tmp_path):
    ex = PipelineExecutor.__new__(PipelineExecutor)  # bypass __init__
    ex.project_dir = str(tmp_path / "TestProj")
    ex.project = "TestProj"
    ex.products_dir = str(tmp_path)
    ex.agent_specs = {}
    ex.enable_tools = False
    ex.tool_registry = None
    ex.execution = None
    ex.tech_stack = {}
    ex.requested_tech_stack = []
    ex.summarizer = None
    ex._last_compaction_saved = 0
    ex.input_cache = None
    ex.model_registry = _Reg()
    ex.model_calls = {"n": 0}

    def _build(agent_id, stage_id, task, contract, artifact_file):
        return f"BASE::{agent_id}::{stage_id}::{task}"

    def _llm(prompt, agent_id, stage_id, pin_model=""):
        ex.model_calls["n"] += 1
        m = _FEATURE_PROMPT.search(prompt)
        if m:
            label = m.group(1)
            return (f"## {label}\n"
                    f"### Behaviour\nThe feature shall work.\n"
                    f"### Validation\nReject empty input.\n"
                    f"### Acceptance criteria\nHappy path passes.\n"), _token_info()
        m = _SECTION_PROMPT.search(prompt)
        if m:
            return f"## {m.group(1)}\n- item one\n- item two\n", _token_info()
        return "## Notes\n- generic\n", _token_info()

    ex._build_agent_prompt = _build
    ex._call_llm = _llm
    ex._collect_stage_artifacts = lambda stage_id: {}
    ex._get_agent_model_config = lambda agent_id, stage_id: {"model": "stub-model", "provider": "stub"}
    ex._scope_guard = lambda: ""
    ex._output_requirements = lambda agent_id: ""
    ex._is_marked_sectioned = lambda agent_id: False
    ex._mark_sectioned = lambda agent_id: None
    return ex


def _merged_section(text, fid):
    m = re.search(rf"^##\s*{re.escape(fid)}\b.*?(?=^##\s|\Z)", text, re.S | re.M)
    return m.group(0).rstrip() if m else ""


FEATURES = [{"id": "F-1", "name": "Alpha"}, {"id": "F-2", "name": "Beta"}]


@pytest.mark.parametrize("agent,stage,suffix", [
    ("design", "1", "functional"),
    ("product-design-spec", "1a", "design"),
])
def test_t1_per_feature_files_match_merged_sections(tmp_path, agent, stage, suffix):
    _write_plan(tmp_path, FEATURES)
    ex = _make_executor(tmp_path)

    arts, _execution = ex._generate_agent_artifacts(agent, stage, "task")

    fdir = tmp_path / "TestProj" / "artifacts" / stage / "features"
    assert (fdir / f"F-1-{suffix}.md").exists()
    assert (fdir / f"F-2-{suffix}.md").exists()

    merged = Path(arts[0]).read_text(encoding="utf-8")
    for fid in ("F-1", "F-2"):
        section = _merged_section(merged, fid)
        assert section, f"merged doc missing {fid}"
        written = (fdir / f"{fid}-{suffix}.md").read_text(encoding="utf-8")
        assert written.rstrip() == section.rstrip()

    index = (fdir / "index.md").read_text(encoding="utf-8")
    for fid, name in (("F-1", "Alpha"), ("F-2", "Beta")):
        assert fid in index and name in index
        assert f"({fid}-{suffix}.md)" in index


def test_t2_merged_file_unchanged_and_only_returned_artifact(tmp_path):
    _write_plan(tmp_path, FEATURES)
    ex = _make_executor(tmp_path)

    arts, execution = ex._generate_agent_artifacts("design", "1", "task")

    # additive: the feature files are NOT part of the returned artifact list
    assert len(arts) == 1
    merged_path = Path(arts[0])
    assert merged_path.name == "design-output.md"
    assert execution.artifacts == [str(merged_path)]

    text = merged_path.read_text(encoding="utf-8")
    assert text.startswith("# DESIGN Output - Stage 1")
    assert "## Output" in text
    assert "## F-1: Alpha" in text and "## F-2: Beta" in text


def test_t3_regeneration_removes_stale_feature_files(tmp_path):
    _write_plan(tmp_path, FEATURES)
    ex = _make_executor(tmp_path)
    ex._generate_agent_artifacts("design", "1", "task")

    fdir = tmp_path / "TestProj" / "artifacts" / "1" / "features"
    stale = fdir / "F-9-functional.md"
    stale.write_text("## F-9: Gone\nold content\n", encoding="utf-8")

    # plan changes: F-2 disappears, F-3 appears
    _write_plan(tmp_path, [{"id": "F-1", "name": "Alpha"}, {"id": "F-3", "name": "Gamma"}])
    ex._generate_agent_artifacts("design", "1", "task")

    assert not stale.exists()
    assert not (fdir / "F-2-functional.md").exists()
    assert (fdir / "F-1-functional.md").exists()
    assert (fdir / "F-3-functional.md").exists()

    index = (fdir / "index.md").read_text(encoding="utf-8")
    assert "F-3" in index and "F-2" not in index
