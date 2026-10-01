# ENG-3 — Git / Worktree / Branch Orchestration

**Phase:** ENG-3 of `PRODUCT_FORGE_MASTER_API_FIRST_ENGINEERING_FACTORY_E2E_EXECUTION_PLAN.md` (§15)
**Status:** Implemented (core primitives) — gate PASS
**Depends on:** ENG-2 (`docs/ENG-2-WORK-PLANNER-SCHEDULER.md`), ENG-0

> **Entry path (§2A):** git/worktree isolation serves the **direct engineering path** (Task/Work → worker).
> Intake is not involved.

## What this phase builds

Git is the source-control execution layer; workers must each get an **isolated** working directory and a
**feature branch**, and `develop`/`main` are never written directly. ENG-3 consolidates git into **one owner**
and adds the worktree/branch primitives the ENG-4 worker loop will use.

```
core/vcs.py                           # the ONE git owner (VCSManager) — extended, read+isolate
  feature_branch_name(area, task_id)  #   feature/<area>/<task-id>
  validation_branch_name(run_id)      #   validation/<run-id>
  is_protected(branch)                #   develop/main are protected (controlled merge only)
  worktree_root()                     #   sibling <repo>-worktrees/ (or git-config.json worktree_root)
  add_worktree(name, branch, base)    #   fresh worktree on a feature branch (fixes PF-050)
  list_worktrees() / remove_worktree()
  status() / branches() / commits ... #   (API-3 reads)
core/git_manager.py                   # REMOVED — the duplicate git manager (was unwired + buggy)
api/routers/vcs.py                    # GET /vcs/branch-name | /vcs/worktrees; POST /vcs/worktrees[/{name}/remove]
scripts/dev/vcs_worktree_check.py     # gate (in precheck)
config/engineering-flow.json          # worktree step: partial -> exists
```

## The worker git flow (plan §15)

```
Task → worker assignment → fresh worktree → feature branch → implementation → tests → commit → push
```

- **Feature branch:** `feature/<project-or-area>/<task-id>` (e.g. `feature/web-ui/tc-pf-0001`).
- **Validation branch:** `validation/<RUN_ID>`.
- **Never** commit to `develop`/`main` directly — only the controlled merge mechanism does (ENG-5). `is_protected()`
  reports this; the ENG-4 worker loop will refuse to start on a protected branch.
- **Isolation:** each worker gets its own worktree under `<repo>-worktrees/<name>/`; workers never share a
  mutable working directory.

## One git owner (consolidation)

| Before | After |
|---|---|
| `core/vcs.py` (canonical, wired) **and** `core/git_manager.py` (parallel, unwired, PF-050 bug) | `core/vcs.py` only |
| `capability_bridge.git_status` + `pipeline_capabilities` probe imported `GitManager` | both use `core.vcs.VCSManager` |
| `core/__init__` re-exported `GitManager` | removed |

**PF-050 (fixed):** the old `GitManager.create_worktree` called `create_branch(branch, create=True)` — a kwarg
that did not exist — so worktree creation always raised. `VCSManager.add_worktree` uses
`git worktree add -b <branch> <path> <base>` (or reuses an existing branch), with a base fallback
(`base → develop → current`). The gate explicitly exercises add/list/remove.

## API

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/vcs/branch-name?task_id&area&run_id` | feature/validation branch names |
| GET | `/api/v1/vcs/worktrees?project` | worktree root + list |
| POST | `/api/v1/vcs/worktrees` | create isolated worktree (operator) |
| POST | `/api/v1/vcs/worktrees/{name}/remove` | remove worktree (operator) |

## 360° dependency check

- No new store; `git-config.json` (owner `core/vcs.py`) is unchanged and already registered.
- Deleting `git_manager.py` removes a duplicate git manager (plan §41 "no third git manager"); its only
  importers were updated, and `wired_audit` stays green (unwired 0).
- No edits to `dashboard/` (frozen). Worktrees live outside the repo dir (sibling root) — never a shared dir.
- The ENG-0 architecture gate now verifies the `worktree` step's owner file exists and its route is wired.

## Verification (executed)

```
python -m compileall -q api core scripts dashboard                # 0
python scripts/dev/wired_audit.py                                 # OK (unwired 0, naming 0)
python scripts/dev/api_contract_check.py                          # api-contract: OK
python scripts/dev/engineering_flow_check.py                      # engineering-flow: OK (23 steps, 7 planned)
python scripts/dev/vcs_worktree_check.py                          # vcs-worktree: OK (naming, add/list/remove, isolation, protected)
python -m pytest test-framework/tests/pipeline -q -o addopts=""   # full suite green
python scripts/dev/precheck.py                                    # precheck: PASS
```

## Gate (plan §15)

| Criterion | Result |
|---|---|
| Git is the source-control execution layer, one owner | ✅ `core/vcs.py` (duplicate removed) |
| Fresh worktree + feature branch per task | ✅ `add_worktree` + naming helpers |
| Worker isolation (no shared mutable dir) | ✅ gate proves worktree/mains isolation |
| develop/main never written directly | ✅ `is_protected()` (+ enforced in ENG-4) |
| Worktree creation works (PF-050) | ✅ fixed + regression-tested |
| Exposed API-first + wired + exercised | ✅ `/api/v1/vcs/*` + gate + tests |
| ENG-0 flow updated | ✅ `worktree`: partial → exists |

**ENG-3 GATE: PASS.** Next: **ENG-4 — Worker Runtime and OpenCode Adapter** (claim a scheduled task in an
isolated worktree, execute, and report a normalized result — adapter/OpenCode is a client, never a dependency).
Push/PR/CI is **ENG-5**.
