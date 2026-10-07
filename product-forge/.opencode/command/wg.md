---
description: "WorkerGrid command surface: /wg <verb>. verbs: serve, register, list, status, unregister, work, schedule, adapters, dispatch, instruct, config. Thin adapter to workergrid/wg.py (external execution plane; separate from PF)."
agent: orchestrator
model: opencode-go/mimo-v2.5
---

**NOTE:** WorkerGrid is a **separate, producer-agnostic execution plane** (not PF). This command is a **thin
adapter** to `workergrid/wg.py` at the repo root (sibling of `product-forge/`). WorkerGrid reads work from
Product Forge's **backlog API** and assigns it to workers. It contains **no orchestration logic** itself.

$ARGUMENTS

## STEP 1: empty?
If `$ARGUMENTS` is empty/whitespace, run the CLI with `help` and STOP.

## STEP 2: delegate
Run the WorkerGrid CLI with the given arguments, e.g. from the repo root:
`python workergrid/wg.py $ARGUMENTS`
(or from `product-forge/`: `python ../workergrid/wg.py $ARGUMENTS`).

## Verb map
- `/wg serve [--host H] [--port P]` (run the coordinator service; shared state for all workers)
- `/wg register --runtime <r> [--caps a,b]` · `/wg list` · `/wg status [<id>]` · `/wg unregister <id>`
- `/wg work [--worker W] [--runtime R] [--scope S] [--project P]`
- `/wg schedule eligible|next|status [--scope S] [--project P]`
- `/wg adapters` · `/wg dispatch [--force]`
- `/wg instruct` (show shared worker instructions) · `/wg instruct <text>` (append; file: `workergrid/instructions.md`)
- `/wg config` (resolved config + paths)

## Notes
- **Instructions** live in `workergrid/instructions.md` — edit any time (`/wg instruct`).
- Worker/scheduler verbs were **moved out of `/pf`** into `/wg`.
