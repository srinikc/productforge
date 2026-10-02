# FULL DOGFOOD + FINAL AUDIT

**Phases:** FULL DOGFOOD + FINAL AUDIT (plan §26/§40/§42)
**Status:** Implemented (lifecycle harness + acceptance audit) — gate PASS
**Depends on:** all prior phases (MASTER-0 … REL-0)

## What this builds

The closing gate: a full-lifecycle exercise plus a mechanical audit of the program's acceptance criteria.

```
core/e2e_lifecycle.py            # walks the canonical chain on a scratch product (task -> ... -> packaging -> audit)
core/audit.py                    # mechanical §42 acceptance audit + §41 "must-not-build" invariants
api/routers/audit.py             # GET /audit/acceptance|/readiness ; POST /audit/e2e
scripts/dev/final_audit_check.py # gate (in precheck)
```

## FULL DOGFOOD lifecycle (§26/§40)

`core.e2e_lifecycle.run()` drives, on a real scratch product, the canonical owners:

```
engineering_task (task_contract) -> scheduler -> worker/worktree (vcs) -> validation (validation_engine)
  -> integration (merge_gate) -> dogfood -> release (gate) -> packaging -> audit (§42)
```

- **Entry** is the engineering task contract (never intake as a prerequisite — §2A).
- **Fail-closed:** dry runs report `PARTIAL_SUCCESS`, never a false `PASS`; real runs require every stage to succeed.
- Scratch state is isolated under `products/_e2e_<id>/` and removed after.

## FINAL AUDIT (§42)

`core.audit.run()` evaluates the program acceptance criteria across:

| area | checked |
|---|---|
| API | /api/v1, OpenAPI, auth, correlation IDs, idempotency, events, compatibility policy |
| Runtime | run entry, pipeline executor, task lifecycle, artifact/evidence, store registry |
| Engineering | task contract, scheduler, dependency graph, elastic workers, worktree, branch, normalized result |
| GitHub | PR, exact-commit, CI, evidence, merge gate, integration queue |
| Validation | one engine + FEATURE_PR/INTEGRATION/DOGFOOD/RELEASE + no-false-green + run-bound + RCCA |
| Release | package, provenance, licensing/entitlement, deployment, rollback/upgrade |
| Clients | OpenCode/MCP/CLI adapters, dashboard via API/events, no client owns state |
| Invariants | §41 must-not-build (single executor/engine/backlog/defect/artifact/event/git) |

`production_ready = no unmet criteria`.

## API

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/audit/acceptance` | full §42 audit (all criteria) |
| GET | `/api/v1/audit/readiness` | summary (`production_ready`, passed/total, unmet) |
| POST | `/api/v1/audit/e2e` | run the full lifecycle (operator; `dry` default true) |

## 360° dependency check

- Reuses every canonical owner; **no new engine, no new store** (single-writer registry untouched).
- The audit is deterministic and file/owner-based; the lifecycle runs scrubbed scratch state.
- Commercial decisions remain human-governed; the audit only checks capability existence/wiring.

## Verification (executed)

```
python -m compileall -q api core scripts        # 0
python scripts/dev/final_audit_check.py         # OK (acceptance 52/52, production_ready, lifecycle 9 stages)
python scripts/dev/precheck.py                  # PASS
```

**FULL DOGFOOD + FINAL AUDIT GATE: PASS — program acceptance criteria met.**
