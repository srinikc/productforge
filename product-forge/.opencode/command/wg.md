---
description: "WorkerGrid command surface: /wg <verb>. verbs: serve, work, agent, status, register, list, unregister, schedule, adapters, dispatch, instruct, config. Thin adapter to workergrid/wg.py. WorkerGrid is the thin runtime host; PF owns assignment + delivery (ADR-0003)."
agent: orchestrator
model: opencode-go/mimo-v2.5
---

**NOTE:** **WorkerGrid** is a **thin runtime host** (not PF orchestration). Per **ADR-0003**, PF owns the
**assignment** (per-item claim/lease over `item.execution{}`) and the **delivery** (validate → PR → merge → push);
WorkerGrid claims from PF, runs the runtime in PF's worktree, and reports back. This command is a **thin adapter**
to `workergrid/wg.py`. The coordinator (`/wg serve`) is a **fallback** for a producer without the assignment API.
Two planes never mix: the worker runs PF's **own** backlog (`product_forge`); generated products use the PF pipeline.

$ARGUMENTS

## STEP 1: empty?
If `$ARGUMENTS` is empty/whitespace, run the CLI with `help` and STOP.

## STEP 2: delegate
Run the WorkerGrid CLI with the given arguments, e.g. from the repo root:
`python workergrid/wg.py $ARGUMENTS`
(or from `product-forge/`: `python ../workergrid/wg.py $ARGUMENTS`).

## Verb map
- `/wg work [--runtime R] [--worker-id W] [--scope S] [--project P] [--once]` — **run the worker** (claim from PF →
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
- **Instructions** live in `workergrid/instructions.md` — edit any time (`/wg instruct`).
- Worker/scheduler verbs were **moved out of `/pf`** into `/wg`.
