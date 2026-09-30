# Issue ⇄ Backlog Close-Loop — Design (BI-PF-0271)

## Goal
Implement the process exactly as specified: **raise issue → raise the paired backlog → record RCCA →
fix → close the loop back (backlog AND issue, recording where the fix was done)** — bidirectionally and
fail-closed. This closes the gap left by `BI-PF-0262`, where the pieces existed but the loop was not
wired end-to-end.

## 360° — current behaviour (verified in code)
| Step | Today | Gap |
|---|---|---|
| Raise issue | `issues.raise_issue` creates the finding | does **not** auto-raise the paired backlog item |
| Raise backlog | caller must pre-create + pass `backlog_ref` | not part of the issue path |
| Reciprocal link | `link_backlog` sets issue⇄backlog | `raise_issue` only links when `backlog_ref` given (fixed in BI-PF-0270) |
| RCCA | `issues.set_rcca` (root_cause/corrective/fixed_where/generalized) | ok |
| Close backlog | `backlog.set_status` gates on issue RCCA complete | one-way only |
| Close issue | `issues.set_status` requires RCCA complete | does **not** propagate to the backlog; `fixed_where` not stamped on backlog |

## Design (single loop, fail-closed, no new store)
**Owners unchanged:** `core/issues.py` owns issue state; `core/backlog.py` owns backlog state. Neither
writes the other's file directly — they call the other's public API (existing pattern in
`link_backlog`). One truth per concern preserved.

1. **Raise (one call):** `raise_issue(..., auto_backlog=True)` — when no `backlog_ref` is supplied,
   create the paired backlog item (`type="task"`, `tag` from scope, dedup-checked via
   `backlog.find_similar`, linked to the issue), then `link_backlog` 1:1. Default `auto_backlog=False`
   to keep existing callers unchanged; `ingest_defects` opts in.
2. **RCCA:** unchanged (`set_rcca`; generalized → learning; fail-closed `rcca_complete`).
3. **Close the loop (fixed):**
   - `issues.set_status(..., "closed")`: still fail-closed on RCCA; on success, **propagate** to the
     linked backlog item — `backlog.set_status(..., "completed")` and stamp
     `links.issue_closed=true` + `fixed_where` (from RCCA) onto the backlog item so "where the fix was
     done" is recorded on **both** sides.
   - `backlog.set_status(..., "completed")`: unchanged fail-closed gate (refuses until RCCA complete).
   - Propagation is idempotent and guarded (never raises into the caller); an explicit
     `propagate=True` default with `force` honored.
4. **Evidence on both sides:** issue.rcca.fixed_where ⇄ backlog.links.issue + `fixed_where` field.

## Acceptance / test (the exact user sequence, e2e)
`test_issue_close_loop.py`:
1. `raise_issue(..., auto_backlog=True)` ⇒ a backlog item exists and is linked 1:1 to the issue.
2. `backlog.set_status(completed)` before RCCA ⇒ **refused** (fail-closed).
3. `set_rcca(root_cause, corrective, fixed_where)` ⇒ issue RCCA complete.
4. `issues.set_status(closed)` ⇒ succeeds AND the linked backlog item is `completed` with
   `fixed_where` recorded.
5. Reverse: a fresh issue with incomplete RCCA ⇒ `backlog.set_status(completed)` refused.

## Gates
`compileall` · `wired_audit` · `workflow_matrix_check` · pipeline tests · `precheck`. Merge on
`feature/bi-pf-0271-close-loop`; close `BI-PF-0271` **through the gate** (proving the loop in prod).

## Out of scope
UI surfacing of the paired items (dashboard already reads `/api/v1/issues*`); auto-reopening.
