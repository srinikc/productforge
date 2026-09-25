"""
Cache-policy regression (philosophy: generation OUTPUT is never served from a
cache; only the INPUT side is cached, keyed by a fingerprint of resolved inputs).

Layers covered:
  t1  outputs never cached -> two identical runs call the model twice.
  t2  input-side (fingerprint-keyed) cache HIT on identical inputs, MISS on change.
  t3  PIPELINE_NO_CACHE=1 / --no-cache -> zero cache reads.
  t4  empty / reasoning-only / checklist-failing output -> no cache entry written.

A stub LLM is injected so no network call is ever made.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.pipeline_executor import PipelineExecutor  # noqa: E402
from core.orchestrator.storage import InputCache, input_cache_key, fingerprint_inputs  # noqa: E402


GOOD_ARCH = (
    "# Architect Output\n\n"
    "## Architecture Style\nA modular monolith with clear module boundaries.\n\n"
    "## Tech Stack\nFastAPI + SQLite for the first cut.\n\n"
    "## Components\n- api gateway\n- worker\n- persistence\n\n"
    "## Security Considerations\nAuthN/AuthZ, secrets in env, least privilege.\n\n"
    "## ADRs\nADR-1: choose FastAPI for speed of delivery.\n"
)

CHECKLIST_FAILING = (
    "# Architect Output\n\n"
    "## Notes\nThis document intentionally omits every essential architect section so the\n"
    "output checklist fails while still being a long, structured (non-reasoning) document.\n"
    "It contains enough characters to pass the 'too short' guard but no required headings.\n"
)

REASONING_ONLY = (
    "Here is a thinking process: we need to produce the architecture document. "
    "The user wants components, security and ADRs. Let me think about how to structure it. "
    "I will first consider the modules, then the stack, then the deployment topology. "
    "We should produce a comprehensive answer but this is just scratch reasoning.\n"
)


class _Prof:
    context_window = 100000
    max_output_tokens = 4000
    cost_per_1k_input = 0.0
    cost_per_1k_output = 0.0


class _Reg:
    def get_model(self, name):
        return _Prof()


def _token_info(content="", model="stub-model", truncated=False, fallback=False):
    return {
        "content": content,
        "input_tokens": 1, "output_tokens": 1, "cached_tokens": 0,
        "reasoning_tokens": 0, "total_tokens": 2, "cost": 0.0,
        "selected_model": model, "selected_provider": "stub",
        "cost_per_1k_input": 0.0, "cost_per_1k_output": 0.0,
        "finish_reason": "stop", "truncated": truncated, "retries": 0,
        "continuations": 0, "fallback": fallback,
    }


def _make_executor(tmp_path, upstream=None, llm_content=GOOD_ARCH):
    ex = PipelineExecutor.__new__(PipelineExecutor)  # bypass __init__
    ex.project_dir = str(tmp_path)
    ex.project = "TestProj"
    ex.products_dir = str(tmp_path)
    ex.agent_specs = {}
    ex.enable_tools = False
    ex.tool_registry = None
    ex.execution = None
    ex.tech_stack = {}
    ex.requested_tech_stack = []
    ex._last_compaction_saved = 0
    ex.input_cache = InputCache(str(tmp_path))
    ex.build_calls = {"n": 0}
    ex.model_calls = {"n": 0}

    def _build(agent_id, stage_id, task, contract, artifact_file):
        ex.build_calls["n"] += 1
        return f"BASE::{agent_id}::{stage_id}::{task}"

    def _call_llm(prompt, agent_id, stage_id, pin_model=""):
        ex.model_calls["n"] += 1
        return llm_content, _token_info(content=llm_content)

    ex._build_agent_prompt = _build
    ex._call_llm = _call_llm
    ex._collect_stage_artifacts = (lambda stage_id: dict(upstream or {}))
    ex._get_agent_model_config = lambda agent_id, stage_id: {"model": "stub-model", "provider": "stub"}
    ex._format_llm_output = (lambda agent_id, stage_id, model, provider, content, *a, **k: content)
    ex._is_marked_sectioned = lambda agent_id: False
    ex._mark_sectioned = lambda agent_id: None
    return ex


def _isolate_env(monkeypatch):
    for k in ("PIPELINE_NO_CACHE", "PIPELINE_ALLOW_OUTPUT_CACHE", "PIPELINE_INPUT_CACHE"):
        monkeypatch.delenv(k, raising=False)


# ── t1: rerun regenerates; outputs are never cached ──────────────────────────
def test_t1_rerun_regenerates_calls_model_twice(tmp_path, monkeypatch):
    _isolate_env(monkeypatch)
    ex = _make_executor(tmp_path)

    arts1, _ = ex._generate_agent_artifacts("architect", "1", "task A")
    assert ex.model_calls["n"] == 1
    assert arts1 and Path(arts1[0]).exists()
    first = Path(arts1[0]).read_text(encoding="utf-8")

    # Two identical runs -> the model is called again (no output cache) and the
    # artifact is rewritten.
    arts2, _ = ex._generate_agent_artifacts("architect", "1", "task A")
    assert ex.model_calls["n"] == 2
    assert Path(arts2[0]).read_text(encoding="utf-8") == first

    # Legacy output cache must never have been populated (.llm-cache absent/empty).
    llm_cache_dir = tmp_path / ".llm-cache"
    assert (not llm_cache_dir.exists()) or (not list(llm_cache_dir.glob("*.json")))


def test_t1_rerun_invalidation_recomputes_inputs(tmp_path, monkeypatch):
    _isolate_env(monkeypatch)
    ex = _make_executor(tmp_path)

    ex._generate_agent_artifacts("architect", "1", "task A")
    ex._generate_agent_artifacts("architect", "1", "task A")
    # second run reused the cached prompt (no rebuild) but still called the model
    assert ex.build_calls["n"] == 1
    assert ex.model_calls["n"] == 2

    # A deliberate rerun invalidates the input cache -> inputs recompute.
    ex.input_cache.clear(agents=["architect"])
    ex._generate_agent_artifacts("architect", "1", "task A")
    assert ex.build_calls["n"] == 2
    assert ex.model_calls["n"] == 3


# ── t2: input cache HIT / MISS ───────────────────────────────────────────────
def test_t2_input_cache_hit_and_miss(tmp_path, monkeypatch):
    _isolate_env(monkeypatch)
    upstream = tmp_path / "upstream-ideation.md"
    upstream.write_text("UPSTREAM-A", encoding="utf-8")
    ex = _make_executor(tmp_path, upstream={"1_ideation": str(upstream)})

    # run 1: MISS -> build prompt, call model, write an input-cache entry.
    ex._generate_agent_artifacts("architect", "1", "task A")
    assert ex.build_calls["n"] == 1
    assert ex.model_calls["n"] == 1
    assert list((tmp_path / ".input-cache").glob("*.json"))

    # run 2: identical inputs -> HIT (prompt reused), model still called.
    ex._generate_agent_artifacts("architect", "1", "task A")
    assert ex.build_calls["n"] == 1
    assert ex.model_calls["n"] == 2

    # change the upstream artifact -> fingerprint changes -> MISS (rebuild).
    upstream.write_text("UPSTREAM-B", encoding="utf-8")
    ex._generate_agent_artifacts("architect", "1", "task A")
    assert ex.build_calls["n"] == 2
    assert ex.model_calls["n"] == 3


def test_t2_fingerprint_changes_with_upstream():
    a = fingerprint_inputs(upstream_digests=["x:1"], feedback="t", section_id="1/architect")
    b = fingerprint_inputs(upstream_digests=["x:2"], feedback="t", section_id="1/architect")
    assert a != b
    assert a == fingerprint_inputs(upstream_digests=["x:1"], feedback="t", section_id="1/architect")
    # key includes model/agent/prompt/template/fingerprint -> all part of identity
    k1 = input_cache_key("m", "architect", "p", "v1", a)
    assert k1 != input_cache_key("m2", "architect", "p", "v1", a)
    assert k1 != input_cache_key("m", "architect", "p", "v2", a)
    assert k1 != input_cache_key("m", "architect", "p", "v1", b)


# ── t3: hard bypass -> zero cache reads ──────────────────────────────────────
def test_t3_no_cache_flag_zero_reads(tmp_path, monkeypatch):
    _isolate_env(monkeypatch)
    monkeypatch.setenv("PIPELINE_NO_CACHE", "1")
    ex = _make_executor(tmp_path)

    reads = {"n": 0}
    orig_get = ex.input_cache.get

    def spy_get(key, agent_id=""):
        reads["n"] += 1
        return orig_get(key, agent_id)

    ex.input_cache.get = spy_get

    ex._generate_agent_artifacts("architect", "1", "task A")
    assert reads["n"] == 0                       # no cache read
    assert ex.model_calls["n"] == 1              # full recompute
    assert not list((tmp_path / ".input-cache").glob("*.json"))  # no writes


def test_t3_run_pipeline_has_no_cache_flag_and_env():
    """--no-cache must exist and set PIPELINE_NO_CACHE (guard the CLI wiring)."""
    src = (Path(__file__).parent.parent.parent.parent /
           "scripts" / "run_pipeline.py").read_text(encoding="utf-8")
    assert '"--no-cache"' in src
    assert 'os.environ["PIPELINE_NO_CACHE"] = "1"' in src


def test_t3_no_cache_helper_reflects_env(monkeypatch):
    from core.orchestrator.storage import no_cache, input_cache_enabled
    monkeypatch.delenv("PIPELINE_NO_CACHE", raising=False)
    assert no_cache() is False
    monkeypatch.setenv("PIPELINE_NO_CACHE", "1")
    assert no_cache() is True
    monkeypatch.delenv("PIPELINE_INPUT_CACHE", raising=False)
    assert input_cache_enabled() is True          # default ON
    monkeypatch.setenv("PIPELINE_INPUT_CACHE", "0")
    assert input_cache_enabled() is False


# ── t4: bad output is never cached ───────────────────────────────────────────
def _assert_cache_empty(tmp_path):
    d = tmp_path / ".input-cache"
    assert (not d.exists()) or (not list(d.glob("*.json")))


def test_t4_empty_output_not_cached(tmp_path, monkeypatch):
    _isolate_env(monkeypatch)
    ex = _make_executor(tmp_path, llm_content="")
    ex._generate_agent_artifacts("architect", "1", "task A")
    _assert_cache_empty(tmp_path)


def test_t4_reasoning_only_output_not_cached(tmp_path, monkeypatch):
    _isolate_env(monkeypatch)
    ex = _make_executor(tmp_path, llm_content=REASONING_ONLY)
    ex._generate_agent_artifacts("architect", "1", "task A")
    _assert_cache_empty(tmp_path)


def test_t4_checklist_failing_output_not_cached(tmp_path, monkeypatch):
    _isolate_env(monkeypatch)
    ex = _make_executor(tmp_path, llm_content=CHECKLIST_FAILING)
    arts, _ = ex._generate_agent_artifacts("architect", "1", "task A")
    # artifact IS written (it is not "unusable"), but it must NOT be cached.
    assert arts
    _assert_cache_empty(tmp_path)


# ── Layer 1 at the LLM client: output cache is never read by default ─────────
def test_output_cache_never_read_by_default(tmp_path, monkeypatch):
    _isolate_env(monkeypatch)
    from core.orchestrator.llm_client import LLMClient

    class _SpyCache:
        def __init__(self):
            self.gets = 0
            self.sets = 0

        def get(self, *a, **k):
            self.gets += 1
            return None

        def set(self, *a, **k):
            self.sets += 1

    client = LLMClient.__new__(LLMClient)
    client.model_registry = _Reg()
    client._resolve_model_config = lambda agent_id, stage_id: {
        "model": "stub-model", "provider": "stub", "api_endpoint": "http://x"}
    client.llm_cache = _SpyCache()
    client.project = "TestProj"
    client.semantic_cache = None

    calls = {"n": 0}

    def fake_single(prompt, model_name, provider, api_endpoint, session_id, agent_id,
                    stage_id, max_output_tokens, **kw):
        calls["n"] += 1
        return "REAL-OUTPUT", _token_info("REAL-OUTPUT")

    client._call_llm_single = fake_single

    content, _ti = client._call_llm("prompt", "architect", "1")
    assert content == "REAL-OUTPUT"
    assert calls["n"] == 1
    assert client.llm_cache.gets == 0     # output cache NOT read
    assert client.llm_cache.sets == 0     # output cache NOT written
