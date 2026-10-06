# PIDL-5 — Approval Policy + Feedback + Versioned Traceability + API/CLI

**Item:** BI-PF-0380 (epic BI-PF-0375) · `core/pidl.py` + `core/learning_synth.py` + API/CLI

Completes PIDL (doc implementation order #9–#11 + the versioning/traceability section): centralized approval
policy, controlled outcome/correction feedback, and the append-only decision trace that makes every decision
explainable.

## Approval policy

`config/approval-policy.json` (owner `core/pidl.py`): action/area rules decide whether authenticated human
approval is required. `pidl.approval_policy(action/area/components)` is consulted by `decide()`/`gate()`, so
`decision.approval.required` reflects both the consequential signal and the configured policy. Approvals are
recorded via `POST /engineering/pidl/approvals/{decision_id}` (`require_operator`).

## Versioned traceability

`data/pidl/decisions.jsonl` (owner `core/pidl.py`, append-only, single writer). Every decision records
`decision_id`, `decision_version`, `pidl_profile_version`, `worker_id`/`runtime`, `evidence`, `confidence`,
`risk`, `approval` (policy ref), and `outcome` — so an old decision stays explainable after the profile
changes. `record_decision()` is invoked on the real path by `core/close_loop` (the PIDL-3 gate). Read via
`history()`, `get()`, `latest()`.

## Controlled outcome/correction feedback

`pidl.record_outcome(decision_id, outcome, corrections)` appends to the trace and turns each correction into
an **evidence-gated candidate** via the new `learning_synth.add_candidate()` (idempotent) — it **never**
creates a rule directly. Promotion stays the existing `learning_synth.approve/reject` flow
(`data/learning-candidates.json`). No silent rule creation.

## API / CLI visibility

- `GET /engineering/pidl/decisions`, `/decisions/{id}`, `/candidates`, `/policy`
- `POST /engineering/pidl/decisions/{id}/outcome`, `/approvals/{id}` (operator)
- CLI: `pf pidl decisions|show <id>|latest <id>|candidates|policy`

Dashboard is frozen; visibility is API + CLI (item records `dashboard_impact=no`).

## Verification

```
python scripts/dev/pidl_trace_check.py   # approval policy, versioned trace, corrections->candidates, wired
```
