# ENG-9 — DOGFOOD Execution

**Phase:** ENG-9 of `PRODUCT_FORGE_MASTER_API_FIRST_ENGINEERING_FACTORY_E2E_EXECUTION_PLAN-updated.md` (§23)
**Status:** Implemented (orchestration + fail-closed states) — gate PASS
**Depends on:** ENG-5 (PR/evidence), ENG-6 (validation), ENG-8 (integration/merge), ENG-3 (vcs/worktree)

## What this phase builds

ENG-9 orchestrates a **DOGFOOD run** that proves Product Forge can build a real product end-to-end — validating
**both** (A) PF as a platform and (B) the product PF generates. It reuses canonical owners only.

```
core/dogfood.py             # baseline -> fresh worktree -> RUN_ID -> pipeline (run_entry) -> generated-product
                            #   validation -> evidence -> defect classification -> (optional) repair -> report
api/routers/validation.py   # POST /api/v1/validation/dogfood
scripts/dev/dogfood_check.py# gate (dry, fail-closed) - in precheck
config/engineering-flow.json# dogfood step: planned -> partial
```

## Flow (§23)

```
approved baseline → fresh isolated worktree → RUN_ID → product idea → deployment target → baseline health
  → full PF pipeline (run_entry) → observe stages → generated-product validation (DOGFOOD profile)
  → evidence → defect classification → controlled repair (only if authorized) → retest → regression → report
```

- **Baseline:** exact SHA via `validation_engine._resolve_target`; validated in a **fresh worktree**; the baseline
  branch is never modified (worktree removed after).
- **Pipeline:** triggered through the **ONE** canonical path `core.run_entry.enqueue` (source `dogfood`).
- **Generated product validation:** the DOGFOOD profile of the ENG-6 engine.
- **Evidence:** run-bound `core.github.build_evidence`; **defects** classified via `core.issues.open`.
- **Repair:** `auto_repair` false; `controlled_repair` only if explicitly authorized.

## Final states

`PASS` · `PARTIAL_SUCCESS` (e.g. dry run / unverified checks) · `FAIL` (generated-product failed) ·
`BLOCKED` (baseline unresolved / pipeline could not start). **Fail-closed: a dry or incomplete run is never
reported PASS.** Never: hide failures, weaken security, change tests to pass, bypass CI, delete evidence.

## API

| Method | Path | Notes |
|---|---|---|
| POST | `/api/v1/validation/dogfood` | run DOGFOOD (operator); `dry/trigger_pipeline/use_worktree/repair/idea/target/baseline` |
| GET | `/api/v1/validation/runs?profile=DOGFOOD` | prior dogfood reports (same store) |

Records to `validation-runs.json` (no new store).

## 360° dependency check

- No new store; reuses `vcs`/`run_entry`/`validation_engine`/`github`/`issues`.
- Fresh-worktree isolation prevents modifying the baseline; pipeline goes through the single run entry.
- Gate proves fail-closed behavior (non-repo ⇒ BLOCKED; dry ⇒ not PASS).

## Verification (executed)

```
python -m compileall -q api core scripts dashboard                # 0
python scripts/dev/wired_audit.py                                 # OK (unwired 0, naming 0)
python scripts/dev/dogfood_check.py                               # OK (dry fail-closed states, baseline, steps)
python scripts/dev/precheck.py                                    # PASS (97 paths, 105 ops in sync, lint clean)
```

## Gate (§23)

| Criterion | Result |
|---|---|
| Fresh isolated worktree from approved baseline | ✅ |
| RUN_ID minted; pipeline via `run_entry` | ✅ |
| Generated-product validation | ✅ DOGFOOD profile |
| Evidence + defect classification | ✅ `build_evidence` + `issues` |
| Controlled repair only when authorized | ✅ `auto_repair` false |
| Final states PASS/PARTIAL_SUCCESS/FAIL/BLOCKED | ✅ fail-closed |
| Never hide failures | ✅ dry/incomplete ⇒ non-PASS |
| API-first + wired + exercised | ✅ endpoint + gate + tests |
| ENG-0 flow updated | ✅ `dogfood`: planned → partial |

**ENG-9 GATE: PASS.** Next: **ENG-10 — RELEASE execution**.
