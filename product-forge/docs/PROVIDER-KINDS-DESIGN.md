# Provider-Kind Abstraction + Kind-Aware Router — Design (BI-0193)

## Goal
One abstraction for **provider kind** (`direct` | `aggregator` | `self-host`), with per-kind request
shaping and a **kind-aware model router**, so routing/selection works for all provider kinds — the
foundation the multimodal + standards epics (`BI-0185`/`0195`) build on.

## 360° — verified current state
| Concern | Now | Target | Owner |
|---|---|---|---|
| Provider kind data | `config/credentials.json` `providers.<p>.kind` = direct/aggregator (self-host unused) | same, first-class | `core/credentials.py` |
| `provider_kind()` | `credentials.provider_kind(p)` returns the string | keep; add a **registry** with behaviour | `core/credentials.py` |
| Request shaping | `llm_client._build_api_headers` special-cases `opencode-*` (session header); `_extract_response_content` OpenAI-shaped only | per-kind adapters (headers/body/response/tool-calls) | new `core/provider_kinds.py` |
| Routing | `llm_client` picks candidates by tier config; provider is a string; `kind` never consulted | **kind-aware** candidate ordering/validation | `core/orchestrator/llm_client.py` |
| Model gate | `core/model_gate.py` fail-closed on UNKNOWN model fit | unchanged; kind feeds fit/needs | `core/model_gate.py` |
| Endpoints | `tier_config.api_endpoint` per model/profile | per-kind endpoint resolution w/ fallback | `provider_kinds` + tier config |

**Blast radius / consumers:** `llm_client` (3 chat paths), `credentials`, `model_gate`, `agent_runner`
(model resolution), dashboard `/api/v1/model-*`. Keep single writers: `credentials` owns kind config;
the new module owns *behaviour*, not config.

## Design decisions
- **New module `core/provider_kinds.py`** = the abstraction (no new store; reads `credentials` kind data
  + a small built-in adapter table). Provides:
  - `kinds()` → `direct|aggregator|self-host`.
  - `kind_of(provider)` → delegates to `credentials.provider_kind` (single source of truth).
  - `adapter(provider)` → an `Adapter` (headers(base,key,session), body-normalize, extract_content,
    supports(tool_calls/images), endpoint(provider, model, fallback)).
  - `order_candidates(candidates, prefer_kind="")` → stable ordering; validates kind ∈ kinds().
  - `supports(provider, feature)` → e.g. `"images"`, `"tools"`, `"json_mode"` — wired into capability
    steering so unsupported features are dropped/blocked (fail-closed).
- **Kind-aware routing in `llm_client`:** when building `candidate_cfgs`, annotate each with its kind
  and order by `PIPELINE_PREFER_KIND` if set else by tier order. An unknown provider is annotated
  `kind=""` (a custom/unregistered provider with an explicit endpoint is legal); **strict fail-closed
  dropping** is available via `order_candidates(reject_unknown=True)` and blocking of unknown models is
  owned by `core/model_gate` (already fail-closed). No behaviour change when kinds are the existing
  direct/aggregator set.
- **Adapters are data + thin functions** (no transport rewrite): current OpenAI-shaped request/response
  is the default adapter; aggregator (openrouter/replicate/fal/kie) gets the same shape + its headers;
  direct providers keep per-provider headers. This is the "metadata + request shaping" slice.
- **Config-driven, no hardcoding:** adapter table keyed by provider with a `kind`-level default, so new
  providers only need a `credentials.json` entry.

## Plan (branch `feature/bi-0193-provider-kinds`)
1. `docs/PROVIDER-KINDS-DESIGN.md` (this file).
2. `core/provider_kinds.py`: kinds, kind_of, adapters, order_candidates, supports. Register nothing new
   (no store); ensure it's imported on the runtime path (wired via `llm_client`).
3. `core/orchestrator/llm_client.py`: annotate candidates with kind; fail-closed unknown kind; order by
   `PIPELINE_PREFER_KIND`/tier; route headers/body/extract through `provider_kinds.adapter`.
4. `config/env-flags.json`: add `PIPELINE_PREFER_KIND` (default "").
5. Tests: `test_provider_kinds.py` — kind_of for known providers, adapter selection, order_candidates,
   supports() fail-closed for unknown feature, and that llm_client candidate annotation is kind-aware.
6. Gates: compileall, wired_audit, workflow_matrix, pipeline tests, precheck.
7. Merge; close `BI-0193` through the loop.

## Acceptance
- `provider_kinds.kind_of` matches `credentials.provider_kind` for every configured provider.
- Unknown provider/kind ⇒ fail-closed (blocked), never silently routed.
- `llm_client` candidates carry a validated kind; ordering honors `PIPELINE_PREFER_KIND`.
- No new store; single-writer intact; existing routing behaviour unchanged for direct/aggregator.
- `precheck` PASS.

## Out of scope (tracked separately)
Full transport adapters per provider (SDK clients), self-host deployment, multimodal parts (BI-0186),
plugin/registry framework (BI-0200).
