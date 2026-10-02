# ENG-8 — INTEGRATION Execution

**Phase:** ENG-8 of `PRODUCT_FORGE_MASTER_API_FIRST_ENGINEERING_FACTORY_E2E_EXECUTION_PLAN-updated.md` (§22)
**Status:** Implemented (integration validation + merge enforcement + shared-path reservation) — gate PASS
**Depends on:** ENG-6 (validation engine), ENG-7 (FEATURE_PR), ENG-5 (PR), ENG-3 (vcs/worktree)

## What this phase builds

ENG-8 validates that **independently developed changes work together**, enforces the **merge gate**, and adds the
**shared-path reservation** that serializes concurrent workers on common code (`BI-PF-0357`).

```
core/validation_engine.run(profile="INTEGRATION")   # integration validation (exact SHA, checks, promotion)
core/merge_gate.evaluate / queue                    # merge requires pr_gate + a PASS validation run
core/reservations.py + config/shared-paths.json     # shared-path reservation + common-code detection
core/scheduler.plan()                               # defers tasks on shared/reserved paths
api/routers/validation.py, api/routers/reservations.py
.github/workflows/structure.yml                     # CI: full precheck is the required gate
```

## Integration validation (§22)

`POST /api/v1/validation/integration` runs the **INTEGRATION** profile (via the ENG-6 engine): exact
target/base/merge-base, changed-file/impact, the FEATURE_PR checks plus **cross-workstream/shared-core** emphasis,
and a **promotion** decision. Result PASS/FAIL/BLOCKED (fail-closed).

## Merge enforcement (folded §38)

`core.merge_gate.evaluate(project, project_dir)` → merge allowed only if **`pr_gate.can_merge`** AND a **PASS**
validation run (FEATURE_PR/INTEGRATION) exists. Non-PASS ⇒ **BLOCKED** (`unmet` list). `queue()` lists PR records
with their gate decision (the **integration queue**). CI (`.github/workflows/structure.yml`) now runs the **full
`precheck`** as the required check; **branch protection** (required status check, no force-push) is documented in
the workflow.

## Shared-path reservation (`BI-PF-0357`)

- **Detection:** `config/shared-paths.json` (components + globs) + a git-**hotspot** heuristic (advisory,
  read-only) — `core.reservations.is_shared/shared_paths/hotspots`.
- **Reservation:** `core/reservations.py` — advisory holds on a path/module with **TTL** (no deadlock),
  `acquire/acquire_many/release`, single writer of `reservations.json`.
- **Scheduler:** `core.scheduler.plan()` **defers** a task if any declared path is **reserved by another live
  holder** (reason `reserved by <task>`) or if another task in the wave already holds shared code
  (`shared path overlap with <task>`). Disjoint work stays parallel.
- **WIP:** safe — the worker snapshots WIP on its own branch (`VCSManager.wip_snapshot`); never merged unvalidated.

## API

| Method | Path | Notes |
|---|---|---|
| POST | `/api/v1/validation/integration` | run the INTEGRATION profile (operator) |
| GET | `/api/v1/validation/merge-gate?scope&project` | merge decision (pr_gate + validation) |
| GET | `/api/v1/validation/merge-gate/queue` | integration queue |
| GET | `/api/v1/reservations` / `/shared-paths` | active holds / allowlist + hotspots |
| POST | `/api/v1/reservations` / `/reservations/release` | acquire / release (operator) |

## 360° dependency check

- New stores `reservations.json` + config `shared-paths.json`, both registered, single writers.
- Reuses `pr_gate`, `validation_engine`, `vcs`, `github` — **no duplicate** gate/queue/validator.
- Scheduler change is additive (shared/reserved serialization) with the ENG-2 gate still green.
- `PF_RESERVATIONS_FILE` override keeps gates/tests off the shared store.

## Verification (executed)

```
python -m compileall -q api core scripts dashboard                # 0
python scripts/dev/wired_audit.py                                 # OK (unwired 0, naming 0)
python scripts/dev/reservations_check.py                          # OK
python scripts/dev/merge_gate_check.py                            # OK (fail-closed)
python scripts/dev/precheck.py                                    # PASS (96 paths, 104 ops in sync, lint clean)
```

## Gate (§22)

| Criterion | Result |
|---|---|
| Integration validation (exact target + checks + promotion) | ✅ INTEGRATION profile |
| Cross-workstream / shared-core emphasis | ✅ shared detection feeds scheduling |
| Merge requires green evidence | ✅ `merge_gate` (pr_gate + PASS validation) |
| Integration queue | ✅ `merge_gate.queue` |
| CI runs full precheck (required) | ✅ workflow updated (+ branch-protection note) |
| Shared-path reservation serializes common code | ✅ reservations + scheduler |
| Common-code detection | ✅ allowlist + git hotspots |
| API-first + wired + exercised | ✅ endpoints + gates + tests |
| ENG-0 flow updated | ✅ `integration` / `merge_gate` steps |

**ENG-8 GATE: PASS.** Next: **ENG-9 — DOGFOOD execution** (full PF E2E; generated-product validation).
