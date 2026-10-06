# PIDL-2 — Decision Engine + Structured Contract

**Item:** BI-PF-0377 (epic BI-PF-0375) · `core/pidl.py` + `POST /engineering/pidl/decide`

The decision engine evaluates a decision point and returns the doc's **structured contract**. It is pure and
read-only (policy first; no LLM required). Traceability/outcome recording is PIDL-5.

## Contract

```yaml
decision:   { action: AUTO_PROCEED | REVIEW | CORRECT | APPROVAL_REQUIRED | ESCALATE, reason }
confidence: { factual, architectural, requirement_interpretation, user_preference, implementation, overall }
risk:       LOW | MEDIUM | HIGH
recommendation
evidence:   [refs]
conflicts:  []
approval:   { required, policy }
next_action
pidl_profile_version
```

## Deterministic precedence

`ESCALATE` (repeated failures / explicit) → `APPROVAL_REQUIRED` (consequential, from the PIDL-1 execution
policy) → `CORRECT` (conflicts) → `REVIEW` (failed/blocked/needs-review result, or overall confidence below
`decision.review_below`) → `AUTO_PROCEED`.

Confidence is an explainable, bounded (0..1) weighted signal (`pidl-profile.json` → `decision.weights`), not
an opaque model score. Risk is `HIGH` for consequential/conflicting, `MEDIUM` for review/approval, else `LOW`.

## API (API-first)

`POST /api/v1/engineering/pidl/decide?scope=&project=` with body `{action, area, components, result, conflicts,
failures, escalated}` (read-only).

## Verification

```
python scripts/dev/pidl_check.py   # contract keys, closed action set, precedence, determinism, bounds
```
