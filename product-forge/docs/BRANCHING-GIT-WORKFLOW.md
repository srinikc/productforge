# Branching & Git Workflow (Product Forge)

End-to-end reference for **how git branching, worktrees, fetch/rebase/merge and push actually happen** — for
Product Forge itself, for generated products, and for the PF backlog whether it arrives via **intake** or is
executed by a **worker**.

Owner: `core/vcs.py` (`VCSManager`) is the single git primitive layer. `core/delivery.py` orchestrates worker
delivery. Nothing else shells out to `git` except the WorkerGrid agent (a separate, producer-agnostic plane).

---

## 0. Repos and scopes (the three things)

| Scope | Repo / working tree | Where |
|---|---|---|
| **PF itself** (`product_forge`) | one repo; toplevel = the checkout root, remote `srinikc/productforge` | `<repo-root>/` (contains `product-forge/` + `workergrid/`); PF's logical `ROOT` = `<repo-root>/product-forge` |
| **Generated product** (`project`) | its **own** repo per product | `products/<project>/` (git-init'd by the pipeline) |
| **WorkerGrid** | part of the PF repo (`workergrid/`) | `<repo-root>/workergrid/` |

> **ROOT vs repo toplevel:** `core.paths.ROOT` = the `product-forge` directory, but git's repo toplevel is the
> checkout root above it. Git `HEAD`/branch is **global to the checkout**, so checking out a branch anywhere
> under it switches the whole repo (IS-PF-0036). This is why worker delivery never checks out the live tree.

Branch names:
- integration branch: `develop` (config `integration_branch`)
- release branch: `release` (config `release_branch`)
- protected: `is_protected()` (develop/release/main)

---

## 1. The git primitive layer — `core/vcs.py` (`VCSManager`)

Every git operation goes through `VCSManager(project_dir, config)`:

| Method | What it does |
|---|---|
| `is_repo()` | `git rev-parse --is-inside-work-tree` |
| `init()` | `git init` + identity + `checkout -b release` + empty commit + `ensure_develop()` |
| `ensure_develop()` | creates the `develop` (integration) branch if missing |
| `feature_branch(name, base=None)` | `checkout develop` then `checkout -b name` (base = `develop` by default) |
| `checkout(branch)` | switch branch in the working tree |
| `commit(msg, paths)` | `git add` (+ commit) |
| `fetch()` | `git fetch <remote> --prune` (no-op if no remote) |
| `base_ref(base="")` | new-branch base: explicit `base` → **`origin/develop`** (after fetch) → local `develop` |
| `reremote_ref()` | `origin/develop` |
| `pull`/`sync(push, integration)` | fetch + fast-forward/merge integration + **push gated by `PF_AUTO_PUSH`** (default off) |
| `push(branch, set_upstream)` | `git push -u origin <branch>` |
| `rebase(onto)` | `git rebase <onto>`; returns `{ok, conflicts}` |
| `merge(source, target, msg, require_gate=True)` | **`pr_gate.can_merge` gate** → `checkout target` → `merge --no-ff source` |
| `has_conflicts()` | unmerged paths (after a failed rebase/merge) |
| `worktree_root()` | sibling dir `<project_dir>-worktrees` (or `git-config.json:worktree_root`) |
| `add_worktree(name, branch, base)` | `git worktree add` on a feature branch (base = `origin/<integration>` preferred) |
| `remove_worktree(name)` / `list_worktrees()` | `git worktree remove --force` + `prune` / list |
| `is_protected(branch)` | protected-branch guard (PR refuses a protected head) |
| `feature_branch_name(area, id)` / `validation_branch_name(run_id)` | branch name helpers |

Repo-root `.gitattributes` pins `*.go`, `go.mod`, `go.sum` to **LF** (Windows `autocrlf` would otherwise
re-introduce CRLF and break `gofmt`).

---

## 2. Flow A — generated product (scope `project`): the PF pipeline

**This is the product-building path. Workers are NOT used here (BI-PF-0427).**

```
intake / idea / new project
   │  core/intake_channels.py  ->  run_entry.enqueue(project, item_id=<backlog item>)   (job_manager queue)
   ▼
job_manager pipeline-run queue (one run per project; max_parallel_projects)
   ▼
core/pipeline_executor.py  (execute_pipeline)  — runs the stage agents
   │  for each stage:
   │     v = VCSManager(project_dir)            # products/<project>/  (its own repo)
   │     v.init()                               # git init + release + develop   (first run only)
   │     v.feature_branch(f"feat/stage-<id>-<ts>")   # off develop
   │     …stage writes output…
   │     v.commit("feat(stage-<id>): pipeline output")
   │     v.push(br)
   │     v.merge(br, v.integration_branch)      # checkout develop + merge --no-ff  (pr_gate gated)
   ▼
end of run:
   v.push(current)                              # develop
   v.merge(develop, v.release_branch)           # integration -> release
   v.push(release)
   ▼
close_loop.verify_and_close -> backlog item closed (evidence linked)
```

Calls: `pipeline_executor.py:1561` (`VCSManager`), `:1574 init`, `:1575 feature_branch`,
`:1586 commit`, `:1587 push`, `:1588 merge`, `:1640 merge → release`, `:1643 push`.

---

## 3. Flow B — PF's own backlog via **intake → PF pipeline** (scope `product_forge`)

Same pipeline as A, but `project_dir` = **PF's ROOT**:

```
intake (CustomGPT / web / ideas / API)  ->  backlog item (BI-PF-*)
   │  run_entry.enqueue  (job_manager pipeline-run queue)
   ▼
pipeline_executor on PF ROOT  ->  per-stage feat/stage-* branches  ->  merge into PF `develop`  ->  push
```

This path performs checkouts/merges **in the PF working tree** (ROOT), run under the `run_entry` lock. It is the
"build/change PF via its own pipeline" path.

---

## 4. Flow C — PF's own backlog via the **WORKER** (the new path)

**Scope-restricted to `product_forge` (BI-PF-0427).** The live tree (ROOT) is **never** checked out.

```
/wg work  (WorkerGrid, an opencode session drives it)
   │  GET /engineering/schedule/next?stage=execute&scope=product_forge   (eligibility)
   │  POST /engineering/assignments/claim                                (job_manager.claim_next, per-item lease)
   ▼
PF creates a worktree folder:
   <ROOT>-worktrees/assign-<item>/       branch  wg/<item>   (off `origin/develop` via base_ref)
   ▼
runtime (opencode run …) works + commits **inside that worktree**       (ROOT untouched)
   │  heartbeats: POST /assignments/<item>/heartbeat  (renew_lease)
   ▼
POST /assignments/<item>/complete  ->  status = verifying   (lease cleared)
   │  api/routers/engineering.py -> BackgroundTasks -> core/delivery.deliver
   ▼
DELIVERY LANE  (core/delivery.py; one landing at a time — repo lock)
   1. v.push(branch)                                  # publish wg/<item>
   2. github.create_pr(...)                           # PR (real with `gh`)
   3. validation_engine.feature_pr(...)               # runs in its OWN validation/<run> worktree
   4. LANDING (never checks out the live tree):
        • gh available + PR #:  gh pr merge <n> --merge --delete-branch     ← develop advances on GitHub
        • else (no gh):  temp <ROOT>-worktrees/integrate-<item>/  off origin/develop
                         -> git merge --no-ff wg/<item>
                         -> run_quality_gate (fast re-verify)
                         -> git push origin HEAD:develop
                         -> remove the temp worktree
   5. backlog.set_delivery(branch, merge_sha, pr, pr_url) + set_status(completed)
```

Fail-closed: validation not `PASS`, a rebase conflict, or a failed gate → status **blocked** (never merged).

Calls: `api/routers/engineering.py` (`/assignments/claim`, `/complete`), `core/job_manager.py`
(`claim_next`, `renew_lease`, `release`, `complete`, `fail`), `core/delivery.py` (`deliver`, `_land`),
`core/vcs.py` (`add_worktree`, `fetch`, `base_ref`, `push`), `core/validation_engine.py` (`feature_pr`),
`core/github.py` (`create_pr`).

---

## 5. Flow D — an agent/session DoD change to PF (how *this* repo is normally changed)

What the engineer/agent does (AGENTS.md Definition of Done):

```
1. git checkout -b <feature-branch> off develop
2. implement (one concern) + tests
3. python scripts/dev/precheck.py            # compile, wired-audit, api-contract/governance, tests …
4. link evidence on the backlog item
5. git checkout develop ; git merge --no-ff <feature-branch>   # controlled merge
6. push origin develop
7. core.backlog.set_delivery(branch, merge_sha, pr, pr_url)     # closes the traceability loop
```

(This is the path you and I use for the `BI-PF-*` items; the worker path (Flow C) automates it.)

---

## 6. Worktrees (where the folders are)

- `worktree_root()` = **sibling** of the project dir: `<project_dir>-worktrees/` (e.g.
  `<repo-root>/product-forge-worktrees` for PF; `products/<project>-worktrees` for a product).
- Named worktrees created by the system:

| Folder | Branch | Created by | Purpose |
|---|---|---|---|
| `assign-<item>/` | `wg/<item>` | worker claim | the runtime works here |
| `validate-<run>/` | `validation/<run>` | `validation_engine.feature_pr` | isolated validation (removed after) |
| `integrate-<item>/` | `integrate/<item>` | `delivery._land` fallback | merged landing, pushed as `develop` (removed after) |
| `dogfood-<rid>/` | `dogfood/<rid>` | `core/dogfood.py` | dogfood run |

**IS-PF-0036 (one working tree per session/execution):** never run two things in the **same** working tree —
git `HEAD`/branch is global. Each session/run gets its **own clone or worktree**. The worker runtime, the
validation run and the integration landing each use their own worktree; the live ROOT is never switched.

---

## 7. Fetch, rebase, merge, conflicts

- **Fresh base**: `base_ref()` prefers **`origin/develop`** (fetched) so cross-system work never branches off a
  stale local `develop`. New worktrees start from that.
- **Merge gate**: `vcs.merge(source, target)` calls **`core/pr_gate.can_merge`** first; if unmet it returns
  `{blocked: true}` and does **not** merge (fail-closed).
- **Rebase conflicts**: `vcs.rebase(onto)` returns `{ok, conflicts}`; when `has_conflicts()` is non-empty the
  landing **blocks** the item (`status=blocked`) rather than merging.
- **Merge conflicts** (fallback landing): `git merge --no-ff` non-zero → blocked.
- **Fast re-verify** after a rebase/merge in the fallback landing: `core/run_quality_gate.evaluate` (compileall
  + wired_audit) on the merged tree; failure → blocked.
- **PR merge (primary landing)**: `gh pr merge --merge --delete-branch` — GitHub merges server-side (respects
  branch protection if enabled), `develop` advances remotely, the PR closes.
- **Sync**: `VCSManager.sync()` = fetch + merge integration + **push gated by `PF_AUTO_PUSH`** (default off);
  surfaced as `/pf sync`.

---

## 8. Branch reference

| Branch | Created by | Base | Merged into | Notes |
|---|---|---|---|---|
| `develop` | `vcs.init` / `ensure_develop` | — | — | the integration branch |
| `release` | `vcs.init` | — | — | release branch (`develop → release` on release) |
| `feat/stage-<id>-<ts>` | pipeline_executor | develop | develop | one per pipeline stage |
| `wg/<item>` | worker claim (`add_worktree`) | origin/develop | develop (via landing) | the worker's change |
| `validation/<run>` | validation_engine (`add_worktree`) | target SHA | — | throwaway; removed after |
| `integrate/<item>` | delivery fallback (`add_worktree`) | origin/develop | develop (`push HEAD:develop`) | throwaway |
| `dogfood/<rid>` | dogfood | base SHA | — | throwaway |
| `<feature>` (DoD) | agent/session | develop | develop (`merge --no-ff`) | human/agent change |

---

## 9. Invariants

1. **One git primitive layer** (`core/vcs.py`); no other module calls `git` except the WorkerGrid agent.
2. **Never commit to `develop`/`release` directly** (feature branch → merge).
3. **One working tree per session/execution** (IS-PF-0036); worker/validation/landing all use their own.
4. **The live tree is never checked out by delivery** (gh merge, or integrate-worktree push-ref).
5. **Fail-closed**: gate unmet / conflict / re-verify fail → `blocked`, never merged.
6. **`.gitattributes`** pins Go files to LF.
7. **Delivery provenance** is written back to the item (`core.backlog.set_delivery`).
8. **Scope**: the worker path is `product_forge`-only (BI-PF-0427); generated products build via the pipeline.
