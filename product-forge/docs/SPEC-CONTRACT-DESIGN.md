# Canonical Specification Contract Design

- Item: BI-PF-1547
- Epic: BI-PF-1243
- Scope: tooling/process; no customer-facing runtime

## RECONCILIATION

### PRIOR DECISIONS
- BI-PF-1538/1543 introduced implementation controls and readiness checks.
- BI-PF-1270 exposed repeated design drift across design_pack, functional_spec and spec_pack.
- HIL acceptance is not a substitute for mechanical consistency.
- Tooling belongs in a separate item/branch/PR.

### EXISTING PATH
- `scripts/dev/design_pack.py`, `functional_spec.py`, `spec_pack.py` validate presence/format.
- `conformance_check.py` checks FR traceability.
- `implementation_readiness_check.py` checks control rows and symbols.
- Backlog context API already accepts design_pack/functional_spec/spec_pack.

### ASSUMPTIONS
- New items carry one canonical `spec_contract` field.
- Historical items are not retrofitted.
- The compiler is Python tooling, not runtime.

### DIVERGENCES
- Today three documents are authored separately and can contradict.
- The backlog API has no `spec_contract` write path; add it to the existing context whitelist.

### OPEN QUESTIONS
- Effective date/cutoff for new items.
- Whether existing in-flight items opt in.

## Design

### Canonical source
`item.spec_contract`:
- `version`
- `requirements[]`: AC/FR ids, behaviour, errors
- `controls[]`: AC/FR, kind, symbol, tests, evidence, N-A reasons
- `api`: method/path/auth/validation/tenant or explicit N/A
- `config`: one key table with default/type/owner
- `rollback`: one canonical string
- `risks`, `assumptions`, `decisions`
- `candidate_sha`

### Compiler
`scripts/dev/spec_contract.py`:
- validates canonical fields
- compiles `design_pack`, `functional_spec`, `spec_pack`
- compares compiled objects to the item’s stored packs
- fails closed on drift
- generates a compact impact-review table

Mechanical checks:
- unique AC/FR/control IDs
- every AC/FR has a control
- required control kinds
- every control has symbol + positive/negative tests + evidence
- test paths exist
- config keys have one default/type/owner
- rollback is identical across generated packs
- API contract complete or explicit N/A
- candidate SHA present and identical
- N/A has a concrete reason

### API
Add `spec_contract` to existing backlog context whitelist. No new endpoint or store.

### Gates
- New precheck gate `spec-contract` runs before architect review.
- Gate 1 consumes compiler output; architect review sees a consistent contract.
- Compiler failure blocks review.

### Tests
- valid canonical contract compiles and matches
- config drift fails
- rollback drift fails
- missing AC/FR/control fails
- duplicate control/symbol fails
- missing SHA fails
- invalid N/A fails
- API contract incomplete fails

## Impact Review

| Area | Impact | Check |
|---|---|---|
| Language | Python tooling only | language rule |
| API | context field addition | api-first |
| Backlog data | one new field, no store | store registry |
| Gate 1 | compiler before review | gate test |
| Existing items | cutoff, no retrofit | precheck |
| Tests | positive/negative matrix | pytest |

## Risks

| Risk | Mitigation |
|---|---|
| Canonical source itself becomes stale | derived packs computed from it; drift fails |
| Over-blocking | N/A allowed with reason; cutoff for new items |
| Duplicate logic | reuse existing design_pack/functional/spec renderers |
| Review latency | compiler is mechanical and local |

## Rollback

Remove the compiler gate and `spec_contract` field from context. Existing stored packs remain readable.
