---
description: "Product Forge command surface: /pf <verb>. verbs: product, backlog, dogfood, validate, release, package, audit, status, pidl. Thin adapter to scripts/pf.py (no logic here). Worker/scheduler orchestration moved to /wg (WorkerGrid)."
agent: build
---

**NOTE:** This command is a **thin adapter** to `scripts/pf.py`, which calls the canonical core/API.
It contains **no orchestration logic**. `/pipeline` is a deprecated alias for `/pf product`.
**Worker/scheduler orchestration was decoupled** into **WorkerGrid** (`/wg`, `workergrid/wg.py`) — see ADR-0002.

$ARGUMENTS

## STEP 1: empty?
If `$ARGUMENTS` is empty/whitespace, run `python scripts/pf.py --help` and STOP.

## STEP 2: delegate
Run `python scripts/pf.py $ARGUMENTS` from the `product-forge/` directory and report the output.
Deterministic verbs (backlog, dogfood, validate, release, package, audit, status) return JSON. Product
generation (`/pf product ...`) delegates to `scripts/pipeline.py` (the existing agent runner).

## Verb map
- `/pf help [verb]` — usage overview, or per-verb details (subcommands + flags)
- `/pf product new "idea" --tier <tier>` / `continue` / `fix "desc"` → `scripts/pipeline.py`
- `/pf backlog list|show <id>|groom <id> [--no-ai]|approve <id>`
- `/pf dogfood [--dry]`
- `/pf validate <PROFILE>` · `/pf release readiness|gate` · `/pf package <edition>`
- `/pf audit` · `/pf status` · `/pf pidl decisions|show|candidates|policy|latest`
- `/pf sync` — git sync (fetch remote + push develop)

## Moved to WorkerGrid (`/wg`)
- worker registry, work pull, scheduler eligibility, adapters, dispatch → **`/wg …`**
