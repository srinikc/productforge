---
description: "Product Forge command surface (GLOBAL): /pf <verb>. verbs: product, backlog, dogfood, validate, release, package, audit, status, pidl. Thin adapter to product-forge scripts/pf.py (no logic here). Worker/scheduler moved to /wg (WorkerGrid). Available in every opencode session."
agent: build
---

**NOTE:** This command is a **thin adapter** to `scripts/pf.py` (Product Forge), which calls the
canonical core/API. It contains **no orchestration logic**. `/pipeline` is a deprecated alias for
`/pf product`. Inside the product-forge repo the project-level `.opencode/command/pf.md` overrides
this file; this global copy makes `/pf` work from ANY session/cwd — it resolves `pf.py` itself
(STEP 0), with no dependency on install.py/install.sh/install.bat.

**SOURCE OF TRUTH:** `product-forge/.opencode/command_global/pf.md` — keep the installed copy at
`~/.config/opencode/command/pf.md` byte-identical; `python scripts/dev/pf_surface_check.py`
fails on drift.

$ARGUMENTS

## STEP 0: resolve pf.py (self-locating — no installer)
Resolve `$PFSCRIPT` = the FIRST path below for which `Test-Path` returns `True`:
1. `$env:PF_ROOT\scripts\pf.py` — explicit override (set the `PF_ROOT` env var if you use one)
2. Known checkout: `C:\Users\ADMIN\Documents\Srinikc\AI Products\Exploring\product-forge\scripts\pf.py`
3. Discovery from the current directory: `<cwd>\scripts\pf.py`, then for each parent up to 5 levels:
   `<parent>\scripts\pf.py` and `<parent>\product-forge\scripts\pf.py`

If NONE exist → STOP. Report exactly: "Product Forge not found — set `PF_ROOT` to your product-forge
checkout (e.g. `setx PF_ROOT \"D:\path\product-forge\"`) or edit `~/.config/opencode/command/pf.md`."
Do NOT attempt STEP 1/2 and do not invent an alternative.
If one exists → continue and use `$PFSCRIPT` in STEP 1/2.

## STEP 1: empty?
If `$ARGUMENTS` is empty/whitespace, run `python "$PFSCRIPT" --help` and STOP.

## STEP 2: delegate
Run `python "$PFSCRIPT" $ARGUMENTS` and report the output.
(pf.py self-locates its repo ROOT from its own file location, so the resolved path works from any cwd.)
Deterministic verbs (backlog, dogfood, validate, release, package, audit, status) return JSON. Product
generation (`/pf product ...`) delegates to
Product Forge's `scripts/run_pipeline.py` (the canonical agent runner).

## Verb map
- `/pf help [verb]` — usage overview, or per-verb details (subcommands + flags)
- `/pf product new "idea" --tier <tier>` / `continue` / `fix "desc"` → PF `scripts/run_pipeline.py`
- `/pf backlog list|show <id>|groom <id> [--no-ai] [--force]|approve <id>`
  — groom fills the full context (objective/AC/in_scope/…), priority, and structured deps; gap-fill by default,
  `--force` overwrites existing authored fields
- `/pf backlog groom-all [--no-ai] [--batch N] [--jobs N] [--limit N] [--ids a,b] [--force] [--dry]|review|approve-all [--ids a,b] [--force] [--dry]`
  — bulk: groom all open items (incl. in-progress) in batched AI passes (3/pass, 4 concurrent), review the results,
  then approve clean items (approve-all skips flagged unless `--force`; COMPLETE items re-groomed only with `--force`)
- `/pf dogfood [--dry]`
- `/pf sync` — git sync (fetch remote + push develop)
- `/pf validate <PROFILE>` · `/pf release readiness|gate` · `/pf package <edition>`
- `/pf audit` · `/pf status`
