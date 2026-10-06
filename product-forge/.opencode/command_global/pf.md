---
description: "Product Forge command surface (GLOBAL): /pf <verb>. verbs: product, backlog, work, scheduler, worker, adapters, dispatch, dogfood, validate, release, package, audit, status. Thin adapter to product-forge scripts/pf.py (no logic here). Available in every opencode session."
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
Deterministic verbs (backlog, work, scheduler, worker, adapters, dispatch, dogfood, validate, release,
package, audit, status) return JSON. Product generation (`/pf product ...`) delegates to
Product Forge's `scripts/pipeline.py` (the existing agent runner).

## Verb map
- `/pf product new "idea" --tier <tier>` / `continue` / `fix "desc"` → PF `scripts/pipeline.py`
- `/pf backlog list|show <id>|groom <id> [--no-ai]|approve <id>`
- `/pf work [--worker W] [--runtime R]`
- `/pf scheduler status|eligible|next|plan`
- `/pf worker register --runtime R --caps a,b | list | status <id> | unregister <id>`
- `/pf adapters`
- `/pf dispatch status | dispatch tick [--force]`
- `/pf dogfood [--dry]`
- `/pf validate <PROFILE>` · `/pf release readiness|gate` · `/pf package <edition>`
- `/pf audit` · `/pf status`
