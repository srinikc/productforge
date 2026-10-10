---
description: "WorkerGrid command surface (GLOBAL): /wg <verb>. verbs: serve, work, agent, status, register, list, unregister, schedule, recover, watch, adapters, dispatch, instruct, config. Thin adapter to workergrid/wg.py (no logic here). WorkerGrid is the thin runtime host; PF owns assignment + delivery (ADR-0003). Available in every opencode session."
agent: build
---

**NOTE:** **WorkerGrid** is a **thin runtime host** (not PF orchestration). Per **ADR-0003**, PF owns the
**assignment** (per-item claim/lease via `POST /engineering/assignments/claim`) and the **delivery**
(validate → PR → merge → push); WorkerGrid claims from PF, and by default (`MANUAL`) **this session acts as the
worker**: it works the assigned item in the worktree and ALWAYS asks you for approval at the gates.
`/wg work auto` runs the headless self-approving worker instead. This command is a **thin adapter** to
`workergrid/wg.py` (no orchestration logic). The coordinator (`/wg serve`) is a **fallback** for a producer
without the assignment API. Two planes never mix: the worker runs PF's **own** backlog (`product_forge`);
generated products use the PF pipeline. `/pf` has no worker/scheduler verbs — they live here.

**SOURCE OF TRUTH:** `product-forge/.opencode/command_global/wg.md` — keep the installed copy at
`~/.config/opencode/command/wg.md` byte-identical.

$ARGUMENTS

## STEP 0: resolve wg.py (self-locating — no installer)
Resolve `$WGSCRIPT` = the FIRST path below for which `Test-Path` returns `True`:
1. `$env:WORKERGRID_ROOT\wg.py` — explicit override (set the `WORKERGRID_ROOT` env var if you use one)
2. Known checkout: `C:\Users\ADMIN\Documents\Srinikc\AI Products\Exploring\PF-validation\workergrid\wg.py`
3. Discovery from the current directory: for each parent up to 5 levels:
   `<parent>\workergrid\wg.py`

If NONE exist → STOP. Report: "WorkerGrid not found — set `WORKERGRID_ROOT` to your workergrid folder."
If one exists → continue and use `$WGSCRIPT` in STEP 1/2.

## STEP 1: empty?
If `$ARGUMENTS` is empty/whitespace, run `python "$WGSCRIPT" help` and STOP.

## STEP 2: delegate
Run `python "$WGSCRIPT" $ARGUMENTS` (paths shown are relative to the `workergrid/` directory).
For verbs other than `work`, run and REPORT the JSON output.
For `work`, follow the **WORKER MODE PROTOCOL** below.

## WORKER MODE PROTOCOL (the 14 guidelines — binding at every gate)
- `/wg work [manual] [--epic ID]` (**MANUAL**, default): **this session is the worker.**
  1. Run `python "$WGSCRIPT" work [manual] [--epic ID]` → returns the atomic ASSIGNMENT PACKAGE
     (`item_id`, `worktree`, `branch`, `brief`, `objective`, `acceptance_criteria`, `in_scope/out_of_scope`,
     `epic`, `pidl_context`, `execution_policy`). PF holds the per-item lease.
  2. Work INSIDE the returned `worktree` path (absolute) on the returned `branch` — never the main checkout.
     Renew long runs with `python "$WGSCRIPT" work heartbeat <item_id>`.
  3. Follow the charter: **think → design → 360° check → backlog gate →** (any epic to update? backlog fields
     complete?) `→ RECONCILIATION block (PRIOR DECISIONS / EXISTING PATH / ASSUMPTIONS / DIVERGENCES / OPEN
     QUESTIONS) → IMPACT REVIEW table → plain-language functionality summary + risks/mitigations`.
     Framework-agnostic: no specific AI-tool references in PF code; the current dashboard is legacy — never
     reference it.
  4. **PAUSE: ASK OPERATOR FOR APPROVAL** presenting the items above. Do NOT implement before approval.
     Nothing proceeds automatically without an explicit yes.
  5. On approval: implement end-to-end in the worktree (feature branch), wire + exercise everything, no
     shortcuts; raise issue → RCCA → backlog for any defect; extend existing functionality instead of
     shortcuts; design a new path only when needed (and ask for approval with details).
  6. Run lint + gates; then **PAUSE for operator approval to DELIVER**.
  7. On approval: commit in the worktree, then
     `python "$WGSCRIPT" work complete <item_id> --note "<summary>" [--usage-file .wg/usage.json]`
     → PF's delivery lane validates, opens the PR and merges to `develop`.
  8. If the operator instead says requeue/stop:
     `python "$WGSCRIPT" work release <item_id> --reason "..."` (keeps the branch), or
     `python "$WGSCRIPT" work fail <item_id> --reason "..."`.
- `/wg work auto [--epic ID] [--once]` → the **headless self-approving worker** (`wg-agent`): claim → runtime →
  complete/fail with no operator gate (use when you want it to proceed automatically).
- `/wg watch [--epic ID] [--follow] [--lines N]` → live monitoring of active assignments + the worker journal.
- `/wg work claim-only [...]` → claim and return the package only (no session instructions).

## Other verbs
- `/wg status [--scope S] [--project P]` — active assignments from PF (workers ↔ items)
- `/wg serve [--host H] [--port P]` — coordinator service (**fallback** only; not needed for PF)
- `/wg schedule eligible|next|status [--scope S] [--project P] [--epic ID]` — query PF eligibility (epic-scoped)
- `/wg register --runtime <r> [--caps a,b]` · `/wg list` · `/wg unregister <id>` — coordinator-mode worker registry
- `/wg adapters` · `/wg dispatch [--force]` — coordinator-mode
- `/wg recover [--scope S] [--project P]` — free dead/stuck assignments + clean their worktrees
- `/wg instruct` (show shared worker instructions) · `/wg instruct <text>` (append; `workergrid/instructions.md`)
- `/wg config` (resolved config + paths)

## Notes
- Manual is the DEFAULT (attended; every gate asks). Auto is the exception you opt into.
- Framework-agnostic boundary: PF never references a specific runtime or the legacy dashboard.
- Stale/orphaned runs self-heal: `agent.timeout_seconds` bounds runs, and `wg recover` releases dead leases
  and cleans worktrees (`PF_LEASE_RECOVERY` policy).
