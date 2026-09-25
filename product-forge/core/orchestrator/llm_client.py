"""
LLM Client (extracted from pipeline_executor - 1A.11).

Encapsulates all provider calls: api key/headers/request building, response
extraction, token/cost accounting, single/chunked calls, messages, native
tool-calling chat, and the template fallback.

Dependencies are injected so this stays framework-agnostic and testable.
"""
import json
import os
import time
from datetime import datetime
from typing import Dict, Optional, Tuple, List

from core.context_manager import get_contract
from core.orchestrator.storage import no_cache, output_cache_allowed

FALLBACK_MODEL = os.getenv("PIPELINE_FALLBACK_MODEL", "mimo-v2.5")
FALLBACK_PROVIDER = os.getenv("PIPELINE_FALLBACK_PROVIDER", "opencode-go")
FALLBACK_ENDPOINT = os.getenv(
    "PIPELINE_FALLBACK_ENDPOINT",
    "https://opencode.ai/zen/go/v1/chat/completions",
)


class LLMClient:
    """Provider-agnostic LLM calls for the orchestrator."""

    def __init__(self, model_registry, resolve_model_config, llm_cache, project="default"):
        self.model_registry = model_registry
        self._resolve_model_config = resolve_model_config
        self.llm_cache = llm_cache
        self.project = project
        self.semantic_cache = None  # opt-in (4.9)

    def _call_llm(self, prompt: str, agent_id: str, stage_id: str,
                  pin_model: str = "") -> Tuple[Optional[str], Dict]:
        """Call LLM with cache, chunking, and runtime model capability check.
        
        Strategy:
        1. Check application cache first (zero cost)
        2. Get model's context_window from registry (runtime)
        3. If prompt fits → single call
        4. If prompt too long → chunk by artifact, call each chunk, merge
        5. Cache result for future calls
        """
        start_time = time.time()
        max_retries = 2
        retry_delay = 5
        
        session_id = f"pipeline-{self.project}-{agent_id}-{stage_id}"
        
        # Get model from tier config (dynamic per agent)
        tier_config = self._resolve_model_config(agent_id, stage_id)
        primary_model = tier_config["model"]
        provider = tier_config.get("provider", FALLBACK_PROVIDER)
        api_endpoint = tier_config.get("api_endpoint", FALLBACK_ENDPOINT)
        # Candidates may span providers (e.g. free-trial mixing Zen + OpenRouter).
        candidate_cfgs = tier_config.get("candidates")
        if not candidate_cfgs:
            fallback_models = [m for m in (tier_config.get("fallback_models") or [])
                               if m and m != primary_model]
            candidate_cfgs = (
                [{"model": primary_model, "provider": provider, "api_endpoint": api_endpoint}]
                + [{"model": m, "provider": provider, "api_endpoint": api_endpoint}
                   for m in fallback_models]
            )
        # Pin a model (e.g. keep one model across a sectioned run for consistency).
        if pin_model and pin_model != primary_model:
            candidate_cfgs = [{"model": pin_model, "provider": provider, "api_endpoint": api_endpoint}] \
                + [c for c in candidate_cfgs if c.get("model") != pin_model]
        
        # Get model profile for context_window and capabilities (runtime lookup)
        model_profile = self.model_registry.get_model(primary_model)
        model_context_window = model_profile.context_window if model_profile else 1000000

        # Output cap comes from the AGENT CONTRACT (per-agent), not a hardcoded
        # global. Fall back to the model profile only if the contract is absent.
        contract = get_contract(agent_id)
        contract_max_out = contract.get("max_output_tokens", 0) or 0
        model_default_out = getattr(model_profile, "max_output_tokens", 0) if model_profile else 0
        model_max_output = contract_max_out or model_default_out or 16000
        # Env override to RAISE the output cap (free/reasoning models often need a
        # larger budget so the artifact actually completes). Never lowers it.
        try:
            _ov = int(float(os.getenv("PIPELINE_MAX_OUTPUT_TOKENS", "0") or "0"))
            if _ov > model_max_output:
                model_max_output = _ov
        except (TypeError, ValueError):
            pass

        # Continuation token ceiling: bound total (input+output) spend per agent
        # so auto-continue can't run away re-sending the growing context. Verbose
        # (long-document) agents get a larger budget so their artifact can COMPLETE.
        try:
            from core.agent_requirements import continuation as _cont
            factor = float(os.getenv("CONTINUATION_MAX_TOKENS_FACTOR",
                                     str(_cont(agent_id).get("factor", 1.5))))
        except Exception:
            try:
                factor = float(os.getenv("CONTINUATION_MAX_TOKENS_FACTOR", "1.5"))
            except (TypeError, ValueError):
                factor = 1.5
        contract_max_in = contract.get("max_input_tokens", 8000) or 8000
        _derived = int((contract_max_in + max(contract_max_out, 4000)) * factor)
        # Do NOT block a large-but-legitimate artifact on the token budget: apply a
        # generous floor so auto-continue can COMPLETE the document. The ceiling
        # still exists (runaway bound). Override exactly with PIPELINE_MAX_TOTAL_TOKENS.
        try:
            _floor = int(os.getenv("PIPELINE_MIN_TOTAL_TOKENS", "200000") or "0")
        except (TypeError, ValueError):
            _floor = 200000
        max_total_tokens = max(_derived, _floor)
        try:
            _explicit = int(os.getenv("PIPELINE_MAX_TOTAL_TOKENS", "0") or "0")
            if _explicit > 0:
                max_total_tokens = _explicit
        except (TypeError, ValueError):
            pass
        
        # Calculate usable context (80% of model's window)
        usable_context = int(model_context_window * 0.8)
        prompt_chars = len(prompt)
        prompt_tokens_est = prompt_chars // 4  # rough estimate
        
        # Layer 1: generation OUTPUT is never served from cache (always regenerate).
        # The legacy prompt-keyed output cache and the semantic cache are both
        # OUTPUT-side; they are consulted ONLY behind the explicit debug escape
        # hatch PIPELINE_ALLOW_OUTPUT_CACHE=1 (never with the Layer 3 bypass).
        if output_cache_allowed() and not no_cache():
            print(f"  [CACHE] {agent_id}: OUTPUT-CACHE ENABLED "
                  f"(PIPELINE_ALLOW_OUTPUT_CACHE=1; outputs normally regenerate)")
            cached = self.llm_cache.get(prompt, primary_model, agent_id)
            if cached and cached.get("content") and not cached.get("fallback"):
                print(f"  [CACHE HIT] {agent_id} - reusing cached response")
                cached["cache_hit"] = True
                return cached.get("content"), cached

            # Semantic cache is output-side too; same escape hatch.
            sem = getattr(self, "semantic_cache", None)
            if sem is not None:
                try:
                    hit = sem.get(f"{agent_id}\n{prompt}")
                    if hit and hit.get("content"):
                        print(f"  [SEM-CACHE] {agent_id} - semantic cache hit")
                        hit = dict(hit)
                        hit["cache_hit"] = True
                        return hit.get("content"), hit
                except Exception:
                    pass
        else:
            print(f"  [CACHE] {agent_id}: OUTPUT-REGEN (outputs are never cached)")
        
        # Check if prompt fits in single call
        if prompt_tokens_est <= usable_context:
            # Single call, with fallback across the tier's fallback_models
            # (essential for rate-limited free tiers).
            for cand in candidate_cfgs:
                cand_model = cand.get("model")
                cand_provider = cand.get("provider", provider)
                cand_endpoint = cand.get("api_endpoint", api_endpoint)
                cand_profile = self.model_registry.get_model(cand_model)
                cand_ctx = cand_profile.context_window if cand_profile else model_context_window
                content, token_info = self._call_llm_single(
                    prompt, cand_model, cand_provider, cand_endpoint,
                    session_id, agent_id, stage_id, model_max_output,
                    max_total_tokens=max_total_tokens, allow_template=False,
                    fast_fail=True
                )
                if content:
                    if cand_model != primary_model:
                        print(f"  [FALLBACK] {agent_id}: '{primary_model}' unavailable, using "
                              f"'{cand_model}' ({cand_provider})")
                    token_info["cache_hit"] = False
                    token_info["chunking_used"] = False
                    token_info["chunks_count"] = 1
                    token_info["model_context_window"] = cand_ctx
                    # Write OUTPUT cache ONLY behind the explicit escape hatch
                    # (Layer 4: never cache empty/reasoning-only output).
                    if (output_cache_allowed() and not no_cache()
                            and (content or "").strip()):
                        cache_entry = {"content": content, **token_info}
                        self.llm_cache.set(prompt, cand_model, agent_id, cache_entry)
                        if getattr(self, "semantic_cache", None) is not None:
                            try:
                                self.semantic_cache.set(f"{agent_id}\n{prompt}", cache_entry)
                            except Exception:
                                pass
                    return content, token_info
            # All candidates (primary + fallbacks) failed: report as failure so
            # callers do NOT treat this as a completed agent.
            return None, {"input_tokens": 0, "output_tokens": 0,
                          "cached_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0,
                          "cost": 0.0, "selected_model": "", "selected_provider": "",
                          "fallback": True, "attempted": [c.get("model") for c in candidate_cfgs]}
        else:
            # Prefer a bigger-window model in the same tier: a single call avoids the
            # per-chunk instruction cost. If one fits the whole prompt, use it.
            try:
                for c in candidate_cfgs:
                    cm = c.get("model")
                    cp = self.model_registry.get_model(cm)
                    cwin = cp.context_window if cp else 0
                    if cwin > model_context_window and prompt_tokens_est <= int(cwin * 0.8):
                        print(f"  [UPGRADE] {agent_id}: routing to larger-window model "
                              f"'{cm}' ({cwin} tok) to fit prompt in one call")
                        return self._call_llm_single(
                            prompt, cm, c.get("provider", provider),
                            c.get("api_endpoint", api_endpoint), session_id, agent_id,
                            stage_id, model_max_output, max_total_tokens=max_total_tokens,
                            allow_template=False, fast_fail=True)
            except Exception:
                pass
            # Need to chunk - split prompt by artifacts (and by SIZE within an
            # artifact), so it works even if a single artifact exceeds the window.
            print(f"  [CHUNKING] {agent_id} - prompt ({prompt_tokens_est} tokens) exceeds model context ({usable_context} tokens)")
            return self._call_llm_chunked(
                prompt, primary_model, provider, api_endpoint,
                session_id, agent_id, stage_id, model_max_output, model_context_window
            )
    def _call_llm_single(self, prompt: str, model_name: str, provider: str, 
                         api_endpoint: str, session_id: str, agent_id: str, 
                         stage_id: str, max_output_tokens: int,
                         max_total_tokens: Optional[int] = None,
                         allow_template: bool = True,
                         fast_fail: bool = False) -> Tuple[Optional[str], Dict]:
        """Single LLM call with retries and auto-continuation on truncation.

        If the provider stops because it hit max_tokens (finish_reason=length),
        follow-up calls continue the output and the pieces are merged, up to
        max_continuations. This prevents silent truncation of large artifacts.
        """
        import requests
        from dotenv import load_dotenv
        load_dotenv()

        try:
            max_retries = int(os.getenv("PIPELINE_MAX_RETRIES", "2") or "2")
        except (TypeError, ValueError):
            max_retries = 2
        retry_delay = 5
        try:
            from core.agent_requirements import continuation as _cont
            max_continuations = int(os.getenv("PIPELINE_MAX_CONTINUATIONS", "")
                                    or _cont(agent_id).get("max_continuations", 3))
        except Exception:
            max_continuations = 3

        api_key = self._get_api_key(provider)
        if not api_key:
            print(f"[WARNING] No API key for provider: {provider}")
            return None, {"input_tokens": 0, "output_tokens": 0,
                          "cached_tokens": 0, "total_tokens": 0, "cost": 0.0,
                          "selected_model": "", "selected_provider": ""}

        headers = self._build_api_headers(provider, api_key, session_id)

        messages = [{"role": "user", "content": prompt}]
        all_content = ""
        total_input = total_output = total_cached = total_reasoning = 0
        finish_reason = ""
        continuations = 0
        last_attempt = 0
        attempt = 0

        while attempt < max_retries:
            attempt += 1
            last_attempt = attempt
            try:
                data = self._build_api_request_messages(model_name, messages, max_output_tokens)
                response = requests.post(api_endpoint, json=data, headers=headers, timeout=180)

                if response.status_code != 200:
                    print(f"[WARNING] {model_name} API error: {response.status_code}")
                    # With a fallback candidate list, don't burn time retrying a
                    # throttled/unavailable model - move to the next candidate.
                    if fast_fail:
                        break
                    if attempt < max_retries:
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    break

                # Decode JSON as UTF-8 explicitly: requests' .json() uses an
                # apparent-encoding guess (often cp1252) -> mojibake (BI-0079).
                result = json.loads(response.content.decode("utf-8", errors="replace"))
                content = self._extract_response_content(result, provider) or ""
                choices = result.get('choices', [{}])
                finish_reason = choices[0].get('finish_reason', '') if choices else ''

                usage = result.get('usage', {}) or {}
                in_tok = usage.get('prompt_tokens', 0) or max(1, len(prompt) // 4)
                out_tok = usage.get('completion_tokens', 0) or max(1, len(content) // 4)
                cached_tok = usage.get('prompt_tokens_details', {}).get('cached_tokens', 0)
                reason_tok = usage.get('completion_tokens_details', {}).get('reasoning_tokens', 0)

                all_content += content
                total_input += in_tok
                total_output += out_tok
                total_cached += cached_tok
                total_reasoning += reason_tok

                if finish_reason == 'length':
                    spent = total_input + total_output
                    if max_total_tokens and spent >= max_total_tokens:
                        print(f"  [CONTINUE-STOP] {agent_id} reached continuation token "
                              f"ceiling ({spent}/{max_total_tokens}); stopping")
                        break
                    # Only continue when there is usable content and budget for it.
                    # (Some providers return finish_reason=length with empty
                    # content; retrying then just wastes calls.)
                    if content and continuations < max_continuations:
                        continuations += 1
                        print(f"  [CONTINUE] {agent_id} output truncated (length); "
                              f"continuation {continuations}/{max_continuations}")
                        messages = [
                            {"role": "user", "content": prompt},
                            {"role": "assistant", "content": all_content},
                            {"role": "user", "content": "Continue exactly where you stopped. "
                                                        "Output only the continuation; do not repeat earlier content."},
                        ]
                        attempt = 0  # reset retry budget for the continuation request
                        retry_delay = 5
                        continue
                    break

                return all_content, self._build_token_info(
                    model_name, provider, total_input, total_output, total_cached,
                    total_reasoning, finish_reason, continuations, max(0, last_attempt - 1))

            except Exception as e:
                error_msg = str(e)
                if '429' in error_msg or 'rate' in error_msg.lower():
                    if attempt < max_retries:
                        print(f"[RETRY] Rate limited on {model_name}, waiting {retry_delay}s...")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    break
                else:
                    print(f"[WARNING] {model_name} failed: {str(error_msg)[:100]}")
                    break

        # Partial content across continuations is better than a template fallback.
        if all_content:
            return all_content, self._build_token_info(
                model_name, provider, total_input, total_output, total_cached,
                total_reasoning, finish_reason or "error", continuations, max(0, last_attempt - 1))

        # Caller (fallback loop) may want to try another model instead of a stub.
        if not allow_template:
            return None, self._build_token_info(
                model_name, provider, total_input, total_output, total_cached,
                total_reasoning, finish_reason or "error", continuations, max(0, last_attempt - 1))

        # Fallback to template
        print(f"[WARNING] LLM failed for {agent_id}, using template")
        template_content = self._generate_template_output(agent_id, stage_id, prompt)
        return template_content, {"input_tokens": 0, "output_tokens": 0, 
                                  "cached_tokens": 0, "total_tokens": 0, "cost": 0.0,
                                  "selected_model": "", "selected_provider": "",
                                  "cost_per_1k_input": 0.0, "cost_per_1k_output": 0.0,
                                  "fallback": True}
    def _build_token_info(self, model_name: str, provider: str, total_input: int,
                          total_output: int, total_cached: int, total_reasoning: int,
                          finish_reason: str, continuations: int, retries: int) -> Dict:
        """Assemble token_info dict (with cost) for a (possibly continued) call."""
        token_info = {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "cached_tokens": total_cached,
            "reasoning_tokens": total_reasoning,
            "total_tokens": total_input + total_output,
            "cost": 0.0,
            "selected_model": model_name,
            "selected_provider": provider,
            "cost_per_1k_input": 0.0,
            "cost_per_1k_output": 0.0,
            "finish_reason": finish_reason,
            "truncated": finish_reason == "length",
            "continuations": continuations,
            "retries": retries,
        }
        model_profile = self.model_registry.get_model(model_name)
        if model_profile:
            token_info["cost_per_1k_input"] = model_profile.cost_per_1k_input
            token_info["cost_per_1k_output"] = model_profile.cost_per_1k_output
            token_info["cost"] = (total_input / 1000 * model_profile.cost_per_1k_input +
                                  total_output / 1000 * model_profile.cost_per_1k_output)
        return token_info
    def _call_llm_messages(self, messages: List[Dict], agent_id: str, stage_id: str) -> Tuple[str, Dict]:
        """Single completion for a full messages array (used by the tool loop)."""
        import requests
        from dotenv import load_dotenv
        load_dotenv()
        tier = self._resolve_model_config(agent_id, stage_id)
        model = tier["model"]
        provider = tier.get("provider", FALLBACK_PROVIDER)
        endpoint = tier.get("api_endpoint", FALLBACK_ENDPOINT)
        api_key = self._get_api_key(provider)
        if not api_key:
            return "", self._build_token_info(model, provider, 0, 0, 0, 0, "no_api_key", 0, 0)
        headers = self._build_api_headers(provider, api_key, f"toolp-{self.project}-{agent_id}")
        contract = get_contract(agent_id)
        max_out = contract.get("max_output_tokens", 4000)
        try:
            data = self._build_api_request_messages(model, messages, max_out)
            r = requests.post(endpoint, json=data, headers=headers, timeout=180)
            if r.status_code != 200:
                return "", self._build_token_info(model, provider, 0, 0, 0, 0, f"http_{r.status_code}", 0, 0)
            res = json.loads(r.content.decode("utf-8", errors="replace"))
            content = self._extract_response_content(res, provider) or ""
            usage = res.get("usage", {}) or {}
            in_tok = usage.get("prompt_tokens", 0) or (sum(len(m.get("content", "")) for m in messages) // 4)
            out_tok = usage.get("completion_tokens", 0) or (len(content) // 4)
            cached = usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
            fr = (res.get("choices", [{}])[0].get("finish_reason", "") if res.get("choices") else "")
            return content, self._build_token_info(model, provider, in_tok, out_tok, cached, 0, fr, 0, 0)
        except Exception as e:
            return "", self._build_token_info(model, provider, 0, 0, 0, 0, f"error:{str(e)[:60]}", 0, 0)
    def _call_llm_chunked(self, full_prompt: str, model_name: str, provider: str,
                          api_endpoint: str, session_id: str, agent_id: str,
                          stage_id: str, max_output_tokens: int, model_context_window: int) -> Tuple[Optional[str], Dict]:
        """Chunk prompt by artifacts and call LLM for each chunk."""
        # Split prompt into instruction + artifacts
        # The prompt format is: INSTRUCTIONS\n\nCONTEXT FROM PREVIOUS STAGES:\n\n--- artifact1 ---\n...\n\n--- artifact2 ---\n...\n\nWrite the output to: ...
        
        # Extract instruction part (everything before "CONTEXT FROM PREVIOUS STAGES:")
        context_marker = "CONTEXT FROM PREVIOUS STAGES:"
        if context_marker in full_prompt:
            instruction_part = full_prompt.split(context_marker)[0]
            context_and_output = full_prompt.split(context_marker, 1)[1]
        else:
            instruction_part = full_prompt
            context_and_output = ""
        
        # Extract output file path
        output_marker = "Write the output to:"
        if output_marker in context_and_output:
            output_file = context_and_output.split(output_marker)[-1].strip()
            context_part = context_and_output.split(output_marker)[0]
        else:
            output_file = ""
            context_part = context_and_output
        
        # Split context into individual artifacts
        artifacts = []
        parts = context_part.split("\n\n---")
        for i, part in enumerate(parts):
            if part.strip():
                prefix = "---" if i > 0 else ""
                artifacts.append(prefix + part)
        
        # Calculate usable context per chunk
        instruction_tokens = len(instruction_part) // 4
        overhead_tokens = 500  # for output instructions, formatting
        artifact_budget = (int(model_context_window * 0.8) - instruction_tokens - overhead_tokens)
        if artifact_budget < 1000:
            # Instructions are large relative to the window: use the whole remaining
            # window and still split. (Model-upgrade to a bigger window is preferred;
            # this is the last-resort guard so we never divide by an unusable budget.)
            artifact_budget = max(1000, int(model_context_window * 0.9) - instruction_tokens)

        def _split_by_size(text: str, budget: int):
            """Split one artifact into line-bounded pieces each <= budget tokens."""
            pieces, cur, size = [], [], 0
            for line in (text.splitlines() or [text]):
                lt = len(line) // 4 + 1
                if cur and size + lt > budget:
                    pieces.append("\n".join(cur)); cur = [line]; size = lt
                else:
                    cur.append(line); size += lt
            if cur:
                pieces.append("\n".join(cur))
            return pieces or [text]

        # Group artifacts into chunks; SPLIT any artifact larger than the budget so
        # every chunk fits — nothing is dropped, it is processed across chunks.
        chunks = []
        current_chunk = []
        current_size = 0

        for artifact in artifacts:
            artifact_tokens = len(artifact) // 4
            if artifact_tokens > artifact_budget:
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk, current_size = [], 0
                chunks.extend(_split_by_size(artifact, artifact_budget))
                continue
            if current_size + artifact_tokens > artifact_budget and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [artifact]
                current_size = artifact_tokens
            else:
                current_chunk.append(artifact)
                current_size += artifact_tokens

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        if not chunks:
            chunks = _split_by_size(context_part or instruction_part, artifact_budget)
        
        print(f"  [CHUNKS] {len(chunks)} chunks created for {agent_id}")

        # MAP-REDUCE (not naive concatenation): each chunk yields a DENSE digest, then ONE
        # reduce call produces the single coherent artifact — so the saved file is correct.
        total_input_tokens = total_output_tokens = total_cached_tokens = 0
        total_cost = 0.0
        model_info = {}

        def _acc(ti):
            nonlocal total_input_tokens, total_output_tokens, total_cached_tokens, total_cost, model_info
            total_input_tokens += ti.get("input_tokens", 0)
            total_output_tokens += ti.get("output_tokens", 0)
            total_cached_tokens += ti.get("cached_tokens", 0)
            total_cost += ti.get("cost", 0.0)
            if ti.get("selected_model"):
                model_info = ti

        digests = []
        for i, chunk in enumerate(chunks):
            map_prompt = (
                f"{instruction_part}\n\n"
                f"You are given PART {i + 1} of {len(chunks)} of the context. Extract ONLY the "
                f"facts needed to satisfy the instructions above (requirements, ids, decisions, "
                f"names, numbers, constraints). Output a DENSE bullet digest. Do NOT produce the "
                f"final artifact and do NOT add commentary.\n\n"
                f"CONTEXT PART {i + 1}/{len(chunks)}:\n{chunk}")
            c, ti = self._call_llm_single(map_prompt, model_name, provider, api_endpoint,
                                          session_id, agent_id, stage_id, max_output_tokens)
            _acc(ti)
            if c and not ti.get("fallback"):
                digests.append(c)

        merged_content = None
        if digests:
            merged_digest = "\n\n".join(digests)
            for _try in range(3):
                reduce_prompt = (
                    f"{instruction_part}\n\n"
                    f"CONSOLIDATED CONTEXT (digests of all {len(chunks)} parts):\n{merged_digest}\n\n"
                    f"Produce the COMPLETE final artifact now as ONE coherent document (no "
                    f"per-part sections). Write the output to: {output_file}")
                if len(reduce_prompt) // 4 <= int(model_context_window * 0.8) or _try == 2:
                    final, ti = self._call_llm_single(reduce_prompt, model_name, provider,
                                                      api_endpoint, session_id, agent_id,
                                                      stage_id, max_output_tokens)
                    _acc(ti)
                    if final and not ti.get("fallback"):
                        merged_content = final
                    break
                # digests still too big -> compress them, then retry the reduce
                c, ti = self._call_llm_single(
                    "Compress these digests into the fewest bullets that still capture every "
                    "id, number and decision:\n\n" + merged_digest,
                    model_name, provider, api_endpoint, session_id, agent_id, stage_id,
                    max_output_tokens)
                _acc(ti)
                if c and not ti.get("fallback"):
                    merged_digest = c
                else:
                    break
        else:
            # Map produced nothing usable -> fall back to a single (best-effort) call.
            single_prompt = (f"{instruction_part}\n\nCONTEXT FROM PREVIOUS STAGES:\n"
                             f"{context_part}\n\nWrite the output to: {output_file}")
            merged_content, ti = self._call_llm_single(
                single_prompt, model_name, provider, api_endpoint, session_id, agent_id,
                stage_id, max_output_tokens)
            _acc(ti)

        merged_token_info = {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "cached_tokens": total_cached_tokens,
            "reasoning_tokens": 0,
            "total_tokens": total_input_tokens + total_output_tokens,
            "cost": total_cost,
            "selected_model": model_name,
            "selected_provider": provider,
            "cost_per_1k_input": model_info.get("cost_per_1k_input", 0.0),
            "cost_per_1k_output": model_info.get("cost_per_1k_output", 0.0),
            "cache_hit": False,
            "chunking_used": True,
            "chunks_count": len(chunks),
            "model_context_window": model_context_window,
            "fallback": merged_content is None,
        }
        
        # Write OUTPUT cache ONLY behind the explicit escape hatch (never by default).
        if merged_content and output_cache_allowed() and not no_cache():
            cache_entry = {"content": merged_content, **merged_token_info}
            self.llm_cache.set(full_prompt, model_name, agent_id, cache_entry)
        
        return merged_content, merged_token_info
    def _chat_with_tools(self, messages: List[Dict], agent_id: str, stage_id: str,
                         tools: List[Dict]) -> Tuple[Dict, Dict]:
        """Native function-calling chat. Returns (assistant_message, token_info)."""
        import requests
        from dotenv import load_dotenv
        load_dotenv()
        tier = self._resolve_model_config(agent_id, stage_id)
        model = tier["model"]
        provider = tier.get("provider", FALLBACK_PROVIDER)
        endpoint = tier.get("api_endpoint", FALLBACK_ENDPOINT)
        api_key = self._get_api_key(provider)
        if not api_key:
            return {}, self._build_token_info(model, provider, 0, 0, 0, 0, "no_api_key", 0, 0)
        headers = self._build_api_headers(provider, api_key, f"toolp-{self.project}-{agent_id}")
        max_out = get_contract(agent_id).get("max_output_tokens", 4000)
        data = {"model": model, "messages": messages, "max_tokens": max_out, "temperature": 0.3}
        if tools:
            data["tools"] = tools
            data["tool_choice"] = "auto"
        try:
            r = requests.post(endpoint, json=data, headers=headers, timeout=180)
            if r.status_code != 200:
                return {}, self._build_token_info(model, provider, 0, 0, 0, 0, f"http_{r.status_code}", 0, 0)
            res = json.loads(r.content.decode("utf-8", errors="replace"))
            choice = (res.get("choices") or [{}])[0]
            msg = choice.get("message", {}) or {}
            usage = res.get("usage", {}) or {}
            in_tok = usage.get("prompt_tokens", 0) or (len(str(messages)) // 4)
            out_tok = usage.get("completion_tokens", 0) or 0
            cached = usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
            ti = self._build_token_info(model, provider, in_tok, out_tok, cached, 0,
                                        choice.get("finish_reason", ""), 0, 0)
            return msg, ti
        except Exception as e:
            return {}, self._build_token_info(model, provider, 0, 0, 0, 0, f"error:{str(e)[:60]}", 0, 0)
    def _get_api_key(self, provider: str) -> str:
        """Get API key based on provider."""
        import os
        from dotenv import load_dotenv
        load_dotenv()
        
        key_map = {
            "opencode-go": "OPENCODE_ZEN_API_KEY",
            "opencode-zen": "OPENCODE_ZEN_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }
        
        env_key = key_map.get(provider, "OPENCODE_ZEN_API_KEY")
        return os.getenv(env_key, "")
    def _build_api_headers(self, provider: str, api_key: str, session_id: str) -> dict:
        """Build API headers based on provider."""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # Cloudflare (error code 1010) rejects requests with no/blank User-Agent
        # before they reach the Zen API. Send one on every provider path; override
        # with PIPELINE_USER_AGENT (default preserves the historical Zen value).
        headers["User-Agent"] = os.getenv("PIPELINE_USER_AGENT", "product-forge-pipeline/1.0")

        # Add provider-specific headers
        if provider in ["opencode-go", "opencode-zen"]:
            headers["x-opencode-session"] = session_id

        return headers
    def _build_api_request(self, model_name: str, prompt: str, max_output_tokens: int = 16000) -> dict:
        """Build API request data with model-specific max_output_tokens."""
        return {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_output_tokens,
            "temperature": 0.7
        }
    def _build_api_request_messages(self, model_name: str, messages: list, max_output_tokens: int = 16000) -> dict:
        """Build an API request from a full messages array (used for continuation)."""
        return {
            "model": model_name,
            "messages": messages,
            "max_tokens": max_output_tokens,
            "temperature": 0.7
        }
    def _extract_response_content(self, result: dict, provider: str) -> str:
        """Extract content from API response based on provider."""
        try:
            message = result['choices'][0]['message']

            content = message.get('content')
            # Some providers return structured content blocks.
            if isinstance(content, list):
                parts = []
                for p in content:
                    if isinstance(p, dict):
                        parts.append(str(p.get("text") or p.get("content") or ""))
                    else:
                        parts.append(str(p))
                content = "".join(parts)
            if content is None:
                content = ""
            # NEVER fall back to message['reasoning']: that leaks the model's
            # chain-of-thought into artifacts (BI-0075). Empty content is detected
            # by the artifact/compliance check and retried (BI-0034).
            return content if isinstance(content, str) else str(content)
        except (KeyError, IndexError):
            return ""
    def _generate_template_output(self, agent_id: str, stage_id: str, prompt: str) -> str:
        """Generate template output as fallback."""
        contract = get_contract(agent_id)
        return f"""# {agent_id.upper()} Output - Stage {stage_id}

**Task:** {prompt[:200]}...
**Agent:** {agent_id}
**Stage:** {stage_id}
**Timestamp:** {datetime.now().isoformat()}
**Status:** Generated from template (LLM unavailable)

## Task Description
{prompt[:1000]}

## Quality Checks
- [x] Context package built ({contract['max_input_tokens']} token budget)
- [x] Knowledge routed
- [x] Budget checked

---
*Generated by PipelineExecutor (template fallback)*
"""
