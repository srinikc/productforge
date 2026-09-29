# Capability Steering — design & plan (S4: BI-0221..BI-0230)

> Design-first (EOS §4). Cut cost/latency by steering **per-call capabilities** (reasoning,
> structured output, tools, vision, context/output size) instead of always-on maximal calls.

## 1. DESIGN — outcome & invariants
- **Outcome:** smaller, task-appropriate LLM calls; no over-generation; graceful degrade when a model lacks a
  needed capability.
- **Invariants:** a capability is enabled **only if the agent needs it AND the model supports it**; never ask a
  model for something it cannot do; degrade is explicit (flagged), never silent; behaviour stays backward-compatible.

## 2. 360° — components (blast radius)
| Piece | Now | Change |
|---|---|---|
| Per-agent capability vector | none (needs in `config/agent-requirements.json`) | new `config/agent-capability-vector.json` + `core/agent_capabilities.py` (BI-0221) |
| Request builder | llm_client builds params inline | `agent_capabilities.build_request(agent, model_caps)` (BI-0222) |
| Reasoning on/off | always on for reasoning models | `reasoning_enabled(agent)` + request param (BI-0223) |
| Model gate | `needs_for` from agent-requirements | merges the vector (this slice wires it) |
| Consumers | `llm_client`, `model_router`, `model_gate`, `pipeline_executor` | read the builder/vector |

## 3. PLAN — ordered
- **Slice 1 (this change):** capability vector + `build_request` (capability-aware) + reasoning control; model gate
  consumes the vector (BI-0221/0222/0223).
- **Slice 2:** apply the builder in `llm_client` per call (reasoning/structured/tool-subset + min_output/context)
  (BI-0222/0223 wiring); structured-output-first + deterministic render (BI-0224).
- **Slice 3:** parallel section/feature generation (BI-0225); context discipline compact+current (BI-0226).
- **Slice 4:** capability fallback + escalate-on-failure (BI-0227); OSS role-prompt standardization (BI-0228).
- **Slice 5:** verbose-gated logging + loops/tool-calls in summary (BI-0229); incremental artifact writes (BI-0230).

## 4. Acceptance
- `build_request` enables only supported capabilities; `degraded` names the shortfalls.
- `model_gate` needs come from the vector; default agents unaffected (backward compatible).
- Later slices wired into the call path + loop paths; tests per slice.

## 5. Progress
- **Slice 1 done:** `core/agent_capabilities.py` (vector + `build_request` + `reasoning_enabled`); config
  `agent-capability-vector.json`; `model_gate.needs_for` merges the vector. Tests: `test_capability_steering.py`.
