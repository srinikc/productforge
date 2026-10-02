# ENG-7 — FEATURE_PR Execution

**Phase:** ENG-7 of `PRODUCT_FORGE_MASTER_API_FIRST_ENGINEERING_FACTORY_E2E_EXECUTION_PLAN-updated.md` (§21)
**Status:** Implemented (FEATURE_PR execution) — gate PASS
**Depends on:** ENG-5 (PR/evidence), ENG-6 (validation engine), ENG-3 (vcs/worktree)

## What this phase builds

ENG-7 executes the **FEATURE_PR** profile of the Common Validation Engine against an **exact** PR/branch/commit,
in a **fresh validation worktree** (the developer branch is never modified), and returns PASS/FAIL/BLOCKED with
GitHub evidence and a PR-merge decision.

```
core/validation_engine.feature_pr(...)   # exact SHA + base + merge-base; changed-file + impact; fresh worktree
api/routers/validation.py                # POST /api/v1/validation/feature-pr
scripts/dev/feature_pr_check.py          # gate (precheck)
config/engineering-flow.json             # feature_pr step: planned -> partial
```

## Flow (§21)

```
PR / branch / commit → resolve exact SHA → resolve base → merge-base → fresh validation worktree → RUN_ID
  → changed-file analysis → impact analysis → FEATURE_PR checks (quality-gate/tests/policy/verification/pr-gate)
  → GitHub evidence → PR gate → PASS / FAIL / BLOCKED
```

- **Exact target:** `_resolve_target` records `sha`, `base`, `base_sha`, `merge_base`, `branch`.
- **Changed files/impact:** `git diff --name-only merge_base..sha` + component mapping.
- **Fresh worktree:** `core.vcs.add_worktree("validate-<run>", base=sha)` — checks run against the worktree;
  the developer branch is never touched; the worktree + validation branch are removed afterwards.
- **GitHub evidence:** `core.github.build_evidence(...)` (run-bound) attached to the result.
- **PR gate:** `core.pr_gate.can_merge` → `pr_merge` check.
- **`auto_repair: false`** always (feature validation never modifies the branch).
- **On failure (opt-in `record_defects`):** raises an Issue (`core.issues.raise_issue`, kind=bug) carrying the
  run/evidence — which the canonical loop takes to RCCA → Backlog.

## Result

`PASS` (all checks pass/skip, ≥1 pass) · `FAIL` (any fail) · `BLOCKED` (unknown/unresolved — fail-closed).
Run-bound to `validation-runs.json` with target SHA + changed files + per-check detail.

## API

| Method | Path | Notes |
|---|---|---|
| POST | `/api/v1/validation/feature-pr` | run FEATURE_PR (operator); body `scope/project/target/base/use_worktree/record_defects` |

## 360° dependency check

- Composes existing owners only (`vcs`, `validation_engine` checks, `github`, `pr_gate`, `issues`); no duplicate
  validator, no new store (writes `validation-runs.json`).
- Worktree isolation reuses ENG-3; evidence reuses ENG-5; decision reuses ENG-6/`close_loop`.
- Gate proves: developer-branch HEAD unchanged + worktree cleaned up.

## Verification (executed)

```
python -m compileall -q api core scripts dashboard                # 0
python scripts/dev/wired_audit.py                                 # OK (unwired 0, naming 0)
python scripts/dev/feature_pr_check.py                            # OK (exact SHA, changed-file/impact, isolation, evidence, cleanup)
python scripts/dev/precheck.py                                    # PASS (api-governance 90 paths, api-docs 97 ops in sync, lint clean)
```

## Gate (§21)

| Criterion | Result |
|---|---|
| Exact SHA / base / merge-base resolved | ✅ |
| Fresh validation worktree; dev branch untouched | ✅ gate asserts HEAD unchanged + cleanup |
| Changed-file + impact analysis | ✅ |
| FEATURE_PR checks (build/tests/API/security/PF/gate) | ✅ composed (fail-closed where a signal is absent) |
| GitHub checks/evidence | ✅ `build_evidence` attached |
| PR gate decision | ✅ `can_merge` |
| `auto_repair: false` | ✅ |
| Defect→Issue→RCCA→Backlog handoff | ✅ opt-in `record_defects` |
| ENG-0 flow updated | ✅ `feature_pr`: planned → partial |

**ENG-7 GATE: PASS.** Next: **ENG-8 — INTEGRATION execution** (integration queue, cross-workstream checks, and
the shared-path reservation design `BI-PF-0357`).
