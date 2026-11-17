# Review Material-Change API and Delta Base Design

- Item: BI-PF-1540
- Epic: BI-PF-1243
- Bootstrap exception: approved by HIL to unblock review-budget decisions before BI-PF-1538 merges.

## Problem

Review budget blocks a legitimate fix delta after two full reviews. HIL `MATERIAL_CHANGE`
approval exists in the policy but cannot be recorded through the backlog API. Delta review
also requires the latest reviewed SHA, rejecting a valid earlier reviewed ancestor.

## Design

### Decisions endpoint

`POST /api/v1/backlog/items/{item_id}/decisions`

- operator role only
- `decision` must be `MATERIAL_CHANGE`
- `mode` must be `design` or `diff`
- `reason` >= 20 chars
- `hil_confirmed=true`
- `by=hil:<actor>`
- revision guard
- appends to `item.decisions` through `core.backlog.update`

### Delta base

A re-review may use any SHA that is:
- a reviewed HEAD for the item+mode, and
- an ancestor of current HEAD.

The reason must still cite the latest review SHA. Arbitrary or unreviewed SHAs are rejected.

## API

| Route | Method | Auth | Contract |
|---|---|---|---|
| `/api/v1/backlog/items/{item_id}/decisions` | POST | operator | append-only MATERIAL_CHANGE |

## Failure modes

| Case | Behavior |
|---|---|
| invalid decision/mode/reason | 400 VALIDATION_FAILED |
| missing HIL confirmation/actor | 400 VALIDATION_FAILED |
| stale revision | 409 |
| item not found | 404 |
| unreviewed/non-ancestor delta base | review refused |

## Security

- no caller-controlled tenant/path/DSN
- operator-only auth
- append-only decisions; no update/delete
- reason redaction handled by review tooling

## Tests

- material-change accepted with HIL fields
- material-change rejected without HIL
- decisions route published
- reviewed-ancestor base accepted; arbitrary base rejected


## Guardrail answers

- **Reversibility**: removing the route is safe; append-only decisions are intentionally retained as audit history.
- **Availability**: the endpoint uses the local backlog owner; failures are fail-closed and never partially write.
- **Invariant ordering**: validate revision, then allowlisted HIL identity, then reason/latest-SHA, then append atomically via `core.backlog.update`.
- **Scope/tenant**: item lookup is scope/project-scoped by `_scope_project`; there is no tenant header or caller-controlled tenant input.
- **Observability**: API errors use the standard envelope; decision appends are auditable through item history/trail; budget refusals report mode and count.

HIL identities are allowlisted in `config/review-material-change.json`. The reason must literally cite the latest review SHA.
