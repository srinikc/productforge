---
description: "WorkerGrid command surface (GLOBAL): /wg <verb>. verbs: serve, work, agent, status, register, list, unregister, schedule, adapters, dispatch, instruct, config. Thin adapter to workergrid/wg.py (no logic here). WorkerGrid is the thin runtime host; PF owns assignment + delivery (ADR-0003). Available in every opencode session."
agent: build
---

**NOTE:** **WorkerGrid** is a **thin runtime host** (not PF orchestration). Per **ADR-0003**, PF owns the
**assignment** (per-item claim/lease) and the **delivery** (validate → PR → merge → push); WorkerGrid claims from
PF, runs the runtime in PF's worktree, and reports back. This command is a **thin adapter** to `workergrid/wg.py`
(no orchestration logic). The coordinator (`/wg serve`) is a **fallback** for a producer without the assignment
API. Two planes never mix: the worker runs PF's **own** backlog (`product_forge`); generated products use the PF
pipeline. `/pf` no longer has worker/scheduler verbs — they live here.

**SOURCE OF TRUTH:** `product-forge/.opencode/command_global/wg.md` — keep the installed copy at
`~/.config/opencode/command/wg.md` byte-identical.

$ARGUMENTS

## STEP 0: resolve wg.py (self-locating — no installer)
Resolve `$WGSCRIPT` = the FIRST path below for which `Test-Path` returns `True`:
1. `$env:WORKERGRID_ROOT\wg.py` — explicit override (set the `WORKERGRID_ROOT` env var if you use one)
2. Known checkout: `C:\Users\ADMIN\Documents\Srinikc\AI Products\Exploring\workergrid\wg.py`
3. Discovery from the current directory: for each parent up to 5 levels:
   `<parent>\workergrid\wg.py`

If NONE exist → STOP. Report: "WorkerGrid not found — set `WORKERGRID_ROOT` to your workergrid folder."
If one exists → continue and use `$WGSCRIPT` in STEP 1/2.

## STEP 1: empty?
If `$ARGUMENTS` is empty/whitespace, run `python "$WGSCRIPT" help` and STOP.

## STEP 2: delegate
Run `python "$WGSCRIPT" $ARGUMENTS` and report the output.

## Verb map
- `/wg work [--runtime R] [--worker-id W] [--scope S] [--project P] [--epic ID] [--once]` — **run the worker** (claim from PF →
  run the runtime in PF's worktree → complete/fail; loop; `--once` = one item). `--claim-only` = claim only.
- `/wg status [--scope S] [--project P]` — active assignments from PF (`GET /engineering/assignments`, workers ↔ items)
- `/wg agent …` — alias of the worker loop (legacy)
- `/wg serve [--host H] [--port P]` — coordinator service (**fallback** only; not needed for PF)
- `/wg schedule eligible|next|status [--scope S] [--project P] [--epic ID]` — query PF eligibility (epic-scoped)
- `/wg register --runtime <r> [--caps a,b]` · `/wg list` · `/wg unregister <id>` — coordinator-mode worker registry
- `/wg adapters` · `/wg dispatch [--force]` — coordinator-mode
- `/wg instruct` (show shared worker instructions) · `/wg instruct <text>` (append; `workergrid/instructions.md`)
- `/wg config` (resolved config + paths)

## Notes
- Worker mode: `agent.contract` = `auto` (default; PF mode when the assignment API is reachable) | `pf-assignments`
  | `coordinator` (fallback). See `docs/BRANCHING-GIT-WORKFLOW.md` §4 and ADR-0003.
