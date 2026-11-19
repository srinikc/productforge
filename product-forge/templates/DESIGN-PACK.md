# Design Pack — {{ITEM}}

- **Item:** {{ITEM}}
- **Title:** {{TITLE}}
- **Version:** {{VERSION}}
- **Status:** {{STATUS}}
- **Gate 1.5 review SHA:** {{REVIEW_SHA}}
- **Functional spec:** {{FUNCTIONAL_REF}}
- **Conditional spec pack:** {{SPEC_PACK_REF}}
- **Generated:** {{GENERATED_AT}}

## 1. Standards applied
{{STANDARDS}}

### Coding guidelines applied
{{CODE_GUIDELINES}}

## 2. Requirements / acceptance criteria
{{REQUIREMENTS}}

## 3. Scope and non-goals
### In scope
{{SCOPE}}
### Non-goals
{{NON_GOALS}}

## 4. Logic invariants and state model
{{INVARIANTS}}

## 5. Contracts
### API
{{API}}
### Database / persistence
{{DB}}
### Files / stores / config
{{FILES}}

## 6. Failure matrix
| Case | Expected behavior | Error code |
|---|---|---|
{{FAILURES}}

## 7. Dependencies and failure modes
{{DEPENDENCIES}}

## 8. Security, authz, tenant isolation
{{SECURITY}}

## 9. Observability
{{OBSERVABILITY}}

## 10. Performance and scale
{{PERFORMANCE}}

## 11. Compatibility, migration, rollout, rollback
{{ROLLOUT}}

## 12. Test matrix
| AC | Kind | Test / command |
|---|---|---|
{{TESTS}}

## 13. Decisions and amendments
{{DECISIONS}}

## 14. Runtime contract

| Field | Required value |
|---|---|
| Trigger | {{RUNTIME_TRIGGER}} |
| Exact production entrypoint | {{RUNTIME_ENTRYPOINT}} |
| Exact call-site chain | {{RUNTIME_CALL_SITES}} |
| Production adapter | {{RUNTIME_ADAPTER}} |
| Contract (inputs/outputs/state/auth/timeout) | {{RUNTIME_CONTRACT}} |
| Failure behavior | {{RUNTIME_FAILURE}} |
| Observable result | {{RUNTIME_RESULT}} |

## 15. Failing proof plan
{{PROOF_PLAN}}

## 16. Acceptance evidence
| AC | Evidence | Candidate SHA |
|---|---|---|
{{AC_EVIDENCE}}

## 17. Stop conditions
{{STOP_CONDITIONS}}

## 18. Design delta review contract

- Delta reviews assess **only changed design fields**; the full design is context.
- Prior findings are verified first and not reopened without new evidence.
- New findings outside the delta must be tagged `[OUT_OF_SCOPE]`.
- Any AC/contract/test/control change must update the matching design rows and evidence in the same delta.
- Evidence records `base_sha`, `head_sha`, `design_sha`, changed fields, and `review_scope: delta`.
- Design deltas do not consume the full-review budget; HIL decides after the agreed delta pass.

## 19. Base + inferred design areas

Every area is either fully specified or explicitly `N/A` with a reason. Blank sections are invalid.

{{DESIGN_AREAS}}


## Mandatory 360? Design & Functional Specification

Every item must provide all five before Gate 1:

1. Requirement understanding and analysis: objective, problem, users, requirements, ACs, existing
   behaviour, architecture, dependencies, gaps, ambiguities, assumptions, constraints, implicit
   requirements, WHAT/WHY/outcomes.
2. Complete functional and technical design: journeys, workflows, rules, UI/UX where applicable,
   architecture, components, APIs, data models, integrations, configuration, permissions, errors,
   notifications, dependencies, end-to-end interaction.
3. 360? scenario and impact coverage: normal, alternative, negative, boundary, edge, exception,
   failure, recovery, concurrency, security, performance, scalability, accessibility,
   backward-compatibility; impacts on existing features, shared components, integrations, data and
   workflows; regression risks and mitigation.
4. Implementation and validation readiness: component responsibilities, behaviours, interfaces,
   dependencies, sequencing, ACs; testable unit/API/integration/functional/e2e/regression/security/
   non-functional validation.
5. Specification quality and completeness review: independent product-owner, architect, developer, QA,
   security and end-user review; missing requirements, gaps, contradictions, ambiguity, broken
   workflows, disconnected components, dependencies, untestable ACs; full traceability; assumptions,
   decisions, risks, open questions, completion status.

No superficial, generic, abbreviated or half-baked specification. Never invent requirements or
silently assume missing decisions; label assumptions and raise clarification.
