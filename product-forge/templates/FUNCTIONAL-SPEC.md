# Functional Spec — {{ITEM}} — {{TITLE}}

- **Version:** {{VERSION}}
- **Status:** {{STATUS}}
- **Owner:** {{OWNER}}
- **Source:** {{SOURCE}}
- **Functional SHA:** {{FUNCTIONAL_SHA}}
- **Linked design:** {{DESIGN_REF}}

## 1. Outcome
{{OUTCOME}}

## 2. Actors
{{ACTORS}}

## 3. Scope
{{SCOPE}}

## 4. Non-goals
{{NON_GOALS}}

## 5. Assumptions and dependencies
{{ASSUMPTIONS}}
{{DEPENDENCIES}}

## 6. Domain and glossary
{{DOMAIN}}

## 7. Functional requirements
{{REQUIREMENTS}}

## 8. Operation matrix
| Mode | Operation | Scope | Actor | Expected result | Error |
|---|---|---|---|---|---|
{{OPERATION_MATRIX}}

## 9. Configuration contract
| Name | Default | Precedence | Valid values | Empty behavior | Invalid behavior | Startup validation |
|---|---|---|---|---|---|---|
{{CONFIG_CONTRACT}}

## 10. Non-functional requirements
{{NFR}}

## 11. Data lifecycle
{{DATA_LIFECYCLE}}

## 12. Compatibility
{{COMPATIBILITY}}

## 13. Rollback behavior
{{ROLLBACK}}

## 14. Observability
{{OBSERVABILITY}}

## 15. Traceability
| FR | Design | Test | Evidence |
|---|---|---|---|
{{TRACEABILITY}}

## 16. Open questions
{{OPEN_QUESTIONS}}

## 17. Definition of Done
{{DOD}}


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
