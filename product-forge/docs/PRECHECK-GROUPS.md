# Precheck Guide — tiers, named groups, gates, and test profiles (SSOT-adjacent)

> **Single source of truth is the code**: `scripts/dev/precheck.py` (`_GATES`, `_GROUP_OF`, `_GROUP_ORDER`)
> and `config/validation-profiles.json`. `config/ci-cd-gates.json` is the DERIVED registry (projected from
> `precheck._GATES` by `scripts/dev/ci_cd_gates_check.py`). This document is the human-readable guide to that
> data — keep it in step with the code. BI-PF-1419.

## 1. What precheck is

`scripts/dev/precheck.py` runs the same checks CI enforces, so a PR is green before it is opened. Run from
`product-forge/`. Exit code is non-zero if any step fails.

| Invocation | What it runs |
|---|---|
| `python scripts/dev/precheck.py` | **fast (default)**: the fast-tier gates whose *area* matches the change + **changed-scoped tests** (+ smoke). Derived/bookkeeping-only changes get the **minimal** tier (`compile` + `docs-fresh`). |
| `python scripts/dev/precheck.py --full` | **all NAMED groups, sequentially** (every fast + deep gate + the whole test suite split into halves). Emits per-group `PASS/FAIL` + duration + a rollup. *(The periodic release sweep is NOT included — BI-PF-0385.)* |
| `python scripts/dev/precheck.py --release` | `--full` **+** the periodic full-tree secret sweep (`secret-scan-all`). |
| `python scripts/dev/precheck.py --group <name>` | run exactly one named group. |
| `python scripts/dev/precheck.py --only a,b` | run a subset of named groups. |
| `python scripts/dev/precheck.py --list-groups` | print every group with its gate count / test count. |
| `python scripts/dev/precheck.py --tests-only` | only the changed-scoped tests (pre-push hook helper). |
| `python scripts/dev/precheck.py --tests-changed` | only the test files changed/added in this diff. |
| `python scripts/dev/precheck.py --scope a,b` | explicit test-name substrings for the scoped test step. |

Numeric aliases (kept from PR#210): `1`=all fast gates, `2`=deep, `3`=release, `4`=tests-a, `5`=tests-b.

**Tiers** (per gate, column 3 of `_GATES`): `fast` = every change; `deep` = merge/CI (`--full`);
`release` = periodic full-tree sweeps only (`--release`).

**Test scoping (BI-PF-0382/1340)**: the default test step runs only the tests affected by changed files
(`core/z.py` → `test_z.py` + tests importing `core.z`) plus a foundation smoke set; `--full` runs the whole
suite. New/untracked test files are always included.

## 2. Named groups (BI-PF-1419)

Every gate belongs to **exactly one** group (enforced by `test-framework/tests/pipeline/test_precheck_groups.py`).
A full run churns the groups in this order so the cheapest structural checks fail first:

| # | group | gates | measured time¹ | notes |
|---|---|---|---|---|
| 1 | `structure` | 13 | ~35.5s | compile / static hygiene / generated-doc freshness |
| 2 | `security` | 4 | ~1.1s | secrets / language rule / compliance / threat register |
| 3 | `contracts` | 16 | ~14.2s | API surface / contracts / public surfaces |
| 4 | `worker` | 5 | ~53.5s | leases / worktrees / worker layer (includes the Go build) |
| 5 | `backlog` | 11 | ~64.3s | SSOT invariants / DoD / grooming / staleness / trace |
| 6 | `quality` | 9 | ~54.0s | PIDL / validation engine / close-loop |
| 7 | `tests-a` | 108 files / 540 tests | ~317.7s | first half of the pipeline suite |
| 8 | `tests-b` | 108 files / 643 tests | ~161.1s | second half of the pipeline suite |
| 9 | `deep` | 8 | ~457.2s | dogfood / release / final-audit / backlog-e2e |
| 10 | `release` | 1 | (`--release` only) | full-tree secret sweep |
| — | `fast` (alias 1) | 58 | — | aggregate of every fast-tier gate |

¹ Indicative wall-clock from one `--full` run on a dev machine (develop `60441c4f`); total **≈ 19.5 min**
(excluding `release`). Treat as guidance, not a contract. Targets for further sub-splitting (>~4 min):
`tests-a`, `tests-b`, `deep`.

## 3. Gates by group (name · tier · owner script · purpose)

### structure (13)
- `compile` [fast] — `python -m compileall` over `core scripts dashboard api`.
- `pycompat` [fast] `scripts/dev/pycompat_check.py` — Python-version compatibility guard.
- `ci-cd-gates` [fast] `scripts/dev/ci_cd_gates_check.py` — CI/CD gate registry guard (BI-PF-1239).
- `wired-audit` [fast] `scripts/dev/wired_audit.py` — is every core module invoked on the runtime path?
- `store-contract` [fast] `scripts/dev/store_check.py` — store-registry rule, scoped to changed files.
- `lint` [fast] `scripts/dev/lint_check.py` — ruff, scoped to changed files (baseline-aware).
- `changed-tests` [fast] `scripts/dev/changed_tests_check.py` — a change to shipped/sensitive logic must add/update a test (BI-PF-1340).
- `workflow-matrix` [fast] `scripts/dev/workflow_matrix_check.py` — workflow combination matrix.
- `store-registry` [fast] `scripts/dev/store_registry_check.py` — store-registry completeness (BI-PF-1408/1409).
- `docs-fresh` [fast] `scripts/dev/check_docs_fresh.py` — generated docs are fresh (BI-PF-0258).
- `artifact-map` [fast] `scripts/dev/gen_artifact_map.py --check` — render+verify `docs/ARTIFACT-OWNERS.md`.
- `review-focus` [fast] `scripts/dev/gen_review_focus.py --check` — render+verify `docs/REVIEW-FOCUS.md`.
- `review-static` [fast] `scripts/dev/review_static_check.py` — non-LLM high-risk-pattern scan over changed files (advisory).

### security (4)
- `secret-scan` [fast] `scripts/dev/secret_scan.py` — blocking secret scan (diff-scoped; BI-0205/BI-PF-0385).
- `language-rule` [fast] `scripts/dev/language_rule_check.py` — A6 language rule + undeclared runtime deps (BI-PF-0395).
- `compliance-register` [fast] `scripts/dev/compliance_register_check.py --check` — compliance register + evidence (BI-PF-1206).
- `data-plane-threats` [fast] `scripts/dev/data_plane_threat_check.py --check` — data-plane threat register (EDP-04/BI-PF-1296).

### contracts (16)
- `api-contract` [fast] `scripts/dev/api_contract_check.py` — API contract checks for the canonical `api/` surface.
- `api-governance` [fast] `scripts/dev/api_governance_check.py` — committed OpenAPI must match the live app (API-5).
- `api-docs-regen` [fast] `scripts/dev/api_docs_check.py --write` — regenerate the committed API reference.
- `api-docs` [fast] `scripts/dev/api_docs_check.py` — verify the committed API reference matches the live OpenAPI (BI-PF-0355).
- `engineering-flow` [fast] `scripts/dev/engineering_flow_check.py` — ENG-0 architecture defined AND stitched.
- `task-contract` [fast] `scripts/dev/task_contract_check.py` — ENG-1 task-contract schema valid + exercised.
- `scheduler` [fast] `scripts/dev/scheduler_check.py` — ENG-2 planner/scheduler deterministic (no store writes).
- `reservations` [fast] `scripts/dev/reservations_check.py` — ENG-8 shared-path detection + advisory reservations.
- `packaging` [fast] `scripts/dev/packaging_check.py` — REL-0 edition package manifest fail-closed + distinct.
- `tool-catalog` [fast] `scripts/dev/tool_catalog_check.py` — tool catalog consistent; nothing ships non-bundle_allowed.
- `dependency-catalog` [fast] `scripts/dev/dependency_catalog_check.py` — a NEW dependency needs a catalog entry (BI-PF-0443).
- `api-first` [fast] `scripts/dev/api_first_check.py` — API-first enforcement (ADR-0007/0008, BI-PF-1404).
- `github` [fast] `scripts/dev/github_check.py` — ENG-5 PR orchestration + evidence + guards.
- `pf-surface` [fast] `scripts/dev/pf_surface_check.py` — the `/pf` command surface is thin + API-first.
- `wg-surface` [fast] `scripts/dev/wg_surface_check.py` — WorkerGrid `/wg` surface thin + producer contract present.
- `global-commands` [fast] `scripts/dev/sync_global_commands.py --check` — global commands match the checked-in source.

### worker (5)
- `lease` [fast] `scripts/dev/lease_check.py` — atomic claim + lease + recovery; single claimer (IS-PF-0034).
- `single-path` [fast] `scripts/dev/single_path_check.py` — one submission path; worker/scheduler layer decoupled out of PF.
- `vcs-worktree` [fast] `scripts/dev/vcs_worktree_check.py` — ENG-3 one git owner; worktree isolation + branch naming.
- `worker` [fast] `scripts/dev/worker_check.py` — ENG-4 worker runs a task in an isolated worktree + normalizes the result.
- `wg-go` [fast] `scripts/dev/wg_go_check.py` — WorkerGrid Go coordinator+agent build/vet/test (BI-PF-0412/0413/0414).

### backlog (11)
- `backlog-reconcile` [fast] `scripts/dev/backlog_id_reconcile.py --write` — renumber duplicate ids + fix references (BI-PF-0764).
- `backlog-context` [fast] `scripts/dev/backlog_context_check.py` — every OPEN item carries context; epics consistent (BI-PF-0448).
- `backlog-dod` [fast] `scripts/dev/backlog_dod_check.py` — hard DoD: detailed AC + independent verification (BI-PF-1410).
- `backlog-verification` [fast] `scripts/dev/backlog_verification_check.py` — independent-verification gate (BI-PF-1413).
- `backlog-ids` [fast] `scripts/dev/backlog_id_audit.py` — no duplicate ids in any scope (BI-PF-0457).
- `backlog-epic` [fast] `scripts/dev/backlog_epic_audit.py` — every NEW open item belongs to an epic (BI-PF-1250).
- `backlog-monotonic` [fast] `scripts/dev/backlog_monotonic_check.py` — a change must never regress the backlog.
- `backlog-write` [fast] `scripts/dev/backlog_write_guard.py` — backlog state written only via the sanctioned path (BI-PF-1327/WG-O3).
- `grooming` [fast] `scripts/dev/grooming_check.py` — grooming data-driven, AI-default, never blocks (PFSSOT-P2).
- `staleness` [fast] `scripts/dev/staleness_check.py` — architecture-version-aware analysis staleness + revalidation (BI-PF-0389).
- `intent-trace` [fast] `scripts/dev/intent_trace_check.py` — intent traceability / drift guard.

### quality (9)
- `dogfood-run` [fast] `scripts/dev/dogfood_run_check.py` — DOGFOOD Phase 1 (API auto-dogfood) (BI-PF-0458).
- `pidl` [fast] `scripts/dev/pidl_check.py` — PIDL-1 context resolver: relevant-subset, deterministic, read-only (BI-PF-0376).
- `pidl-gate` [fast] `scripts/dev/pidl_gate_check.py` — PIDL-3 worker-result decision gate, precedence-correct (BI-PF-0378).
- `pidl-synthesis` [fast] `scripts/dev/pidl_synthesis_check.py` — PIDL-4 pre-dispatch + cross-worker synthesis + consequential-action gate (BI-PF-0379).
- `pidl-trace` [fast] `scripts/dev/pidl_trace_check.py` — PIDL-5 approval policy + versioned trace + feedback (BI-PF-0380).
- `validation-engine` [fast] `scripts/dev/validation_engine_check.py` — ENG-6 Common Validation Engine runs profiles.
- `feature-pr` [fast] `scripts/dev/feature_pr_check.py` — ENG-7 FEATURE_PR validates an exact commit in a FRESH worktree.
- `merge-gate` [fast] `scripts/dev/merge_gate_check.py` — ENG-8 merge enforcement fail-closed.
- `rate-budget` [fast] `scripts/dev/rate_budget_check.py` — P12 provider rate budgeting + scheduler fairness.

### deep (8) — merge/CI (`--full`)
- `dogfood` [deep] `scripts/dev/dogfood_check.py` — ENG-9 DOGFOOD runs (dry) fail-closed, produce a final state.
- `dogfood-replay` [deep] `scripts/dev/dogfood_replay_check.py` — deterministic LLM replay (BI-PF-0459).
- `dogfood-schedule` [deep] `scripts/dev/dogfood_schedule_check.py` — dogfood schedule/tick idempotency/trends (BI-PF-0460).
- `repo-setup` [deep] `scripts/dev/repo_setup_check.py` — stage-0 repo setup recommend/confirm/create (fail-closed, hermetic).
- `docs-fresh-strict` [deep] `scripts/dev/check_docs_fresh.py --strict`.
- `release` [deep] `scripts/dev/release_check.py` — ENG-10 the release gate is fail-closed, never falsely green.
- `final-audit` [deep] `scripts/dev/final_audit_check.py` — production-readiness acceptance criteria (plan §42).
- `backlog-e2e` [deep] `scripts/dev/e2e_backlog_check.py` — E2E wiring check for the backlog backbone.

### release (1) — `--release` only
- `secret-scan-all` [release] `scripts/dev/secret_scan.py --all` — periodic full-tree secret sweep.

## 4. Test suite — counts & classification

The pipeline suite (`test-framework/tests/pipeline/`) runs as two halves in `--full`:

| group | files | tests | domain |
|---|---|---|---|
| `tests-a` | 108 | 540 | first half (API foundation/contracts, core, pipeline tests …) |
| `tests-b` | 108 | 643 | second half (backlog, validation, worker, dogfood …) |
| **total** | **216** | **1183** | full pipeline suite |

Classification by **gate**: behavioural/unit tests for each subsystem (api, backlog, validation, worker,
dogfood, pidl, packaging, licensing, events, …). The default fast tier runs only the **changed-scoped**
subset + smoke (`test_api_foundation.py`, `test_backlog_refs.py`, `test_main.py`).

## 5. Validation profiles (`config/validation-profiles.json`, ENG-6)

The Common Validation Engine (`core/validation_engine.py`) composes existing validators into named profiles.
`precheck` is the **local author gate**; these profiles are the engines the **delivery lane and CI** run.

| profile | target | purpose | checks | repair | promotion |
|---|---|---|---|---|---|
| `FEATURE_PR` (default) | pr | validate a change before merge | target, quality_gate, tests, policy, verification, pr_gate | no | merge-to-develop |
| `INTEGRATION` | integration | independently developed changes work together | … + cross_contract | no | promote-integration |
| `DOGFOOD` | baseline | prove complete end-to-end product-building capability | … + e2e | **yes** | none |
| `RELEASE` | release | qualify a release candidate | … + security | no | approve-release |

## 6. Dogfood and the other runs — what they do

- **Dogfood (ENG-9 / Phase 1, `dogfood_check.py`, `dogfood-run` gate).** Builds a **sample product end-to-end**
  from an idea through the pipeline using **dry/auto** runs, proving PF can actually *build* a product, not just
  pass unit tests. `dogfood-run` is the fast API auto-dogfood gate; `dogfood` (deep) runs the dry lifecycle to a
  final state; `dogfood-replay` proves the LLM steps are deterministic by replaying a recorded run; and
  `dogfood-schedule` checks the periodic dogfood schedule (due logic, tick idempotency, trend/regression).
- **FEATURE_PR profile** — the per-PR validation the delivery lane runs: resolve the target commit, run the
  quality gate + tests + policy + verification + PR gate in a **fresh worktree**, then merge to `develop`.
- **INTEGRATION profile** — validates that separately developed changes compose (adds `cross_contract`).
- **RELEASE profile** — qualifies a release candidate (adds `security`) before `approve-release`.
- **Scoped/fast runs** — the default precheck (changed-scoped) and `--tests-only` / `--tests-changed` are the
  author-time fast paths; `--full` is the merge/CI parity run.

---

*Generated/curated for BI-PF-1419. If the gate list or group membership changes, update `_GATES`/`_GROUP_OF` in
`scripts/dev/precheck.py` (the SSOT) and refresh this guide.*
