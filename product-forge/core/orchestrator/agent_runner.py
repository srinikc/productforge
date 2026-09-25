"""
Agent runner mixin (extracted from pipeline_executor - 1A.11).

Mixin (not composition) because these methods operate directly on executor
state (`self`). Moving them verbatim keeps behavior identical while shrinking
pipeline_executor.py.

Holds: prompt building, LLM/tool invocation, and artifact generation/writing.
"""
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.context_manager import get_contract
from core.orchestrator.storage import (TEMPLATE_VERSION, digest_text, fingerprint_inputs,
                                       input_cache_enabled, input_cache_key, no_cache)
from core.orchestrator.types import AgentExecution
from core.tech_stack import stack_to_layers
from core.artifact_formats import (emit as _emit_artifact_formats,
                                   formats_for as _formats_for)


_REASONING_MARKERS = (
    "here is a thinking process", "here's a thinking process", "we need answer",
    "need honor brief", "need parse", "let me think", "chain of thought",
    "thinking process:", "we should produce", "we need to produce",
)


def _unusable_artifact_reason(content) -> str:
    """Return a reason if `content` is NOT a usable artifact, else '' (BI-0034).

    Catches: empty/whitespace, implausibly short, and chain-of-thought leakage
    (reasoning models) that the LLM client should have stripped.
    """
    t = (content or "").strip()
    if not t:
        return "empty content"
    if len(t) < 200:
        return f"too short ({len(t)} chars)"
    low = t[:800].lower()
    for m in _REASONING_MARKERS:
        if m in low:
            return "reasoning-only output (chain-of-thought)"
    first = [ln.strip() for ln in t.splitlines()[:6] if ln.strip()]
    if first and not first[0].startswith("#") and first[0].lower().startswith(
            ("we ", "i ", "let me", "okay", "sure", "the user", "so ")):
        return "prose reasoning instead of a structured artifact"
    return ""


class AgentRunnerMixin:
    def _generate_with_tools(self, agent_id: str, stage_id: str, prompt: str, spec) -> Tuple[str, Dict]:
        """Run the agent with a bounded NATIVE tool loop (falls back to text protocol)."""
        from core.agent_tool_loop import run_native_tool_loop
        acc = {"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0, "reasoning_tokens": 0,
               "total_tokens": 0, "cost": 0.0, "selected_model": "", "selected_provider": "",
               "cost_per_1k_input": 0.0, "cost_per_1k_output": 0.0, "finish_reason": "",
               "truncated": False, "retries": 0, "continuations": 0, "fallback": False,
               "tool_calls": 0, "tool_iterations": 0}

        def _acc(ti):
            for k in ("input_tokens", "output_tokens", "cached_tokens", "reasoning_tokens",
                      "total_tokens", "cost"):
                acc[k] = acc.get(k, 0) + (ti.get(k, 0) or 0)
            for k in ("selected_model", "selected_provider", "cost_per_1k_input", "cost_per_1k_output"):
                if ti.get(k):
                    acc[k] = ti[k]

        contract = get_contract(agent_id)
        # Dynamic tools: base (card) + role/need-driven additions (e.g. web for research).
        try:
            from core import tool_policy as _tp
            _eff = _tp.tools_for(agent_id, base_tools=getattr(spec, "tools", None) or [],
                                 project_dir=self.project_dir,
                                 description=getattr(spec, "description", "") or "")
            if _eff:
                spec.tools = _eff
        except Exception:
            pass
        try:
            _f = float(os.getenv("TOOL_LOOP_TOKEN_FACTOR", "3"))
        except (TypeError, ValueError):
            _f = 3.0
        tool_token_cap = int((contract.get("max_input_tokens", 8000) +
                              max(contract.get("max_output_tokens", 4000), 4000)) * _f)

        # Adaptive reasoning depth (4.9): tune tool-loop iterations to complexity.
        try:
            from core.phase3_advanced import AdaptiveReasoningController
            arc = getattr(self, "_reasoning_ctrl", None) or AdaptiveReasoningController(self.products_dir)
            self._reasoning_ctrl = arc
            _stage_num = int(str(stage_id)[0]) if str(stage_id)[:1].isdigit() else 0
            _depth = arc.assess_complexity(prompt, _stage_num)
            _depth_iters = arc.get_config(_depth).get("iterations", 6)
            max_iters = max(2, min(int(os.getenv("TOOL_LOOP_MAX_ITERS", "6")), int(_depth_iters)))
            print(f"  [REASONING] {agent_id}: depth={_depth} max_iters={max_iters}")
        except Exception:
            max_iters = int(os.getenv("TOOL_LOOP_MAX_ITERS", "6"))

        def _run(seed_messages):
            def chat_fn(msgs, tools):
                msg, ti = self._chat_with_tools(msgs, agent_id, stage_id, tools)
                _acc(ti)
                return msg
            return run_native_tool_loop(chat_fn, self.tool_registry, spec, self.project_dir,
                                        seed_messages,
                                        max_iters=max_iters,
                                        stop_check=lambda: acc["total_tokens"] >= tool_token_cap,
                                        require_write_first=(agent_id.startswith("implement")
                                                             or agent_id in ("devops", "fix")))

        def _needs_retry(stats):
            if not getattr(spec, "tools", None):
                return False
            code_or_test = (agent_id.startswith("implement")
                            or agent_id in ("devops", "fix", "validate"))
            if stats.get("tool_calls", 0) == 0 and code_or_test:
                return True
            if ("write_file" in spec.tools and stats.get("writes", 0) == 0
                    and (agent_id.startswith("implement")
                         or agent_id in ("devops", "package", "fix"))):
                return True
            return False

        try:
            final, _m, stats = _run([{"role": "user", "content": prompt}])
            if _needs_retry(stats):
                print(f"  [TOOLS] {agent_id}: no effective file writes; retrying strict")
                strict = [{"role": "system", "content":
                           "You MUST use the write_file tool to create the required files in the "
                           "workspace (e.g. src/..., tests/...). Do NOT describe code — actually write it."},
                          {"role": "user", "content": prompt}]
                final, _m, stats = _run(strict)
            acc["tool_calls"] = stats.get("tool_calls", 0)
            acc["tool_iterations"] = stats.get("iterations", 0)
            acc["tool_writes"] = stats.get("writes", 0)
            print(f"  [TOOLS] {agent_id}: {acc['tool_calls']} tool call(s), "
                  f"{acc['tool_writes']} write(s) in {acc['tool_iterations']} iteration(s)")
            if not (final or "").strip():
                # Tool loop produced no final text (e.g. read-only research agents) ->
                # fall back to a single call so an artifact is still produced.
                print(f"  [TOOLS] {agent_id}: empty final content; falling back to single call")
                return self._call_llm(prompt, agent_id, stage_id)
            _fl = (final or "").strip()
            # A tiny / planning-only final with NO file written means the loop stopped at a plan
            # announcement. LADDER: (1) re-prompt WITH tools (actually use them), (2) only if that
            # still stalls, a single no-tool full-document call.
            if acc["tool_writes"] == 0 and len(_fl) < 300:
                if getattr(spec, "tools", None):
                    tool_use = [{"role": "system", "content":
                                 "Your previous reply only DESCRIBED a plan. Do the work now: USE "
                                 "the available tools — call http_get to fetch any current facts you "
                                 "need, then write_file (or output) the FULL deliverable. Do not "
                                 "describe a plan; produce the actual document."},
                                {"role": "user", "content": prompt}]
                    print(f"  [TOOLS] {agent_id}: stalled ({len(_fl)} chars, 0 writes); "
                          f"re-prompting WITH tools")
                    final2, _m2, stats2 = _run(tool_use)
                    f2 = (final2 or "").strip()
                    if f2 and (stats2.get("writes", 0) > 0 or len(f2) >= 300):
                        acc["tool_calls"] = stats2.get("tool_calls", 0)
                        acc["tool_iterations"] = stats2.get("iterations", 0)
                        acc["tool_writes"] = stats2.get("writes", 0)
                        print(f"  [TOOLS] {agent_id}: recovered WITH tools "
                              f"({acc['tool_calls']} calls, {acc['tool_writes']} writes)")
                        return final2, acc
                print(f"  [TOOLS] {agent_id}: still stalled; last resort = no-tool full-document call")
                return self._call_llm(prompt, agent_id, stage_id)
            return final, acc
        except Exception as e:
            print(f"  [TOOLS] {agent_id} native loop error ({e}); falling back to single call")
            return self._call_llm(prompt, agent_id, stage_id)


    def _input_fingerprint(self, agent_id: str, stage_id: str, task: str) -> str:
        """Digest of the resolved inputs that affect this agent's output (Layer 2):
        upstream artifact content digests + task/feedback + stage/agent + config."""
        upstream = []
        try:
            for key, path in self._collect_stage_artifacts(stage_id).items():
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        upstream.append(f"{key}:{digest_text(f.read())}")
                except Exception:
                    pass
        except Exception:
            pass
        cfg = {}
        try:
            ts = getattr(self, "tech_stack", {}) or {}
            cfg = {"chosen": ts.get("chosen") or {},
                   "requested": list(getattr(self, "requested_tech_stack", []) or [])}
        except Exception:
            cfg = {}
        return fingerprint_inputs(upstream_digests=upstream, feedback=task or "",
                                  notes="", conditions="",
                                  section_id=f"{stage_id}/{agent_id}", config=cfg)

    def _cache_output_ok(self, agent_id: str, artifact_file: str, content: str) -> bool:
        """Layer 4: never cache bad output — empty/reasoning-only, or checklist-failing."""
        if _unusable_artifact_reason(content):
            return False
        try:
            from core.output_checklist import check, has_checklist
            if has_checklist(agent_id):
                res = check(agent_id, [artifact_file])
                if res.get("applicable") and not res.get("ok", True):
                    return False
        except Exception:
            pass
        return True

    def _generate_agent_artifacts(self, agent_id: str, stage_id: str, task: str) -> Tuple[List[str], AgentExecution]:
        """Generate structured artifacts for an agent by calling LLM.
        
        Returns:
            Tuple of (artifact_files_list, agent_execution_with_token_info)
        """
        artifacts = []
        
        from core import stage_paths as _sp
        stage_dir = _sp.stage_dir(self.project_dir, stage_id, create=True)

        artifact_file = os.path.join(stage_dir, f"{agent_id}-output.md")
        contract = get_contract(agent_id)

        # Per-agent, run-scoped log (standard naming: logs/<run_id>/<stage>-<agent>.log).
        try:
            from core import log_router as _lr
            _run_id = ""
            try:
                _run_id = (self._get_run_id() if hasattr(self, "_get_run_id")
                           else getattr(getattr(self, "execution", None), "pipeline_id", "") or "")
            except Exception:
                _run_id = ""
            _log = _lr.agent_log_path(self.project_dir, stage_id, agent_id, _run_id)
            _lr.log_event(_log, run_id=_run_id, stage=stage_id, agent=agent_id,
                          event="agent_start", message=f"task={str(task)[:120]}")
            self._agent_log_path = _log
        except Exception:
            self._agent_log_path = ""


        # Per-feature files are regenerated from scratch each run; drop any blocks
        # stashed by a previous (possibly different) generation before we start.
        try:
            _pf_store = getattr(self, "_per_feature_sections", None)
            if _pf_store is not None:
                _pf_store.pop(agent_id, None)
        except Exception:
            pass
        
        # ── Layer 2: input-side cache. Caches the ASSEMBLED PROMPT, never the
        # output; generation ALWAYS calls the model (Layer 1). A hit means the
        # resolved inputs are provably unchanged, so the assembled prompt is reused.
        _cache = getattr(self, "input_cache", None)
        _cache_on = _cache is not None and input_cache_enabled() and not no_cache()
        _cache_key = ""
        _fingerprint = ""
        _prompt_from_cache = None
        if _cache_on:
            _fingerprint = self._input_fingerprint(agent_id, stage_id, task)
            try:
                _model = (self._get_agent_model_config(agent_id, stage_id) or {}).get("model", "")
            except Exception:
                _model = ""
            _cache_key = input_cache_key(_model, agent_id, task, TEMPLATE_VERSION, _fingerprint)
            _entry = _cache.get(_cache_key, agent_id)
            if _entry and _entry.get("prompt"):
                print(f"  [IN-CACHE] {agent_id}: HIT key={_cache_key[:8]} "
                      f"fingerprint={_fingerprint[:8]}")
                _prompt_from_cache = _entry["prompt"]
            else:
                print(f"  [IN-CACHE] {agent_id}: MISS (inputs changed)")
        elif _cache is not None:
            print(f"  [IN-CACHE] {agent_id}: SKIP (cache disabled)")

        # Build (or reuse) the prompt for the LLM.
        if _prompt_from_cache is not None:
            prompt = _prompt_from_cache
            self._last_compaction_saved = 0
        else:
            prompt = self._build_agent_prompt(agent_id, stage_id, task, contract, artifact_file)

        # Call LLM to generate real content - now returns both content and token info
        _spec = getattr(self, "agent_specs", {}).get(agent_id)
        use_tools = bool(getattr(self, "enable_tools", False) and _spec is not None
                         and getattr(_spec, "tools", None) and self.tool_registry)
        # Dynamic strategy: one call when it fits, sectioned (many) when needed.
        outline = None
        try:
            from core.agent_requirements import decide_strategy, per_feature_agents, feature_outline
            if agent_id in per_feature_agents():
                outline = feature_outline(getattr(self, "products_dir", "products"),
                                          getattr(self, "project", ""))
            strategy = decide_strategy(agent_id, prior_truncated=self._is_marked_sectioned(agent_id),
                                       feature_outline=outline)
        except Exception:
            strategy = "single"
            outline = None
        if strategy == "sectioned" and not use_tools:
            print(f"  [GENERATION] {agent_id}: sectioned (one call per section + merge)")
            content, token_info = self._generate_sectioned(agent_id, stage_id, task,
                                                           contract, artifact_file, prompt,
                                                           outline=outline)
        elif use_tools:
            content, token_info = self._generate_with_tools(agent_id, stage_id, prompt, _spec)
        else:
            content, token_info = self._call_llm(prompt, agent_id, stage_id)
            if token_info.get("truncated"):
                # Remember: this agent needs sectioned generation next time.
                self._mark_sectioned(agent_id)

        _bad = _unusable_artifact_reason(content)
        if token_info.get("truncated") or _bad:
            # NEVER publish an incomplete/empty/reasoning-only artifact as completed
            # (BI-0034). Keep the partial for debugging and mark needs_retry so the
            # agent re-runs (verbose/sectioned) until it completes or the cap hits.
            reason = "output truncated (incomplete artifact; will re-run)" if token_info.get("truncated") \
                else f"unusable artifact: {_bad} (will re-run)"
            print(f"  [UNUSABLE/TRUNCATED] {agent_id}@{stage_id}: {reason}; marking needs_retry "
                  f"(no completed artifact written)")
            try:
                with open(artifact_file + ".partial", "w", encoding="utf-8") as f:
                    f.write(content or "")
            except Exception:
                pass
            execution = AgentExecution(
                agent_id=agent_id,
                stage_id=stage_id,
                status="needs_retry",
                started_at=datetime.now().isoformat(),
                completed_at=datetime.now().isoformat(),
                error=reason,
                artifacts=[],
                selected_model=token_info.get("selected_model", ""),
                selected_provider=token_info.get("selected_provider", ""),
                total_tokens=token_info.get("total_tokens", 0),
                input_tokens=token_info.get("input_tokens", 0),
                output_tokens=token_info.get("output_tokens", 0),
                cost=token_info.get("cost", 0.0),
                truncated=True,
            )
            return [], execution

        # LLM fallback (template) is NOT success: never write a stub artifact or
        # mark the agent completed. Surface a hard failure so retries / circuit
        # breakers / stop-conditions can react.
        if token_info.get("fallback") or token_info.get("selected_model") == "":
            print(f"[ERROR] {agent_id}@{stage_id}: LLM unavailable; marking FAILED "
                  f"(no template artifact written)")
            execution = AgentExecution(
                agent_id=agent_id,
                stage_id=stage_id,
                status="failed",
                started_at=datetime.now().isoformat(),
                completed_at=datetime.now().isoformat(),
                error="LLM unavailable (fallback) - no usable response",
                selected_model="",
                selected_provider="",
            )
            return [], execution

        if content:
            # Format with metadata
            formatted_content = self._format_llm_output(
                agent_id, stage_id,
                token_info.get("selected_model", ""),
                token_info.get("selected_provider", ""),
                content,
                token_info.get("input_tokens", 0),
                token_info.get("output_tokens", 0),
                token_info.get("cached_tokens", 0),
                token_info.get("reasoning_tokens", 0),
                token_info.get("total_tokens", 0),
                token_info.get("cost_per_1k_input", 0.0),
                token_info.get("cost_per_1k_output", 0.0),
                token_info.get("cost", 0.0)
            )
            
            with open(artifact_file, 'w', encoding='utf-8') as f:
                f.write(formatted_content)
            
            artifacts.append(artifact_file)

            # Per-feature agents (design / product-design-spec): ADDITIONALLY emit
            # one file per feature F-<n> plus an index, next to the merged artifact.
            # The merged file above is the downstream contract and stays untouched.
            _pf_written = 0
            try:
                _pf_written = self._write_per_feature_files(agent_id, stage_id, content)
            except Exception as _pf_err:
                print(f"  [FEATURES] {agent_id}: per-feature write skipped ({_pf_err})")

            # Dynamic artifact-format policy (BI-0110): derive additional formats
            # (.pdf/.docx/.xlsx/.pptx/.html) from the canonical .md. Non-fatal: the
            # .md contract stays authoritative and emit() never fabricates a file.
            try:
                _extra_formats = _formats_for(getattr(self, "project", ""), agent_id,
                                              stage_id, self._PER_FEATURE_SUFFIX.get(agent_id, ""),
                                              content)
                _emit_artifact_formats(getattr(self, "project", ""), artifact_file,
                                       _extra_formats, formatted_content, agent_id=agent_id)
                if _pf_written:
                    _idx_path = os.path.join(_sp.stage_dir(self.project_dir, stage_id),
                                             "features", "index.md")
                    try:
                        with open(_idx_path, "r", encoding="utf-8") as _idx_f:
                            _idx_md = _idx_f.read()
                    except Exception:
                        _idx_md = ""
                    if _idx_md:
                        _emit_artifact_formats(
                            getattr(self, "project", ""), _idx_path,
                            _formats_for(getattr(self, "project", ""), agent_id, stage_id,
                                         "index", _idx_md),
                            _idx_md, agent_id=agent_id)
            except Exception as _fmt_err:
                print(f"  [FORMATS] {agent_id}: skipped ({_fmt_err})")

            # Layer 4: write the input cache ONLY for GOOD output (never cache
            # empty/reasoning-only or checklist-failing output).
            if _cache_on and _cache_key and _prompt_from_cache is None:
                if self._cache_output_ok(agent_id, artifact_file, content):
                    if _cache.set(_cache_key, agent_id, {"prompt": prompt}, stage_id=stage_id):
                        print(f"  [IN-CACHE] {agent_id}: wrote key={_cache_key[:8]} "
                              f"fingerprint={_fingerprint[:8]}")
                else:
                    print(f"  [IN-CACHE] {agent_id}: NOT CACHED (bad output)")
        
        # Create AgentExecution with detailed token info
        execution = AgentExecution(
            agent_id=agent_id,
            stage_id=stage_id,
            status="completed",
            started_at=datetime.now().isoformat(),
            completed_at=datetime.now().isoformat(),
            artifacts=artifacts,
            input_tokens=token_info.get("input_tokens", 0),
            output_tokens=token_info.get("output_tokens", 0),
            cached_tokens=token_info.get("cached_tokens", 0),
            reasoning_tokens=token_info.get("reasoning_tokens", 0),
            total_tokens=token_info.get("total_tokens", 0),
            selected_model=token_info.get("selected_model", ""),
            selected_provider=token_info.get("selected_provider", ""),
            model_cost_per_1k_input=token_info.get("cost_per_1k_input", 0.0),
            model_cost_per_1k_output=token_info.get("cost_per_1k_output", 0.0),
            cost=token_info.get("cost", 0.0),
            # Audit fields
            model_context_window=token_info.get("model_context_window", 0),
            prompt_chars=len(prompt),
            output_chars=len(content) if content else 0,
            artifacts_used=(getattr(self, "_last_context_fidelity", None)
                            or [{"name": k, "chars": 0}
                                for k in self._collect_stage_artifacts(stage_id)]),
            chunking_used=token_info.get("chunking_used", False),
            chunks_count=token_info.get("chunks_count", 1),
            cache_hit=token_info.get("cache_hit", False),
            finish_reason=token_info.get("finish_reason", ""),
            truncated=token_info.get("truncated", False),
            retries=token_info.get("retries", 0),
            compaction_used=getattr(self, "_last_compaction_saved", 0) > 0,
            compaction_saved_chars=getattr(self, "_last_compaction_saved", 0),
            continuations=token_info.get("continuations", 0),
        )

        # Close the per-agent log line (outcome + artifact/token summary).
        try:
            if getattr(self, "_agent_log_path", ""):
                from core import log_router as _lr
                _lr.log_event(self._agent_log_path, stage=stage_id, agent=agent_id,
                              event="agent_complete",
                              message=(f"status={execution.status} artifacts={len(artifacts)} "
                                       f"tokens={execution.total_tokens} cost={execution.cost} "
                                       f"model={execution.selected_model}"),
                              level="INFO" if execution.status == "completed" else "ERROR")
        except Exception:
            pass
        
        # A code-producing agent that used the tool loop but wrote no files is a
        # failure (prevents "passed" runs with no real output).
        if (token_info.get("tool_writes") is not None and
                (agent_id.startswith("implement") or agent_id in ("devops", "package", "fix")) and
                token_info.get("tool_writes", 0) == 0):
            execution.status = "failed"
            execution.error = "No files written by the tool loop"

        # Per-agent brief summary at AGENT COMPLETION (not gated behind approvals).
        # Rolls into the final report.
        try:
            from core import agent_summaries as _asum
            _body = ""
            try:
                if artifact_file and os.path.exists(artifact_file):
                    _body = open(artifact_file, encoding="utf-8", errors="ignore").read()
                elif content:
                    _body = content
            except Exception:
                _body = content or ""
            if _body:
                _asum.write_summary(self.project_dir, stage_id, agent_id, _body,
                                    status=execution.status)
        except Exception:
            pass

        return artifacts, execution
    
    # ── dynamic generation strategy (single vs sectioned) ─────────────────────
    def _generation_state_file(self) -> str:
        return os.path.join(self.project_dir, "generation-state.json")

    def _read_gen_state(self) -> Dict:
        try:
            p = self._generation_state_file()
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f) or {}
        except Exception:
            pass
        return {}

    def _is_marked_sectioned(self, agent_id: str) -> bool:
        return self._read_gen_state().get(agent_id) == "sectioned"

    def _mark_sectioned(self, agent_id: str):
        try:
            st = self._read_gen_state()
            st[agent_id] = "sectioned"
            with open(self._generation_state_file(), "w", encoding="utf-8") as f:
                json.dump(st, f, indent=2)
        except Exception:
            pass

    _SECTION_LABELS = {
        "architecture_style": "Architecture Style", "tech_stack": "Tech Stack",
        "components": "Components", "file_structure": "File Structure",
        "data_model": "Data / Database (Entities)", "deployment": "Deployment / Infrastructure",
        "integration": "Integration Points", "security": "Security Considerations",
        "adrs": "ADRs (Architecture Decision Records)",
        "functional_requirements": "Functional Requirements",
        "non_functional_requirements": "Non-Functional Requirements",
        "user_stories": "User Stories", "api_contracts": "API Contracts",
        "design_direction": "Design Direction", "data_models": "Data Models",
        "vision": "Vision", "features": "Features", "success_criteria": "Success Criteria",
        "target_users": "Target Users / Personas", "workflow": "E2E Workflow / User Journey",
        "risks": "Risk Assessment",
    }

    def _section_label(self, key: str) -> str:
        return self._SECTION_LABELS.get(key, key.replace("_", " ").title())

    def _assemble_section(self, label: str, text: str) -> str:
        t = (text or "").strip()
        if not t:
            return ""
        first = t.splitlines()[0].strip() if t.splitlines() else ""
        if first.startswith("#"):
            return t
        return f"## {label}\n{t}"

    def _section_digest(self, text: str, limit: int = 1200) -> str:
        import re as _re
        keep = []
        for line in (text or "").splitlines():
            s = line.strip()
            if s.startswith("#") or _re.search(r"\b(F-|FR-|NFR-|US-|ADR-)\d+", s):
                keep.append(s)
        return "\n".join(keep)[:limit]

    def _build_section_pack(self, agent_id: str, task: str, contract: dict) -> str:
        """Compact shared context for section calls (avoids N x full-base-prompt cost)."""
        spec = getattr(self, "agent_specs", {}).get(agent_id)
        instr = (getattr(spec, "instructions", "") or "").strip() or f"You are the {agent_id} agent."
        pack = instr + f"\n\nTASK: {task}"
        try:
            pack += self._scope_guard()
        except Exception:
            pass
        try:
            pack += self._output_requirements(agent_id)
        except Exception:
            pass
        # Per-feature agents: inject the deterministic global id allocation so
        # every section call sees which ids belong to which feature.
        try:
            from core.agent_requirements import (per_feature_agents as _pfa,
                                                 feature_outline as _fo,
                                                 id_allocation as _ia,
                                                 format_allocation_table as _fat)
            if agent_id in _pfa():
                _outline = _fo(getattr(self, "products_dir", "products"),
                               getattr(self, "project", ""))
                _alloc = _ia(_outline)
                if _alloc:
                    pack += _fat(_alloc)
        except Exception:
            pass
        # Condensed upstream context (not full artifacts).
        digest = ""
        try:
            prev = self._collect_stage_artifacts("\x00")  # non-matching stage -> all prior
            for k, path in list(prev.items())[:8]:
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        digest += f"\n- {k}: " + self.summarizer.summarize(f.read(), max_chars=400)
                except Exception:
                    pass
        except Exception:
            pass
        if digest:
            pack += "\n\nUPSTREAM CONTEXT (condensed):\n" + digest
        return pack

    def _normalize_merged(self, agent_id: str, text: str) -> str:
        """Deterministic cleanup: collapse blank lines, drop repeated headings, ensure title."""
        out, prev_head, blank = [], None, False
        for ln in (text or "").splitlines():
            s = ln.rstrip()
            if s == "":
                if not blank:
                    out.append("")
                blank = True
                continue
            blank = False
            if s.startswith("#"):
                if prev_head == s:
                    continue
                prev_head = s
            out.append(s)
        t = "\n".join(out).strip()
        if t and not t.startswith("#"):
            t = f"# {agent_id} output\n\n{t}"
        return t

    _PER_FEATURE_KIND = {
        "design": ("FUNCTIONAL spec (what it must do): Requirements (FR/NFR/US ids), Behaviour, "
                   "Business rules, Validation, Edge cases, Error handling, Acceptance criteria, "
                   "API behaviour, Priority"),
        "product-design-spec": ("DESIGN spec (how): Screens, Components, States "
                                "(empty/loading/error/success), Flows, ```mermaid diagrams "
                                "(stateDiagram-v2/sequenceDiagram/erDiagram/flowchart), API contracts, "
                                "Data model, per-feature NFRs, Test plan, Definition of Done"),
    }

    # Stage artifact suffix per per-feature agent (design = functional spec,
    # product-design-spec = design spec).
    _PER_FEATURE_SUFFIX = {
        "design": "functional",
        "product-design-spec": "design",
    }

    def _feature_id(self, label: str) -> str:
        m = re.search(r"F-\d+", label or "")
        return m.group(0) if m else ""

    def _store_per_feature_sections(self, agent_id: str, blocks) -> None:
        try:
            store = getattr(self, "_per_feature_sections", None)
            if store is None:
                store = {}
                self._per_feature_sections = store
            store[agent_id] = list(blocks)
        except Exception:
            pass

    def _split_per_feature_sections(self, agent_id: str, content: str) -> List[Tuple[str, str]]:
        """Prefer the sectioned generator's per-feature blocks; else parse the merged text."""
        store = getattr(self, "_per_feature_sections", None) or {}
        stashed = store.get(agent_id)
        if stashed:
            out = []
            for label, block in stashed:
                fid = self._feature_id(label)
                if fid and (block or "").strip():
                    out.append((fid, block))
            if out:
                return out
        return self._parse_per_feature_sections(content)

    def _parse_per_feature_sections(self, content: str) -> List[Tuple[str, str]]:
        """Deterministic split of merged text on top-level F-<n> headings.

        A feature block spans from its heading to the next heading of the SAME
        or higher level (so ### subsections stay inside the feature, while the
        trailing global ## sections are not absorbed into the last feature).
        """
        lines = (content or "").splitlines()
        heads: List[Tuple[int, int, str]] = []
        for i, ln in enumerate(lines):
            m = re.match(r"^[ \t]{0,3}(#{1,3})[ \t]*(F-\d+)\b", ln)
            if m:
                heads.append((i, len(m.group(1)), m.group(2)))
        out: List[Tuple[str, str]] = []
        for start, level, fid in heads:
            end = len(lines)
            for j in range(start + 1, len(lines)):
                m2 = re.match(r"^[ \t]{0,3}(#{1,6})[ \t]+", lines[j])
                if m2 and len(m2.group(1)) <= level:
                    end = j
                    break
            block = "\n".join(lines[start:end]).rstrip()
            if block:
                out.append((fid, block))
        return out

    def _feature_summary(self, block: str, limit: int = 160) -> str:
        for ln in (block or "").splitlines():
            s = ln.strip()
            if not s or s.startswith("#") or s.startswith("```"):
                continue
            s = re.sub(r"^[-*+]\s+", "", s)
            s = re.sub(r"\s+", " ", s)
            return s[:limit].rstrip()
        return ""

    def _write_per_feature_files(self, agent_id: str, stage_id: str, content: str) -> int:
        """Emit artifacts/<stage>/features/F-<n>-<kind>.md + index.md (plus merged).

        Idempotent: stale F-<n>-<kind>.md files for features no longer present are
        removed from THIS stage's features dir. Returns the number of files written.
        """
        try:
            from core.agent_requirements import per_feature_agents
            if agent_id not in per_feature_agents():
                return 0
        except Exception:
            return 0
        suffix = self._PER_FEATURE_SUFFIX.get(agent_id)
        if not suffix:
            return 0
        raw = self._split_per_feature_sections(agent_id, content)
        if not raw:
            return 0
        seen, ordered = set(), []
        for fid, block in raw:
            if fid and fid not in seen and (block or "").strip():
                seen.add(fid)
                ordered.append((fid, block))
        if not ordered:
            return 0

        from core import stage_paths as _sp
        fdir = os.path.join(_sp.stage_dir(self.project_dir, stage_id), "features")
        os.makedirs(fdir, exist_ok=True)
        expected = set()
        for fid, block in ordered:
            fname = f"{fid}-{suffix}.md"
            expected.add(fname)
            with open(os.path.join(fdir, fname), "w", encoding="utf-8") as f:
                f.write(block.rstrip() + "\n")

        # Idempotent cleanup: drop stale files we own in this stage's features dir.
        owned = re.compile(rf"^F-\d+-{re.escape(suffix)}\.md$")
        try:
            for existing in os.listdir(fdir):
                if owned.match(existing) and existing not in expected:
                    try:
                        os.remove(os.path.join(fdir, existing))
                    except Exception:
                        pass
        except Exception:
            pass

        lines = [f"# Features — {agent_id} (stage {stage_id})", ""]
        for fid, block in ordered:
            first = (block.splitlines()[0] if block else "").strip()
            first = re.sub(r"^[ \t]{0,3}#{1,6}[ \t]*", "", first)
            m = re.match(rf"{re.escape(fid)}\s*[:\-–]\s*(.+)$", first)
            name = m.group(1).strip() if m else fid
            summary = self._feature_summary(block)
            entry = f"- [{fid}: {name}]({fid}-{suffix}.md)"
            if summary:
                entry += f" — {summary}"
            lines.append(entry)
        with open(os.path.join(fdir, "index.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines).rstrip() + "\n")

        print(f"[FEATURES] {agent_id}: wrote {len(ordered)} per-feature file(s) -> "
              f"{os.path.relpath(fdir, self.project_dir)}/")
        return len(ordered)

    def _generate_sectioned(self, agent_id, stage_id, task, contract, artifact_file, base_prompt,
                            outline=None):
        """Write one section per LLM call, then deterministically merge.

        Robust by construction: any failure falls back to a single call; the
        section list comes from config (never assumed); the architect's decision
        JSON is generated FIRST and injected into every section.

        Per-feature agents (design / product-design-spec) emit ONE CALL PER FEATURE
        (F-x read from `product-plan.json`), then the global sections. An empty
        outline falls back to a single call.
        """
        try:
            from core.agent_requirements import (required_sections, per_feature_agents,
                                                 feature_outline, id_allocation,
                                                 format_feature_range)
            spec = required_sections(agent_id) or {}
            is_pf = agent_id in per_feature_agents()
            feat_labels: List[str] = []
            if is_pf:
                if outline is None:
                    try:
                        outline = feature_outline(getattr(self, "products_dir", "products"),
                                                  getattr(self, "project", ""))
                    except Exception:
                        outline = []
                if not outline:
                    print(f"  [GENERATION] {agent_id}: no feature outline -> single call")
                    return self._call_llm(base_prompt, agent_id, stage_id)
                feat_labels = [str(x) for x in outline][:60]
                # Deterministic id allocation: feature index i owns fixed-size
                # FR/NFR/US blocks (F-1 -> FR-1..25, F-2 -> FR-26..50, ...).
                alloc = id_allocation(feat_labels)
                # Global sections = configured keys except per_feature (and functional,
                # which is covered inside each per-feature section).
                ordered = [k for k in (list((spec.get("essential") or {}).keys())
                                       + list((spec.get("recommended") or {}).keys()))
                           if k not in ("per_feature", "functional")]
                ordered = ordered[:12]
            else:
                ordered = (list((spec.get("essential") or {}).keys())
                           + list((spec.get("recommended") or {}).keys()))
                if not ordered:
                    return self._call_llm(base_prompt, agent_id, stage_id)
                ordered = ordered[:12]  # bounded, no runaway

            acc = {"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0, "reasoning_tokens": 0,
                   "total_tokens": 0, "cost": 0.0, "selected_model": "", "selected_provider": "",
                   "cost_per_1k_input": 0.0, "cost_per_1k_output": 0.0, "finish_reason": "stop",
                   "truncated": False, "retries": 0, "continuations": 0, "fallback": False,
                   "sections": 0, "sectioned": True}

            def _accumulate(ti):
                for k in ("input_tokens", "output_tokens", "cached_tokens", "reasoning_tokens",
                          "total_tokens", "cost"):
                    acc[k] = acc.get(k, 0) + (ti.get(k, 0) or 0)
                for k in ("selected_model", "selected_provider",
                          "cost_per_1k_input", "cost_per_1k_output"):
                    if ti.get(k):
                        acc[k] = ti[k]
                acc["continuations"] += ti.get("continuations", 0) or 0
                acc["retries"] += ti.get("retries", 0) or 0
                if ti.get("fallback"):
                    acc["fallback"] = True

            # Compact shared context (avoids re-sending the full base prompt per section).
            shared = self._build_section_pack(agent_id, task, contract)

            # Architect: fix the stack decision FIRST so sections cannot contradict it.
            decision_block = ""
            if agent_id == "architect":
                jtext, jti = self._call_llm(
                    shared + "\n\nOutput ONLY the single fenced ```json tech-stack decision block "
                             "(keys: kind, languages, frameworks, database, cache, deploy, runtime, "
                             "requested, changed_from_request, rationale). No prose.",
                    agent_id, stage_id)
                _accumulate(jti)
                if jtext and "```json" in jtext:
                    decision_block = jtext.strip()
            if decision_block:
                shared += ("\n\nAGREED TECH-STACK DECISION (do NOT contradict this):\n"
                           + decision_block)

            pin = {"model": ""}  # pin one model across the run for consistency

            def _call_section(key, digest, concise=False):
                label = self._section_label(key)
                sec_prompt = (shared +
                              f"\n\nIGNORE any instruction to write the full document. "
                              f"WRITE ONLY the '## {label}' section now; do not write any other section."
                              + (" Keep it concise (bullet lists)." if concise else "")
                              + (f"\n\nALREADY WRITTEN (stay consistent with these names/IDs):\n{digest}"
                                 if digest else ""))
                content, ti = self._call_llm(sec_prompt, agent_id, stage_id, pin_model=pin["model"])
                _accumulate(ti)
                if not pin["model"] and ti.get("selected_model"):
                    pin["model"] = ti["selected_model"]
                return content, ti

            def _call_feature(fid_label, digest):
                kind = self._PER_FEATURE_KIND.get(agent_id, "spec")
                _fid = self._feature_id(fid_label) or fid_label
                _range_line = format_feature_range(_fid, alloc.get(_fid) or {})
                sec_prompt = (shared +
                              (f"\n\n{_range_line}" if _range_line else "") +
                              f"\n\nIGNORE any instruction to write the full document. "
                              f"WRITE ONLY the '## {fid_label}' section now for this ONE feature — a {kind}. "
                              f"Do NOT write any other feature or section. "
                              f"Start your answer with the exact heading '## {fid_label}'."
                              + (f"\n\nALREADY WRITTEN (stay consistent with these names/IDs):\n{digest}"
                                 if digest else ""))
                content, ti = self._call_llm(sec_prompt, agent_id, stage_id, pin_model=pin["model"])
                _accumulate(ti)
                if not pin["model"] and ti.get("selected_model"):
                    pin["model"] = ti["selected_model"]
                return content, ti

            assembled, digest = [], ""
            pf_blocks: List[Tuple[str, str]] = []
            if is_pf:
                for fid in feat_labels:
                    content, ti = _call_feature(fid, digest)
                    if ti.get("truncated") and not content:
                        content, ti = _call_feature(fid, digest)
                    if ti.get("truncated"):
                        acc["truncated"] = True
                    block = self._assemble_section(fid, content)
                    if block:
                        assembled.append(block)
                        pf_blocks.append((self._feature_id(fid) or fid, block))
                        digest += "\n" + self._section_digest(block)
                        acc["sections"] += 1
                    else:
                        print(f"  [GENERATION] {agent_id}: feature '{fid}' empty")

            for key in ordered:
                content, ti = _call_section(key, digest)
                if ti.get("truncated") and not content:
                    content, ti = _call_section(key, digest, concise=True)
                if ti.get("truncated"):
                    acc["truncated"] = True
                block = self._assemble_section(self._section_label(key), content)
                if block:
                    assembled.append(block)
                    digest += "\n" + self._section_digest(block)
                    acc["sections"] += 1
                else:
                    print(f"  [GENERATION] {agent_id}: section '{key}' empty")

            if decision_block:
                assembled.append("```json\n" + decision_block.split("```json", 1)[-1].strip())

            text = self._normalize_merged(agent_id, "\n\n".join(assembled).strip())
            if is_pf and pf_blocks:
                self._store_per_feature_sections(agent_id, pf_blocks)

            # Retry any missing ESSENTIAL sections once (non per-feature agents only;
            # per-feature output is already one section per F-x).
            if not is_pf:
                try:
                    from core.output_checklist import check as _chk
                    tmp = artifact_file + ".sections.tmp"
                    with open(tmp, "w", encoding="utf-8") as f:
                        f.write(text)
                    missing = _chk(agent_id, [tmp]).get("essential_missing") or []
                    for key in missing:
                        content, ti = _call_section(key, digest, concise=True)
                        block = self._assemble_section(self._section_label(key), content)
                        if block:
                            text += "\n\n" + block
                            digest += "\n" + self._section_digest(block)
                    try:
                        os.remove(tmp)
                    except Exception:
                        pass
                except Exception:
                    pass

            if not text.strip():
                # Nothing usable -> fall back to a single call (never return empty).
                return self._call_llm(base_prompt, agent_id, stage_id)
            return text, acc
        except Exception as e:
            print(f"  [GENERATION] {agent_id}: sectioned failed ({e}); falling back to single call")
            try:
                return self._call_llm(base_prompt, agent_id, stage_id)
            except Exception as e2:
                return None, {"fallback": True, "selected_model": "", "error": str(e2)}

    def _build_agent_prompt(self, agent_id: str, stage_id: str, task: str, contract: dict, artifact_file: str) -> str:
        """Build a prompt for the agent with smart context management.
        
        Context management strategy:
        1. Filter artifacts by contract.allowed_inputs
        2. Summarize older artifacts (extract headers + first bullet)
        3. Cap total context at min(contract.max_input_tokens, model.context_window * 0.8)
        4. Always include full instructions and task (never truncate)
        """
        saved_chars = 0  # chars removed by compaction (vs full artifact)
        # Get model config to know context_window
        tier_config = self._get_agent_model_config(agent_id, stage_id)
        model_name = tier_config["model"]
        
        # Get model profile for context_window
        model_profile = self.model_registry.get_model(model_name)
        model_context_window = model_profile.context_window if model_profile else 1000000
        
        # Calculate max context tokens (80% of model's context window, or contract limit)
        max_context_tokens = min(
            contract.get("max_input_tokens", 100000),
            int(model_context_window * 0.8)
        )
        max_context_chars = max_context_tokens * 4  # rough estimate: 1 token ≈ 4 chars
        
        # Get allowed inputs from contract (semantic) and map to PRODUCER agents so
        # artifact selection is correct (artifacts are keyed <stage>_<agent>).
        allowed_inputs = contract.get("allowed_inputs", [])
        allowed_producers = set()
        if allowed_inputs:
            try:
                from core.orchestrator.artifacts_map import allowed_producer_agents
                allowed_producers = allowed_producer_agents(allowed_inputs,
                                                            getattr(self, "agent_specs", {}))
            except Exception:
                allowed_producers = set()

        # Collect and filter artifacts
        prev_artifacts = self._collect_stage_artifacts(stage_id)
        filtered_artifacts = {}
        for key, path in prev_artifacts.items():
            producer = os.path.basename(path).replace("-output.md", "")
            if allowed_inputs and allowed_producers and producer not in allowed_producers:
                continue
            filtered_artifacts[key] = path
        
        # Build context with compact summaries — NEVER a blind truncation, and driven
        # by a DECLARED per-agent policy (full_stages + recent_full). Fidelity (what was
        # actually passed) and gaps (declared-FULL inputs missing/summarised) are recorded.
        context_parts = []
        total_chars = 0
        artifact_count = len(filtered_artifacts)
        fidelity = []
        gaps = []
        try:
            from core import context_policy as _cp
        except Exception:
            _cp = None

        for i, (key, path) in enumerate(filtered_artifacts.items()):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()

                if _cp is not None:
                    mode = _cp.decide(agent_id, key, i, artifact_count,
                                      getattr(self, "project", ""))
                else:
                    mode = "full" if i >= (artifact_count - 3) else "summary"

                if mode == "full":
                    artifact_text = content
                else:
                    _budget = _cp.ambient_budget(agent_id, getattr(self, "project", "")) if _cp else 2000
                    artifact_text = self.summarizer.summarize(content, max_chars=_budget)
                    saved_chars += max(0, len(content) - len(artifact_text))

                entry = f"\n\n--- {key} ---\n{artifact_text}"
                context_parts.append(entry)
                total_chars += len(entry)
                fidelity.append({"name": key, "mode": mode, "chars": len(artifact_text)})
                if mode == "full" and len(artifact_text) < len(content):
                    gaps.append(key)   # declared FULL but content was reduced
            except Exception:
                pass

        self._last_context_fidelity = fidelity
        self._last_context_gaps = gaps
        if gaps:
            print(f"  [CONTEXT-GAP] {agent_id}: declared-FULL input(s) reduced/missing: {gaps}")

        context = "".join(context_parts) if context_parts else ""
        
        # Build the instruction part (always full, never truncated)
        instruction_templates = {
            "ideation": """You are the Ideation Agent for Product Forge.

TASK: {task}

REQUIREMENTS:
- Analyze the idea and extract key requirements
- Identify target users and their needs
- Define success criteria
- List features with priorities (must-have vs nice-to-have)

OUTPUT FORMAT:
Write a comprehensive ideation document using EXACTLY these markdown headings:
# Vision
# Target Users / Personas
# E2E Workflow / User Journey
# Features
# Success Criteria
# Risk Assessment

Under # Features, list each feature as a bullet with an id (F-1, F-2, ...) and a must-have/nice-to-have priority.""",
            "design": """You are the Design Agent for Product Forge.

TASK: {task}

REQUIREMENTS:
- Create detailed requirements document
- Design system architecture
- Define data models and API contracts
- Create UI/UX wireframes description

OUTPUT FORMAT:
Write a comprehensive design document using EXACTLY these markdown headings:
## Functional Requirements
(list each as FR-1, FR-2, ...)
## Non-Functional Requirements
(list each as NFR-1, NFR-2, ...)
## User Stories
(list each as US-1: As a ... I want ... so that ...)
## Design Direction
## Components
## Data Models
## API Contracts""",
            "architect": """You are the Architect Agent for Product Forge.

TASK: {task}

REQUIREMENTS:
- Design technical architecture
- Define component boundaries
- Create file structure
- Specify technology stack

OUTPUT FORMAT:
Write a comprehensive architecture document using EXACTLY these markdown headings:
## Architecture Style
(microservices / modular monolith / event-driven / serverless, plus rationale)
## Tech Stack
## Components
## File Structure
## Data / Database (Entities)
## Deployment / Infrastructure
## Integration Points
## Security Considerations
## ADRs
(list each decision as ADR-1, ADR-2, ...)""",
            "implement": """You are the Implement Agent for Product Forge.

TASK: {task}

REQUIREMENTS:
- Write actual code files
- Follow the architecture from previous stages
- Include error handling
- Add comments where necessary

OUTPUT FORMAT:
Write the implementation with:
1. Complete code files
2. File structure as specified in architecture
3. Proper error handling
4. Configuration files"""
        }
        
        # Instruction source: AgentSpec (preferred, framework-agnostic) or template fallback
        spec = getattr(self, "agent_specs", {}).get(agent_id)
        if spec and getattr(spec, "instructions", ""):
            directive = self._tool_directive(agent_id, stage_id, task)
            if directive and (agent_id.startswith("implement") or agent_id in ("devops", "fix")):
                # Tool-first code agents: use the directive + requirements, NOT the
                # opencode card (which references a 'Task' tool / sub-agents and
                # derails the model into exploring instead of writing).
                instruction = (directive + f"\n\nYou are the {agent_id} agent.\n"
                               + self._output_requirements(agent_id) + f"\n\nTASK: {task}")
            else:
                instruction = ((directive + "\n\n") if directive else "") + \
                    spec.instructions + f"\n\nTASK: {task}"
                instruction += self._output_requirements(agent_id)
        else:
            template = instruction_templates.get(agent_id, """You are agent {agent_id} for Product Forge.

TASK: {task}

Execute this task and produce the required output.""")
            instruction = template.format(task=task, agent_id=agent_id)

        instruction += self._scope_guard()
        try:
            from core.orchestrator.prompt_builder import (conciseness_guard, infra_awareness_guard,
                                                           research_guard)
            instruction += conciseness_guard(agent_id)
            instruction += infra_awareness_guard(agent_id)
            instruction += research_guard(agent_id)
        except Exception:
            pass
        try:
            instruction += self._test_generation_directive(agent_id)
        except Exception:
            pass
        try:
            instruction += self._techstack_guidelines_directive(agent_id)
        except Exception:
            pass
        try:
            instruction += self._business_skills_directive(agent_id)
        except Exception:
            pass
        try:
            instruction += self._service_catalog_directive(agent_id)
        except Exception:
            pass
        try:
            instruction += self._code_analyzer_directive(agent_id)
        except Exception:
            pass
        if not (spec and getattr(spec, "tools", None)):
            instruction += ("\n\nIMPORTANT: You have NO tools available. Do NOT output tool calls "
                            "or JSON such as {\"tool\": ...}. Write the full document text directly.")
        
        # Runtime agent overlay: append owner-added instructions for ANY agent without
        # editing code/cards. Changing it changes the prompt -> prompt-cache key, so no
        # stale cache hits.
        try:
            from core import prompt_overlays as _po
            _ov = _po.for_agent(self.project_dir, agent_id)
            if _ov:
                instruction += "\n\nADDITIONAL INSTRUCTIONS (owner overlay):\n" + _ov
        except Exception:
            pass

        # Incremental/AMEND mode: when enabled and this agent already produced its
        # artifact, include it and instruct an INCREMENTAL update (not a rebuild).
        try:
            _amend = getattr(self, "amend_mode", False) or \
                str(os.getenv("PIPELINE_AMEND", "0")).lower() in ("1", "true", "yes")
            if _amend and artifact_file and os.path.exists(artifact_file):
                _prev = open(artifact_file, encoding="utf-8", errors="ignore").read()
                instruction += (
                    "\n\nAMEND MODE (INCREMENTAL CHANGE): You are UPDATING an existing artifact, "
                    "NOT rebuilding. Preserve its structure and every still-valid part; apply ONLY "
                    "the changes implied by the task/new requirements; keep existing ids stable "
                    "(add new ids, do not renumber). Output the FULL updated artifact.\n\n"
                    "EXISTING OUTPUT (amend this):\n" + _prev)
        except Exception:
            pass

        # Preflight (BI-0165): instructions + context vs the model window. Soft by design —
        # logs (hard-fail only if instructions alone exceed the window). No truncation here;
        # the LLM client map-reduce still handles overflow without loss.
        try:
            from core import context_preflight as _cpf
            _v = _cpf.check(len(instruction), len(context), model_context_window,
                            contract.get("max_input_tokens", 0))
            _cpf.log_verdict(agent_id, _v)
        except Exception:
            pass

        # Assemble final prompt: instructions + context + knowledge
        prompt = f"""{instruction}

CONTEXT FROM PREVIOUS STAGES:
{context if context else "No previous context (first stage)"}

Write the output to: {artifact_file}"""
        
        # Inject knowledge from knowledge base based on agent type and techstack
        try:
            knowledge_content = self._load_knowledge_for_agent(agent_id, stage_id, contract)
            if knowledge_content:
                prompt = f"""{instruction}

RELEVANT GUIDELINES AND KNOWLEDGE:
{knowledge_content}

CONTEXT FROM PREVIOUS STAGES:
{context if context else "No previous context (first stage)"}

Write the output to: {artifact_file}"""
        except Exception as e:
            print(f"[KnowledgeInjection] Error loading knowledge: {e}")

        # Defect/RCCA brief: hand open defects + prevention to the fix (and related) agents.
        try:
            if agent_id in ("fix", "implement", "code-review", "validate"):
                from core.defect_loop import defect_brief
                brief = defect_brief(getattr(self, "project", ""),
                                     getattr(self, "project_dir", ""))
                if brief:
                    prompt += "\n\n" + brief
        except Exception as e:
            print(f"[DefectBrief] {e}")

        self._last_compaction_saved = saved_chars
        return prompt

    def _tool_directive(self, agent_id: str, stage_id: str, task: str) -> str:
        """Delegates to core/orchestrator/prompt_builder (1A.11)."""
        from core.orchestrator.prompt_builder import tool_directive
        return tool_directive(agent_id, stage_id, task,
                              getattr(self, "enable_tools", False), self.project)

    def _scope_guard(self) -> str:
        """Delegates to core/orchestrator/prompt_builder (1A.11)."""
        from core.orchestrator.prompt_builder import scope_guard
        return scope_guard(getattr(self, "tech_stack", {}),
                           getattr(self, "requested_tech_stack", []))

    def _output_requirements(self, agent_id: str) -> str:
        """Delegates to core/orchestrator/prompt_builder (1A.11)."""
        from core.orchestrator.prompt_builder import output_requirements
        return output_requirements(agent_id, getattr(self, "requested_tech_stack", []))

    def _techstack_guidelines_directive(self, agent_id: str) -> str:
        """Inject stack-specific guidance for code agents (resolver-controlled)."""
        if not (agent_id.startswith("implement") or agent_id in ("code-review", "fix", "devops")):
            return ""
        try:
            from core.feature_flags import enabled
            if not enabled("techstack_guidelines", getattr(self, "project_dir", None)):
                return ""
            ts = getattr(self, "tech_stack", {}) or {}
            chosen = ts.get("chosen") or {}
            keys = [str(x) for x in (chosen.get("frameworks") or []) + (chosen.get("languages") or [])]
            if not keys:
                return ""
            from core.techstack_guidelines import TechStackGuidelinesGenerator
            g = TechStackGuidelinesGenerator().get_guidelines(keys[0])
            md = (g.to_markdown() if (g and hasattr(g, "to_markdown")) else "") or ""
            return (f"\n\n## TECH-STACK GUIDELINES ({keys[0]})\n" + md[:2000]) if md else ""
        except Exception:
            return ""

    def _business_skills_directive(self, agent_id: str) -> str:
        """Opt-in: business/domain-based skill recommendations (resolver-controlled)."""
        try:
            from core.feature_flags import enabled
            if not enabled("business_skills", getattr(self, "project_dir", None)):
                return ""
            from core.business_skills_selector import BusinessSkillsSelector
            ts = getattr(self, "tech_stack", {}) or {}
            chosen = ts.get("chosen") or {}
            res = BusinessSkillsSelector(products_dir=getattr(self, "products_dir", "products")).select_for_project(
                self.project, domain=(chosen.get("domain") or None),
                techstack=[str(x) for x in (chosen.get("frameworks") or []) + (chosen.get("languages") or [])])
            d = res.to_dict() if hasattr(res, "to_dict") else {}
            skills = d.get("skills") or d.get("recommendations") or []
            if not skills:
                return ""
            lines = ["", "## RECOMMENDED SKILLS (business/domain)"]
            for s in skills[:10]:
                lines.append("- " + (s.get("name", str(s)) if isinstance(s, dict) else str(s)))
            return "\n".join(lines)
        except Exception:
            return ""

    def _service_catalog_directive(self, agent_id: str) -> str:
        """Opt-in: required-service catalog for discovery/architect."""
        if agent_id not in ("discovery", "architect"):
            return ""
        try:
            from core.feature_flags import enabled
            if not enabled("service_catalog", getattr(self, "project_dir", None)):
                return ""
            from core.service_catalog import get_all_required_services
            cats = get_all_required_services() or []
            lines = ["", "## SERVICE CATALOG (confirm required services + their config)"]
            for c in cats[:30]:
                lines.append("- " + str(getattr(c, "name", None) or getattr(c, "key", None) or c))
            lines.append("Record chosen services + ports/env/secrets in docs/infra.json.")
            return "\n".join(lines)
        except Exception:
            return ""

    def _code_analyzer_directive(self, agent_id: str) -> str:
        """Opt-in: heuristic change-plan for the fix agent."""
        if agent_id != "fix":
            return ""
        try:
            from core.feature_flags import enabled
            if not enabled("code_analyzer", getattr(self, "project_dir", None)):
                return ""
            import json as _json
            from core.code_analyzer import CodeAnalyzer
            from core.defect_loop import defect_brief
            content = defect_brief(self.project, getattr(self, "project_dir", "")) or ""
            if not content.strip():
                return ""
            plan = CodeAnalyzer().analyze_improvement(content, [], [])
            d = plan.to_dict() if hasattr(plan, "to_dict") else {"plan": str(plan)}
            return "\n\n## CHANGE PLAN (code_analyzer)\n" + _json.dumps(d, default=str)[:1500]
        except Exception:
            return ""

    def _test_generation_directive(self, agent_id: str) -> str:
        """Full test catalogue (from the QA matrix) for implement/validate + scaffolds."""
        if agent_id not in ("implement", "validate"):
            return ""
        try:
            import glob
            project_dir = getattr(self, "project_dir", "")
            feats: List[Dict] = []
            try:
                feats = list(self.phasing.extract_features())
            except Exception:
                feats = []
            nfr_ids: List[str] = []
            try:
                from core.test_matrix import spec_ids
                nfr_ids = spec_ids(project_dir).get("nfr", [])
            except Exception:
                nfr_ids = []
            block = ""
            try:
                from core.test_matrix import directive as matrix_directive
                block = matrix_directive(features=feats, nfr_ids=nfr_ids,
                                         tech_stack=getattr(self, "tech_stack", {}))
            except Exception:
                block = ""
            if not block:
                block = ("\n\n## TEST GENERATION REQUIREMENTS\n"
                         "- Write REAL executable tests (no empty `pass`/`skip`); tag each with "
                         "its requirement id (`test_fr_1_...`, `# NFR-2`).")
            scaffolds = glob.glob(os.path.join(project_dir, "tests", "generated", "*.py"))
            extra = []
            if scaffolds:
                extra.append(f"- Scaffolds exist in `tests/generated/` ({len(scaffolds)} file(s)); "
                             "replace their `pytest.skip(...)` bodies with real assertions.")
            extra.append("- Tests cannot run without a build; devops produces the build "
                         "(version + build number) before validate executes.")
            return block + "\n" + "\n".join(extra)
        except Exception:
            return ""

    def get_tools_for_agent(self, agent_id: str) -> List[Dict]:
        """Return framework-agnostic tool schemas allowed for an agent (from its spec)."""
        if not self.tool_registry:
            return []
        spec = getattr(self, "agent_specs", {}).get(agent_id)
        if not spec or not getattr(spec, "tools", None):
            return []
        return self.tool_registry.schemas(spec.tools)

    def execute_agent_tool(self, agent_id: str, tool: str, args: Dict) -> Dict:
        """Execute a tool on behalf of an agent, sandboxed to the project workspace.

        Read-only tool results are cached (ToolResultCache); a successful write
        invalidates the cache so later reads see fresh content.
        """
        if not self.tool_registry:
            return {"ok": False, "error": "tool registry unavailable"}
        spec = getattr(self, "agent_specs", {}).get(agent_id)
        if spec is not None and tool not in (getattr(spec, "tools", None) or []):
            return {"ok": False, "error": f"tool '{tool}' not permitted for {agent_id}"}
        cache = getattr(self, "tool_cache", None)
        if cache is not None:
            cached = cache.get(tool, args)
            if cached is not None:
                return cached
        res = self.tool_registry.execute(tool, args, self.project_dir)
        result = self._compress_tool_result(tool, res.to_dict())
        if cache is not None:
            if tool in ("write_file", "delete_file", "move_file"):
                cache.invalidate()
            else:
                cache.set(tool, args, result)
        return result

    def _compress_tool_result(self, tool: str, result: Dict) -> Dict:
        """Compress long text fields in a tool result (token saver, 4.9).

        Only truncates oversized string payloads; dict/list structure and keys
        are preserved so the agent still sees real data.
        """
        if not isinstance(result, dict):
            return result
        try:
            from core.phase3_advanced import ToolResultCompressor
            comp = getattr(self, "_tool_compressor", None)
            if comp is None:
                comp = ToolResultCompressor()
                self._tool_compressor = comp
            out = dict(result)
            for k in ("content", "output", "stdout", "stderr", "text"):
                v = out.get(k)
                if isinstance(v, str) and len(v) > 8000:
                    out[k] = comp.compress_text(v, max_length=8000)
            return out
        except Exception:
            return result

    def _load_knowledge_for_agent(self, agent_id: str, stage_id: str, contract: dict) -> str:
        """Load relevant knowledge from knowledge base for an agent."""
        # Map agent types to relevant knowledge layers
        agent_knowledge_map = {
            "ideation": ["business_logic"],
            "design": ["api", "frontend", "backend"],
            "architect": ["api", "database", "backend", "architecture"],
            "implement": ["api", "database", "frontend", "backend", "caching", "packaging"],
            "code-review": ["api", "database", "frontend", "backend", "security"],
            "validate": ["testing"],
            "security": ["security"],
            "document": ["packaging"],
        }
        
        # Layers from the SSOT: config/agent-capabilities.json 'knowledge' + the agent card's
        # knowledge_layers. Fall back to the legacy hardcoded map only if neither declares any.
        layers = []
        try:
            import json as _json
            _repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            _caps = _json.load(open(os.path.join(_repo, "config", "agent-capabilities.json"),
                                    encoding="utf-8")).get("agents", {})
            layers += [str(x) for x in (_caps.get(agent_id, {}) or {}).get("knowledge", [])]
        except Exception:
            pass
        try:
            _spec = (getattr(self, "agent_specs", {}) or {}).get(agent_id)
            layers += [str(x) for x in (getattr(_spec, "knowledge_layers", None) or [])]
        except Exception:
            pass
        if not layers:
            layers = list(agent_knowledge_map.get(agent_id, []))
        # Alias capability-knowledge names to actual docs/guidelines layer dirs.
        _ALIAS = {"tech": ["api", "backend", "architecture"],
                  "finance": ["unit-economics", "revenue-models"],
                  "analytics": ["metrics"], "content": ["ui-ux"],
                  "business": ["business", "business-models"],
                  "legal": ["compliance-legal"], "design": ["ui-ux", "rendering"],
                  "domain": ["domain"], "business_logic": ["business", "business-models"]}
        _expanded = []
        for _l in layers:
            _expanded += _ALIAS.get(_l, [_l])
        layers = _expanded

        # Preferred: knowledge derived from the ARCHITECT's agreed tech stack
        # (docs/tech-stack.json). This makes knowledge follow the decision.
        ts = getattr(self, "tech_stack", {}) or {}
        chosen = ts.get("chosen") or {}
        if chosen:
            layers = stack_to_layers(chosen)
            if agent_id.startswith("implement") or agent_id in ("validate", "code-review", "fix"):
                layers.append("testing")
            if agent_id == "security":
                layers.append("security")
            if agent_id == "ideation" and not layers:
                layers = ["business_logic"]
            seen, dedup = set(), []
            for l in layers:
                if l not in seen:
                    seen.add(l)
                    dedup.append(l)
            layers = dedup
        else:
            # Pre-architect: use the requested stack (if any) instead of a fixed map.
            hints = [str(h).lower() for h in
                     (getattr(self, "requested_tech_stack", []) or getattr(self, "tech_stack_hints", []) or [])]
            web_markers = {"fastapi", "flask", "django", "express", "nestjs", "rails",
                           "spring", "dotnet", "asp.net", "laravel", "php", "react",
                           "nextjs", "next.js", "vue", "angular", "svelte", "node",
                           "web", "http", "rest", "graphql", "postgres", "postgresql",
                           "mysql", "mongodb", "redis", "supabase"}
            is_web = any(any(m in h for m in web_markers) for h in hints) or not hints
            if not is_web:
                layers = [l for l in layers if l not in ("api", "frontend", "database", "caching", "backend")]
                coding = []
                if any("python" in h for h in hints):
                    coding.append("python")
                if any(("typescript" in h or "javascript" in h or "node" in h) for h in hints):
                    coding.append("typescript")
                if any("go" in h for h in hints):
                    coding.append("go")
                if agent_id.startswith("implement") or agent_id in ("code-review", "fix"):
                    coding = coding + ["testing"]
                layers = coding + [l for l in layers if l not in coding]
                if not layers:
                    layers = ["business_logic"]

        # Optional knowledge-graph augmentation (4.9, opt-in ENABLE_KNOWLEDGE_GRAPH)
        kg = getattr(self, "knowledge_graph", None)
        if kg and layers:
            try:
                for l in list(layers):
                    kg.add_node(l, l, l)
                for l in list(layers):
                    for rel in kg.cross_domain_search(l)[:3]:
                        d = rel.get("domain")
                        if d and d not in layers:
                            layers.append(d)
            except Exception:
                pass

        # Registry-defined knowledge/skill layers — add/modify/view at runtime via
        # core/knowledge_registry (no code change). Merged in for this agent.
        try:
            from core import knowledge_registry as _kr
            for _l in _kr.resolve_layers(agent_id):
                if _l not in layers:
                    layers.append(_l)
        except Exception:
            pass

        # Load guidelines for these layers
        knowledge = ""
        if layers:
            knowledge = self.guideline_loader.load_guidelines_for_layers(layers, max_tokens=3000)

        # On-demand research notes feed design/architect (if present)
        if agent_id in ("design", "architect", "product-design-spec"):
            try:
                import glob as _glob
                notes = []
                rp = os.path.join(self.project_dir, "docs", "research-notes.md")
                if os.path.exists(rp):
                    notes.append(rp)
                notes += sorted(_glob.glob(os.path.join(self.project_dir, "docs", "research", "*.md")))
                text = ""
                for npth in notes:
                    try:
                        with open(npth, "r", encoding="utf-8", errors="ignore") as f:
                            text += f.read()[:2000] + "\n"
                    except Exception:
                        pass
                if text.strip():
                    knowledge = (knowledge + "\n\nRESEARCH NOTES (on-demand):\n" + text) if knowledge else text
            except Exception:
                pass
        return knowledge
    

    
    def _format_llm_output(self, agent_id: str, stage_id: str, model_name: str, provider: str, content: str,
                           input_tokens: int = 0, output_tokens: int = 0, cached_tokens: int = 0,
                           reasoning_tokens: int = 0, total_tokens: int = 0,
                           model_cost_per_1k_input: float = 0.0, model_cost_per_1k_output: float = 0.0,
                           cost: float = 0.0) -> str:
        """Format LLM output with metadata and token usage."""
        return f"""# {agent_id.upper()} Output - Stage {stage_id}

**Task:** Generated by LLM
**Agent:** {agent_id}
**Stage:** {stage_id}
**Timestamp:** {datetime.now().isoformat()}
**Model:** {model_name}
**Provider:** {provider}

## Token Usage
- **Input Tokens:** {input_tokens}
- **Output Tokens:** {output_tokens}
- **Cached Tokens:** {cached_tokens}
- **Reasoning Tokens:** {reasoning_tokens}
- **Total Tokens:** {total_tokens}
- **Cost:** ${cost:.6f}
- **Cost per 1K input:** ${model_cost_per_1k_input}
- **Cost per 1K output:** ${model_cost_per_1k_output}

## Output

{content}

---
*Generated by PipelineExecutor via {provider} API*
"""
    
    def _cheapest_opencode_go_model(self):
        """Delegates to core/orchestrator/model_router (1A.11)."""
        return self.model_router.cheapest_opencode_go_model()

    def _get_parent_stage_id(self, stage_id: str) -> Optional[str]:
        """Delegates to core/orchestrator/model_router (1A.11)."""
        return self.model_router.parent_stage_id(stage_id)

    def _get_agent_model_config(self, agent_id: str, stage_id: str) -> dict:
        """Delegates to core/orchestrator/model_router (1A.11), then applies any
        model-capability-fit substitution chosen by the preflight (BI-0076)."""
        cfg = self.model_router.get_agent_model_config(
            agent_id, stage_id, force_cheap=getattr(self, "_force_cheap", False))
        ov = getattr(self, "_model_fit_overrides", None) or {}
        chosen = ov.get(agent_id)
        if chosen and chosen.get("model"):
            cfg = dict(cfg)
            cfg["model"] = chosen["model"]
            if chosen.get("provider"):
                cfg["provider"] = chosen["provider"]
            if chosen.get("api_endpoint"):
                cfg["api_endpoint"] = chosen["api_endpoint"]
        return cfg
    
    
    def _collect_stage_artifacts(self, stage_id: str) -> Dict[str, Any]:
        """Collect artifacts from previous stages for context building."""
        artifacts = {}
        if self.execution and self.execution.stage_executions:
            # Snapshot to avoid "dict changed size during iteration" when stages
            # execute concurrently.
            with self._state_lock:
                snapshot = list(self.execution.stage_executions.items())
            for prev_stage, executions in snapshot:
                if prev_stage == stage_id:
                    continue
                for ex in executions:
                    if ex.status == "completed" and ex.artifacts:
                        for artifact_path in ex.artifacts:
                            artifact_name = os.path.basename(artifact_path).replace("-output.md", "")
                            artifacts[f"{prev_stage}_{artifact_name}"] = artifact_path
        # Feed the refined (crisp) idea brief to downstream agents (BI-0039): the
        # synthesis from the 360 discovery panel, so Design/Architect/Implement
        # consume the clarified goal, not just the raw idea.
        try:
            refined = os.path.join(getattr(self, "project_dir", ""), "docs", "idea-refined.md")
            if os.path.exists(refined):
                artifacts.setdefault("0_idea_refined", refined)
        except Exception:
            pass
        return artifacts

    def _call_llm(self, prompt: str, agent_id: str, stage_id: str, pin_model: str = ""):
        try:
            return self.llm._call_llm(prompt, agent_id, stage_id, pin_model=pin_model)
        except TypeError:
            return self.llm._call_llm(prompt, agent_id, stage_id)

    def _chat_with_tools(self, messages, agent_id, stage_id, tools):
        return self.llm._chat_with_tools(messages, agent_id, stage_id, tools)

    def _generate_template_output(self, agent_id, stage_id, prompt):
        return self.llm._generate_template_output(agent_id, stage_id, prompt)
