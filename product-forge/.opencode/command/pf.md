---
description: "Product Forge command surface: /pf <verb>. verbs: product, backlog, work, scheduler, worker, adapters, dispatch, dogfood, validate, release, package, audit, status. Thin adapter to scripts/pf.py (no logic here)."
agent: orchestrator
model: opencode-go/mimo-v2.5
---

**NOTE:** This command is a **thin adapter** to `scripts/pf.py`, which calls the canonical core/API.
It contains **no orchestration logic**. `/pipeline` is a deprecated alias for `/pf product`.

$ARGUMENTS

## STEP 1: empty?
If `$ARGUMENTS` is empty/whitespace, run `python scripts/pf.py --help` and STOP.

## STEP 2: delegate
Run `python scripts/pf.py $ARGUMENTS` from the `product-forge/` directory and report the output.
Deterministic verbs (backlog, work, scheduler, worker, adapters, dispatch, dogfood, validate, release,
package, audit, status) return JSON. Product generation (`/pf product ...`) delegates to
`scripts/pipeline.py` (the existing agent runner).

## Verb map
- `/pf product new "idea" --tier <tier>` / `continue` / `fix "desc"` → `scripts/pipeline.py`
- `/pf backlog list|show <id>|groom <id> [--no-ai]|approve <id>`
- `/pf work [--worker W] [--runtime R]`
- `/pf scheduler status|eligible|next|plan`
- `/pf worker register --runtime R --caps a,b | list | status <id> | unregister <id>`
- `/pf adapters`
- `/pf dispatch status | dispatch tick [--force]`
- `/pf dogfood [--dry]`
- `/pf validate <PROFILE>` · `/pf release readiness|gate` · `/pf package <edition>`
- `/pf audit` · `/pf status`
