---
description: "WorkerGrid command surface: /wg <verb>. verbs: serve, work, agent, status, register, list, unregister, schedule, recover, watch, adapters, dispatch, instruct, config. Thin adapter to workergrid/wg.py. WorkerGrid is the thin runtime host; PF owns assignment + delivery (ADR-0003)."
---

**NOTE:** **WorkerGrid** is a **thin runtime host** (not PF orchestration). Per **ADR-0003**, PF owns the
**assignment** (per-item claim/lease via `POST /engineering/assignments/claim`) and the **delivery**
(validate → PR → merge → push); WorkerGrid claims from PF, and by default (`MANUAL`) **this session acts as the
worker**: it works the assigned item in the worktree and ALWAYS asks you for approval at the gates.
`/wg work auto` runs the headless self-approving worker instead. This command is a **thin adapter**
to `workergrid/wg.py` (no orchestration logic). The coordinator (`/wg serve`) is a **fallback** for a producer
without the assignment API. Two planes never mix: the worker runs PF's **own** backlog (`product_forge`);
generated products use the PF pipeline. `/pf` has no worker/scheduler verbs — they live here.

$ARGUMENTS

## STEP 1: empty?
If `$ARGUMENTS` is empty/whitespace, run `python ../workergrid/wg.py help` (from `product-forge/`) and STOP.

## STEP 2: delegate
Run `python ../workergrid/wg.py $ARGUMENTS` from the `product-forge/` directory and report the output.
For verbs other than `work`, run and REPORT the JSON output.
For `work`, follow the **WORKER MODE PROTOCOL** below.

## WORKER MODE PROTOCOL (the 14 guidelines — binding at every gate)
- `/wg work [manual] [--epic ID]` (**MANUAL**, default): **this session is the worker.**
  1. Run `python ../workergrid/wg.py work [manual] [--epic ID]` → returns the atomic ASSIGNMENT PACKAGE
     (`item_id`, `worktree`, `branch`, `brief`, `objective`, `acceptance_criteria`, `in_scope/out_of_scope`,
     `epic`, `pidl_context`, `execution_policy`). PF holds the per-item lease.
  2. Work INSIDE the returned `worktree` path (absolute) on the returned `branch` — never the main checkout.
     Renew long runs with `python ../workergrid/wg.py work heartbeat <item_id>`.
  3. Follow the charter: **think → design → 360° check → backlog gate →** (any epic to update? backlog fields
     complete?) `→ RECONCILIATION block → IMPACT REVIEW table → plain-language summary + risks/mitigations`.
     Framework-agnostic: no specific AI-tool references in PF code; the current dashboard is legacy — never
     reference it.
  4. **PAUSE: ASK OPERATOR FOR APPROVAL** presenting the items above. Do NOT implement before approval.
     Nothing proceeds automatically without an explicit yes.
  5. On approval: implement end-to-end in the worktree (feature branch), wire + exercise everything, no
     shortcuts; raise issue → RCCA → backlog for any defect; extend existing functionality instead of
     shortcuts; design a new path only when needed (and ask for approval with details).
  6. Run lint + gates; then **PAUSE for operator approval to DELIVER**.
  7. On approval: commit in the worktree, then
     `python ../workergrid/wg.py work complete <item_id> --note "<summary>" [--usage-file .wg/usage.json]`
     → PF's delivery lane validates, opens the PR and merges to `develop`.
  8. If the operator instead says requeue/stop:
     `python ../workergrid/wg.py work release <item_id> --reason "..."` (keeps the branch), or
     `python ../workergrid/wg.py work fail <item_id> --reason "..."`.
- `/wg work auto [--epic ID] [--once]` → the **headless self-approving worker** (`wg-agent`): claim → runtime →
  complete/fail with no operator gate.
- `/wg watch [--epic ID] [--follow] [--lines N]` → live monitoring of active assignments + the worker journal.
- `/wg work claim-only [...]` → claim and return the package only (no session instructions).

## Other verbs
- `/wg status [--scope S] [--project P]` — active assignments from PF (workers ↔ items)
- `/wg schedule eligible|next|status [--scope S] [--project P] [--epic ID]` — query PF eligibility (epic-scoped)
- `/wg serve [--host H] [--port P]` — coordinator service (**fallback** only)
- `/wg register --runtime <r> [--caps a,b]` · `/wg list` · `/wg unregister <id>` · `/wg adapters` · `/wg dispatch [--force]`
- `/wg recover [--scope S] [--project P]` — free dead/stuck assignments + clean their worktrees
- `/wg instruct [<text>]` · `/wg config`

## Notes
- Manual is the DEFAULT (attended; every gate asks). Auto is the exception you opt into.
- Framework-agnostic boundary: PF never references a specific runtime or the legacy dashboard.
- Stale/orphaned runs self-heal: `agent.timeout_seconds` bounds runs; `wg recover` releases dead leases
  and cleans worktrees (`PF_LEASE_RECOVERY` policy).
