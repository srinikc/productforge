# PIDL-1 — Context Resolver

**Item:** BI-PF-0376 (epic BI-PF-0375) · `core/pidl.py` + `config/pidl-profile.json` + `GET /engineering/pidl/context`

PIDL (Personal Intelligence Decision Layer) is a centralized **decision/perspective** capability invoked by
the orchestration/scheduler path at decision boundaries — **never by workers** (doc appendix). PIDL-1 is the
read-only **context resolver**: it assembles only the *relevant subset* of the user's established
rules/principles/preferences/prior decisions for a given task/result/action. The whole personality is never
loaded or injected.

## Reuse, not rewrite

| context | canonical owner |
|---|---|
| strict rules / principles | `core/forge_constitution.py` + `core/learnings.py` |
| preferences | `core/persona.py` (`config/persona.json`) |
| prior decisions / context | `core/memory_api.py` (RAG) |

PIDL owns only the thin **profile index** `config/pidl-profile.json` (version + category→source mapping +
review lenses + approval defaults) — registered single-writer in `config/store-registry.json`. No parallel
memory/identity store.

## Contract

`resolve_context(scope, project, *, task/result/action/components/area)` returns:
`profile_version`, `applicable_rules`, `applicable_principles`, `applicable_preferences`, `prior_decisions`,
`review_lenses`, `execution_policy` (`autonomy`/`approval_required`/`escalation_allowed`), `consequential`,
`evidence`, `context_size`. Pure, deterministic, fail-open-to-empty (never raises).

A **consequential** action (architecture/security/destructive/production/release/… keywords) flips
`execution_policy.approval_required` to true — the basis for the PIDL-4 consequential-action gate.

## API (API-first)

`GET /api/v1/engineering/pidl/context?scope=&project=&area=&components=a,b&action=` (read-only).

## Verification

```
python scripts/dev/pidl_check.py     # subset, deterministic, read-only, decoupled (no worker imports)
python scripts/dev/precheck.py       # fast tier (pidl gate runs when core/pidl* changes)
```
