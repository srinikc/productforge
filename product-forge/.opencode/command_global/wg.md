---
description: "WorkerGrid command surface (GLOBAL): /wg <verb>. verbs: serve, agent, register, list, status, unregister, work, schedule, adapters, dispatch, instruct, config. Thin adapter to workergrid/wg.py (no logic here). Separate from Product Forge. Available in every opencode session."
agent: build
---

**NOTE:** **WorkerGrid** is a separate, producer-agnostic **execution plane** (not PF). This command is a
**thin adapter** to `workergrid/wg.py` (a sibling of `product-forge/`). It contains **no orchestration
logic**. `/pf` no longer has worker/scheduler verbs — they live here.

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
- `/wg serve [--host H] [--port P]` (run the coordinator service; shared state for all workers)
- `/wg agent [--runtime R] [--worker-id W] [--scope S] [--project P] [--once]` (run the worker agent loop: claim → worktree → execute → write-back)
- `/wg register --runtime <r> [--caps a,b]` · `/wg list` · `/wg status [<id>]` · `/wg unregister <id>`
- `/wg work [--worker W] [--runtime R] [--scope S] [--project P]`
- `/wg schedule eligible|next|status`
- `/wg adapters` · `/wg dispatch [--force]`
- `/wg instruct` (show shared worker instructions) · `/wg instruct <text>` (append; `workergrid/instructions.md`)
- `/wg config`
