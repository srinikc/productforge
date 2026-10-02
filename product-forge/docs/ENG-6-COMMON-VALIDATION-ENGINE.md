# ENG-6 — Common Validation Engine

**Phase:** ENG-6 of `PRODUCT_FORGE_MASTER_API_FIRST_ENGINEERING_FACTORY_E2E_EXECUTION_PLAN-updated.md` (§19/§20)
**Status:** Implemented (coordination engine) — gate PASS
**Depends on:** ENG-5, API-5

## What this phase builds

Plan §19: **one Validation Engine, not separate validation architectures** — same evidence model, test
foundation, policy, defect/RCCA, GitHub integration, reporting, gate framework; different target/scope/depth/
trigger/repair/promotion per **profile** (§20).

ENG-6 delivers a **thin orchestration/coordination layer** that runs a profile by **delegating to the existing
canonical validators** — it does NOT reimplement validation (plan §41: no second validation engine).

```
core/validation_engine.py            # engine: profile dispatch + target resolution + evidence + verdict
config/validation-profiles.json      # profile matrix (FEATURE_PR / INTEGRATION / DOGFOOD / RELEASE) [registered]
api/routers/validation.py            # GET /validation/profiles, /validation/runs; POST /validation/run
scripts/dev/validation_engine_check.py   # gate (precheck)
config/engineering-flow.json         # validation_engine step (ENG-6) -> exists
```

## Composition (reuse, not duplication)

| Engine step | Delegates to (owner) |
|---|---|
| target resolution (exact SHA / base / merge-base) | `core.vcs.VCSManager` |
| repo/build/tests + quality gate | `core.run_quality_gate`, `core.test_framework_integration`, `core.verification_runner` |
| policy / coverage | `core.verification_policy` |
| tests verdict | `core.qa_report.load` |
| PR gate | `core.pr_gate.evaluate` |
| run-bound decision | `core.close_loop.verify_run` |

## Profiles (§20)

| Profile | target | checks | repair | promotion |
|---|---|---|---|---|
| **FEATURE_PR** | pr | target, quality_gate, tests, policy, verification, pr_gate | false | merge-to-develop |
| **INTEGRATION** | integration | + cross_contract | false | promote-integration |
| **DOGFOOD** | baseline | + e2e | true | none |
| **RELEASE** | release | + security | false | approve-release |

Checks not yet owned by a subsystem are recorded `unknown` and drive a **BLOCKED** verdict (fail-closed) until
their phase (ENG-7/8/9/10) supplies them.

## Result model

`PASS` (all checks pass/skip with ≥1 pass) · `FAIL` (any fail) · `BLOCKED` (unknown/unresolved target/no
positive signal). Recorded run-bound to `validation-runs.json` (owner `core/validation_engine.py`) with target
SHA/base/merge-base + per-check detail + promotion/repair decision.

## API

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/validation/profiles` | the profile matrix |
| GET | `/api/v1/validation/runs?scope&project&profile` | recorded validation runs |
| POST | `/api/v1/validation/run` | run a profile (operator) |

## 360° dependency check

- No validation logic duplicated; every check delegates to an existing owner.
- One new store (`validation-runs.json`) + one config (`validation-profiles.json`), both registered, single writer.
- Reachable from `scripts/dev/validation_engine_check.py` (precheck) → invocation-audit green.
- ENG-0 gate verifies the `validation_engine` step's owner + route.

## Verification (executed)

```
python -m compileall -q api core scripts dashboard                # 0
python scripts/dev/wired_audit.py                                 # OK (unwired 0, naming 0)
python scripts/dev/precheck.py                                    # PASS (incl. validation-engine, api-governance, api-docs, lint)
```

## Gate (plan §19/§20)

| Criterion | Result |
|---|---|
| ONE validation engine | ✅ `core/validation_engine.py` orchestrates existing owners |
| Profiles FEATURE_PR/INTEGRATION/DOGFOOD/RELEASE | ✅ config + dispatch |
| Same evidence/policy/gate/defect/GitHub integration | ✅ composes those owners |
| Different target/scope/depth/repair/promotion | ✅ per-profile config |
| Run-bound evidence, no false green | ✅ target SHA recorded; unknown ⇒ BLOCKED |
| API-first + wired + exercised | ✅ `/api/v1/validation/*` + gate + tests |
| ENG-0 flow updated | ✅ `validation_engine`: new step → exists |

**ENG-6 GATE: PASS.** Next: **ENG-7 — FEATURE_PR execution** (fills the `cross_contract`/exact-PR depth).
