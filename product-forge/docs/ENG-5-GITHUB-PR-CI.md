# ENG-5 — GitHub / PR / CI Orchestration

**Phase:** ENG-5 of `PRODUCT_FORGE_MASTER_API_FIRST_ENGINEERING_FACTORY_E2E_EXECUTION_PLAN-updated.md` (§17)
**Status:** Implemented (orchestration core; remote via optional adapter) — gate PASS
**Depends on:** ENG-3 (git/worktree), ENG-4 (worker result), `core/pr_gate.py`, `core/close_loop.py`

## What this phase builds

GitHub owns the repository/branches/commits/PRs/reviews/CI/checks/merge state (§17, §28); Product Forge
orchestrates the lifecycle and records **run-bound PR evidence**. The `gh` CLI is an **optional adapter** — PF
degrades gracefully without it (a PR record is still produced as `pr_ready`).

```
core/github.py                       # PR/CI orchestration + PR evidence + append-only PR record store
  available()                        #   gh adapter availability (client only)
  build_evidence(...)               #   aggregates from canonical stores (no duplicates)
  create_pr(...)                    #   push-ready -> PR (guarded; degrades to local 'pr_ready')
  list_prs / get_pr / ci_status      #   PR lifecycle + CI status
  POLICY                             #   the "never" list
core/vcs.py                          # head_commit() read helper (one git owner)
api/routers/github.py                # /api/v1/github[...]
scripts/dev/github_check.py          # gate (in precheck)
config/engineering-flow.json         # pr, ci steps: planned -> partial
```

## Flow (plan §17)

```
Task → scheduler → worker → worktree → feature branch → implementation → commit → push → PR → CI
     → FEATURE_PR validation → review → required gates → merge → develop/integration
```

`create_pr` refuses to open a PR from a **protected** branch (`develop`/`main`) or when head == base; the
controlled merge goes through `core.vcs.merge(require_gate=True)` + `core.pr_gate.can_merge`.

## PR evidence (run-bound; assembled, never duplicated)

`build_evidence(project, project_dir, run_id, task_id, base_sha, head_sha, backlog_ref)` returns:

```text
run_id · task_id · commit_sha · base_sha · backlog
tests       <- core.qa_report.load (go/no-go + qir)
validation  <- core.close_loop.verify_run (run-bound)
artifacts   <- core.artifact_store summary
issues      <- core.issues.list_open
rcca        <- core.issues.list_closed with rcca
security    <- open high/critical risk|bug issues
```

The record stores an `evidence_hash` (tamper-evident); records are **append-only** (evidence is never altered).

## Never (encoded as `POLICY` + guards)

force-push shared branches · bypass required CI · disable tests for a pass · overwrite another worktree ·
silently retarget a validation run · alter evidence after the fact.

## API

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/github?scope&project` | adapter availability + PR records |
| GET | `/api/v1/github/evidence?scope&project&run_id&task_id&...` | run-bound evidence |
| POST | `/api/v1/github/pr` | create/push-ready PR (operator) |
| GET | `/api/v1/github/pr/{number}` | PR record |
| GET | `/api/v1/github/pr/{number}/ci` | CI status (adapter; `available:false` without `gh`) |

Store `pr-records.json` (owner `core/github.py`, kind evidence) is registered; no shadow store.

## 360° dependency check

- GitHub is external; PF keeps only the PR record + derived evidence — no duplicate of GitHub state.
- `gh` absence ⇒ `status: pr_ready` / `ci_status.available: false` — **never a hard dependency**.
- One new store, registered, single writer (append-only). No edits to `dashboard/` (frozen).
- Reachable from `scripts/dev/github_check.py` (precheck) so the invocation-audit stays green.
- ENG-0 gate verifies the `pr`/`ci` owner file exists and their routes are wired.

## Verification (executed)

```
python -m compileall -q api core scripts dashboard                # 0
python scripts/dev/wired_audit.py                                 # OK (unwired 0, naming 0)
python scripts/dev/api_contract_check.py                          # api-contract: OK
python scripts/dev/engineering_flow_check.py                      # OK (17 eng, 6 ingestion, 5 planned)
python scripts/dev/github_check.py                                # github: OK (adapter, evidence, PR record, guards)
python -m pytest test-framework/tests/pipeline -q -o addopts=""   # full suite green
python scripts/dev/precheck.py                                    # precheck: PASS
```

## Gate (plan §17)

| Criterion | Result |
|---|---|
| Push + PR orchestration (guarded) | ✅ `create_pr` (protected/head==base refused) |
| CI status via adapter | ✅ `ci_status` (optional `gh`; degrades) |
| Run-bound PR evidence from canonical stores | ✅ `build_evidence` + `evidence_hash` |
| Never-list enforced | ✅ `POLICY` + guards |
| Merge via controlled gate | ✅ `core.vcs.merge` + `pr_gate` |
| No shadow store; API-first; wired + exercised | ✅ `pr-records.json` + `/api/v1/github/*` + gate + tests |
| ENG-0 flow updated | ✅ `pr`, `ci`: planned → partial |

**ENG-5 GATE: PASS.** Next: **API-5 — API Hardening & Event Layer** (contract governance, canonical OpenAPI,
event API formalization), then **ENG-6 — Common Validation Engine**.
