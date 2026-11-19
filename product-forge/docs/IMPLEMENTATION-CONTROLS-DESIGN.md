# Implementation Controls and 360° Readiness Design

- Item: BI-PF-1538
- Epic: BI-PF-1243
- Status: design for approval
- Scope: tooling/process only; no customer-facing runtime change

## RECONCILIATION

### PRIOR DECISIONS
- BI-PF-1243 owns delivery-process improvements.
- BI-PF-1469/1470 established Gate 2 completion predicates and fail-closed merge evidence.
- BI-PF-1536 added deterministic review selection; BI-PF-1537 was rejected as superseded.
- BI-PF-1268 RCCA: happy-path implementation, missing tenant/IO/concurrency/observability controls, and fix-induced regressions caused repeated review loops.

### EXISTING PATH
- `scripts/dev/design_pack.py` validates design-pack sections.
- `templates/DESIGN-PACK.md`, `FUNCTIONAL-SPEC.md`, `SPEC-PACK.md` render design/spec artifacts.
- `scripts/dev/gate1_check.py` blocks Gate 1 on pending BLOCKER/MAJOR findings and design/spec chain errors.
- `scripts/dev/architect_review.py` runs Gate 2.5 reviews and stores findings.
- `scripts/dev/gate2_completion_check.py` and `merge_gate_check.py` enforce completion/merge evidence.
- Backlog writes are owned by `core.backlog`; API routes are the allowed external write path.

### ASSUMPTIONS
- Enforcement applies to new items only; completed/historical items are not retrofitted.
- Tooling, CI, templates, config and docs may remain Python/JSON/Markdown.
- No new runtime store, service, or duplicate gate owner is required.
- Existing review evidence format can carry the controls matrix without a new review system.

### DIVERGENCES
- The backlog API has no design-pack write endpoint; current design packs are written through core/file paths. BI-PF-1538 must add an API endpoint before enforcement can be API-only.
- Gate 1 currently validates section presence, not implementation-control completeness. This is the gap being closed.

### OPEN QUESTIONS
1. Enforcement start: next newly created item after merge, or an explicit effective date?
2. Do MINOR control gaps block Gate 1, or remain advisory while BLOCKER/MAJOR block?
3. Should final readiness require exact symbol resolution for Go/Python, or allow declared test/evidence paths with symbol-name checks?
4. Which existing observability owner receives control metrics for escaped-defect/RCCA counts?

## Problem

Design/spec gates accept prose and happy-path test plans. Nothing forces an implementer to enumerate negative/failure, tenant/RLS, concurrency, config-invalid, data/IO atomicity, migration/rollback, resource, and observability cases with an owning symbol and test. Reviews therefore become the first quality gate and fixes introduce regressions.

## Design

### 1. Canonical control matrix

Add `design_pack.implementation_controls` as a list. Each row is one control:

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Stable control id, unique within the item |
| `ac` | yes | AC/FR id covered by the control |
| `kind` | yes | `security`, `tenant`, `concurrency`, `failure`, `config`, `data`, `migration`, `resource`, `observability`, `happy` |
| `control` | yes | The behavior that must hold |
| `symbol` | yes | Planned code owner (file + function/type) |
| `positive_test` | yes | Test proving the intended path |
| `negative_test` | yes | Test proving rejection/failure behavior |
| `tenant_test` | conditional | Required for tenant-scoped data/API paths; otherwise `N/A: reason` |
| `concurrency_test` | conditional | Required for shared counters/queues/transactions; otherwise `N/A: reason` |
| `observability` | yes | Signal, owner, threshold/alert or `N/A: reason` |
| `evidence` | yes | Test command/path and expected result |

Rules:
- Every AC/FR has at least one row.
- Every runtime item has `security`, `tenant`, `failure`, `config`, `observability` rows or explicit `N/A` reasons.
- No placeholders (`TBD`, `pending`, `not specified`, empty).
- A row with `symbol` or test paths cannot be actioned until those files exist in the final diff.

### 2. Reuse existing gates; add one checker

Extend, do not replace:
- `templates/DESIGN-PACK.md`: add a control-matrix section.
- `scripts/dev/design_pack.py`: validate matrix shape and required kinds behind an item-creation cutoff.
- `scripts/dev/gate1_check.py`: fail when required matrix rows are missing or placeholder-only.
- New `scripts/dev/implementation_readiness_check.py`:
  - pre-code mode: validate the matrix and planned tests/symbols;
  - final mode: verify symbols/tests/evidence exist in the diff, reject dead/uncalled controls and caller-controlled security inputs;
  - output machine-readable problems for precheck/Gate 2.5.
- `scripts/dev/architect_review.py`: include the matrix in the Gate 2.5 prompt and require planned-vs-actual coverage.
- `scripts/dev/gate2_completion_check.py`: consume the checker result as a completion predicate.

No second review engine, no second backlog store, no duplicate gate owner.

### 3. API-first write path

Add one backlog API endpoint:
- `POST /api/v1/backlog/items/{item_id}/design-pack`
- validates schema through `design_pack.py`
- writes via `core.backlog.update` (single writer)
- enforces operator role and revision guard.

This closes the divergence where design packs can only be written outside the API.

### 4. RCCA path

When a defect escapes a passing gate:
- record RCCA: cause, missed control, why the gate did not catch it;
- open a new backlog item for the missing control or test;
- link both items;
- no silent cross-PR fix.

### 5. Mandatory design and functional-specification prompt

Every new backlog item/feature must produce a self-contained design and functional specification
using these five mandates. The prompts are rendered from templates and Gate 1 rejects missing sections.

1. **Requirement understanding and analysis**: business objective, problem, users, requirements,
   acceptance criteria, existing behaviour, architecture, dependencies, gaps, ambiguities,
   assumptions, constraints, implicit requirements, WHAT/WHY/outcomes.
2. **Complete functional and technical design**: journeys, workflows, business rules, UI/UX where
   applicable, architecture, components, APIs, data models, integrations, configuration, permissions,
   errors, notifications, upstream/downstream dependencies, end-to-end interaction.
3. **360° scenario and impact coverage**: normal, alternative, negative, boundary, edge, exception,
   failure, recovery, concurrency, security, performance, scalability, accessibility,
   backward-compatibility; impacts on existing features, shared components, integrations, data and
   dependent workflows; regression risks and mitigations.
4. **Implementation and validation readiness**: component responsibilities, behaviours, interfaces,
   dependencies, sequencing, acceptance criteria, and testable unit/API/integration/functional/e2e/
   regression/security/non-functional validation.
5. **Specification quality and completeness review**: independent product-owner, architect, developer,
   QA, security and end-user review; missing requirements, gaps, contradictions, ambiguity, broken
   workflows, disconnected components, dependencies, untestable ACs; full requirements-to-validation
   traceability; assumptions, decisions, risks, open questions, completion status.

No superficial, generic, abbreviated or half-baked specification is accepted. Requirements are never
invented and missing decisions are never silently assumed; assumptions are explicit and clarification
is an open question.

### 6. Mandatory implementation prompt

Every implementation or fix uses these five mandates. Gate 2.5 verifies their evidence.

1. **Understand and analyse completely**: requirements, ACs, architecture, dependencies, workflows,
   integrations, affected components; functional, technical, operational, security, performance, data,
   UI/UX and backward-compatibility implications; resolve ambiguities rather than assume.
2. **Implement completely, no shortcuts**: production-quality, integrated end to end; all applicable
   scenarios, components, APIs, data flows, configuration, errors, edge cases and dependent workflows;
   no placeholders, stubs, hardcoding, partial implementations, disconnected components or deferred
   requirements disguised as complete.
3. **360° impact and regression prevention**: upstream/downstream, shared modules, existing features,
   integrations, concurrency, failure modes, side effects; preserve compatibility; no regressions or
   unrelated changes.
4. **Comprehensive validation**: every AC and applicable positive, negative, boundary, edge, failure,
   recovery, concurrency, integration and end-to-end scenario; unit/API/integration/functional/
   regression/security/performance/deployment tests; real execution and outcomes, not compilation or
   test creation alone; fix and revalidate.
5. **Independent quality review and closure**: architect, developer, QA, security and end-user review;
   challenge assumptions, find missed requirements, hidden defects, incomplete wiring and impacts;
   evidence-based closure with traceability, changed components, impact, tests/results, regression
   assessment, limitations and residual risks.

Quality and completeness take precedence over speed, tokens or task closure. Anything not implemented
or validated is reported as incomplete with reason and impact. Never silently skip, downgrade, bypass
or mark an unverified requirement complete.

### 7. Delivery completion states

Every item reports these states separately; only the last means delivered:

- **Code Complete**: changes implemented.
- **Integration Complete**: all affected components/workflows wired.
- **Validation Complete**: required tests executed and passed with evidence.
- **Quality Approved**: independent review has no unresolved critical issues.
- **Delivery Complete**: all four conditions satisfied.

Gate 2 and merge require **Delivery Complete**. A merged PR alone is not Delivery Complete.

### 8. Coding and tech-stack guidelines as executable checks

Guidelines are not prose-only. `config/implementation-controls.json` maps each applicable guideline to
an executable check and evidence field; `implementation_readiness_check.py` fails when a required
check is missing, unrun or unrecorded.

- Go: gofmt, go vet, context propagation, connection/pool reuse, wrapped error classification,
  race tests where shared state exists, no dead or uncalled control.
- PostgreSQL: transaction boundaries, constraints for uniqueness, RLS with NOSUPERUSER/NOBYPASSRLS,
  migration up/down + backup marker, integration test.
- Object store/IO: tenant scope, reference/hash validation, atomicity/failure cleanup, bounded GC.
- API: authentication/authorization, tenant scoping, input validation, fail-closed configuration,
  negative and API contract tests.
- Config: enums fail closed; invalid values are tested.
- Security: no caller-controlled security inputs (paths, DSNs, tenant/role, limits).
- Simplicity/reuse: extend existing owners; no duplicate store/gate engine; self-review deletes
  dead code, unused imports/vars/components and redundant complexity.

## Impact Review

| Area | Impact | Check |
|---|---|---|
| Language | Python tooling/templates/API; no runtime Go | `language_check` |
| API | New design-pack write endpoint | `api_check`; OpenAPI/tests |
| AC-1 | Matrix required at Gate 1 | gate test |
| AC-2 | Readiness checker pre-code and final | checker tests |
| AC-3 | Templates + Gate 2.5 + RCCA enforced | prompt/gate tests |
| Data | Backlog item fields only; no schema migration | store registry review |
| Security | Operator-only API; no caller-controlled paths | API tests |

## Risks and Mitigation

- **False confidence from path-only checks** → require both symbol-name and test/evidence resolution in final mode.
- **Retrofitting historical items** → cutoff by creation timestamp, never mutate closed items.
- **Template/checker drift** → one schema validator used by template, Gate 1 and API.
- **Gate latency** → cache file parsing; run structural checks pre-code and diff checks only on changed files.
- **Over-blocking trivial work** → `N/A: reason` is allowed, but reasons are reviewed.
- **Control matrix becomes paperwork** → final mode must verify real symbols/tests; placeholders fail.

## Rollback

Remove the API endpoint, checker wiring, template section and control requirements; keep the design doc and RCCA history. No data migration to reverse.

## Verification

- Unit tests for schema validation, API endpoint, readiness checker, and Gate 1 failure modes.
- Negative tests: missing AC row, placeholder path, absent symbol, caller-controlled path, dead control.
- Gate 2.5 test proving matrix coverage is included in the prompt.
- Precheck run on this item with no placeholders.
