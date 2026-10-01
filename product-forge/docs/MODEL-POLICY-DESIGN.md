# Per-Model Eligibility Policy — Design (BI-PF-0278)

## Goal
Model eligibility is ad-hoc (`agent-capability-vector` + `model_gate` needs) with **no per-model policy**.
Add a **versioned policy schema + validator** (`config/model-policy.json` / `core/model_policy.py`) with
`allowed_tasks`, `restricted_tasks`, `quality_threshold`, `max_task_cost`, `fallback`, `independent_review`,
consumed by the model-strategy gate/router (and surfaced in the dashboard) — fail-closed, scalable, API-first.

## 360° — verified current state
| Concern | Now | Target | Owner |
|---|---|---|---|
| Capability gate | `core/model_gate.evaluate` (needs vs catalog fit) | consult policy allow/restrict first | extend |
| Capability catalog | `core/model_catalog.capabilities/fit` | unchanged (facts) | reuse |
| Agent capability vector | `core/agent_capabilities` (per-agent needs) | unchanged (needs) | reuse |
| Strategy gate | `core/model_strategy.assess` | surface policy verdicts per model | extend |
| Provider health | `core/provider_health` (BI-PF-0279) | `fallback` chains consulted | reuse |
| Cost | `core/cost_model` (BI-0194) | `max_task_cost` enforced | reuse |
| Authz/approval | model_gate reject-unknown | policy fail-closed on unknown model | extend |

**Blast radius:** new `core/model_policy.py` (owner of `config/model-policy.json`), consulted by
`model_gate.evaluate` (eligibility) + `model_strategy.assess` (surface), API + store-registry entry.

## Design decisions (modular, 1 truth per concern)
- **New `core/model_policy.py`** — owner of `config/model-policy.json`:
  - **Versioned schema** (`schema_version: 1`): per model →
    ```
    {
      "allowed_tasks":   ["chat","vision","coding",...],   # empty = any
      "restricted_tasks":["medical_advice",...],           # explicit deny (wins over allowed)
      "quality_threshold": 0.0..1.0,                        # optional min quality for critical work
      "max_task_cost": 0.0,                                 # per-task cost ceiling (USD; 0 = none)
      "fallback": ["model-a","model-b"],                    # ordered fallback candidates
      "independent_review": true|false                      # needs a second-model review
    }
    ```
  - `validate(policy) -> [errors]`: schema_version present; task names non-empty; thresholds in range;
    costs >= 0; fallbacks reference known catalog models (unknown ⇒ error, **fail-closed**).
  - `eligible(model, task, *, critical=False, est_cost=0.0) -> {ok, reasons, fallback, independent_review}`:
    deny if task ∈ restricted; deny if task ∉ allowed (when allowed non-empty); deny if est_cost >
    max_task_cost; deny if critical and quality_threshold unmet (from catalog quality if available);
    unknown model ⇒ **deny** (fail-closed). Returns the policy's fallback chain for the router.
  - `policy_for(model)` / `all_policies()`: lookup (id/registry-name/`:free` variant robust, like catalog).
- **Reuse, never fork:** `model_catalog` stays the fact source; `model_policy` is the *rules* source;
  `model_gate` composes both (rules first, then capability). `provider_health` supplies fallback liveness;
  `cost_model` supplies est_cost. One policy file, one writer.
- **Fail-closed:** unknown model / malformed policy / over-budget / restricted task ⇒ **deny** with reasons
  (never silently allow). Consistent with `MODEL_GATE_REJECT_UNKNOWN`.
- **Stitched where decisions happen:**
  - `model_gate.evaluate`: for each agent's assigned model, call `eligible(...)`; a policy deny marks the
    entry `POLICY_BLOCKED` (with reasons + fallback); `recommended` prefers policy fallback (then catalog fit).
  - `model_strategy.assess`: adds `model_policy` verdicts per assignment + warnings for blocked models.
- **API-first:** `GET /api/v1/model-policy` (all), `GET /api/v1/model-policy/{model}`, `GET
  /api/v1/model-policy/{model}/eligible?task=&critical=` (decision), `POST /api/v1/model-policy/validate`.
- **Scalable:** pure lookup + validation; no network; deterministic.

## Plan (branch `feature/bi-pf-0278-model-policy`)
1. `docs/MODEL-POLICY-DESIGN.md` (this file).
2. `config/model-policy.json` (schema_version 1; seed a few representative entries + `_doc`) + register in
   `config/store-registry.json`.
3. `core/model_policy.py` — `validate`, `eligible`, `policy_for`, `all_policies`, `load`.
4. Wire: `core/model_gate.evaluate` (policy-aware statuses/recommendation), `core/model_strategy.assess`
   (surface verdicts).
5. `dashboard/api/app.py` — `/api/v1/model-policy*`.
6. Tests `test_model_policy.py` — schema validation (good/bad); allowed/restricted logic; unknown model
   fail-closed; max_task_cost deny; quality_threshold on critical; fallback returned; model_gate marks
   POLICY_BLOCKED; strategy report includes verdicts; API shape.
7. Gates: compileall, wired_audit, workflow_matrix, pipeline tests, precheck.
8. Merge; close `BI-PF-0278` through the loop.

## Acceptance
- A versioned model policy schema exists and validates (invalid ⇒ explicit errors, fail-closed).
- `eligible()` enforces allowed/restricted tasks, cost ceiling, quality threshold, and denies unknown models;
  it returns fallback + independent_review.
- `model_gate` and `model_strategy` consult the policy; API surfaces lookups + decisions.
- `precheck` PASS; single writer; no fork of catalog facts; zero regression when a model has no policy
  (falls back to today's capability-only behavior — asserted by test).

## Out of scope (tracked separately)
Live policy sync from providers, per-task quality scoring engine, human-approval workflow for overrides.
