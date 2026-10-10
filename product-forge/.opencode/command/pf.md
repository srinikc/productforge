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
generation (`/pf product ...`) delegates to `scripts/run_pipeline.py` (the canonical agent runner).

## Grooming -> approval (do not skip the ask)
`groom`/`groom-all` only PROPOSE an analysis (`status=IN_PROGRESS`); they do not approve it. After a groom run:
1. show the user the `summary` (groomed / pending_approval / flagged), then
2. ASK for approval; only on an explicit yes run `approve <id>` / `approve-all` (or re-run with `--approve`).
For one-shot (no prompt) use `/pf backlog groom-all --approve` (or `groom <id> --approve`).
Grooming/approval also refreshes + saves the parent epic's `execution_order` (view with `epic-status <id>`,
`epic-order <id>`).

## Verb map
- `/pf help [verb]` — usage overview, or per-verb details (subcommands + flags)
- `/pf product new "idea" --tier <tier>` / `continue` / `fix "desc"` → `scripts/run_pipeline.py`
- `/pf backlog list|show <id>|epic-order <id> [--dry]|epic-status <id>|status [--all]|restamp [--limit N] [--ai]|groom <id> [--no-ai] [--approve]|approve <id>`
- `/pf dogfood [--dry]`
- `/pf validate <PROFILE>` · `/pf release readiness|gate` · `/pf package <edition>`
- `/pf audit` · `/pf status` · `/pf pidl decisions|show|candidates|policy|latest`
- `/pf sync` — git sync (fetch remote + push develop)

## Moved to WorkerGrid (`/wg`)
- worker registry, work pull, scheduler eligibility, adapters, dispatch → **`/wg …`**
