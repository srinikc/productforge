# Conditional Spec Pack — BI-PF-1540 — Review material-change decision API and correct delta-review base

- **Version:** 1
- **Status:** approved
- **Functional spec:** engineering/specs/BI-PF-1540.md
- **Design pack:** docs/REVIEW-MATERIAL-CHANGE-DESIGN.md

Every conditional spec is `APPLICABLE` with an artifact/sections/evidence, or `N/A` with a concrete reason.

| Spec | Status | Owner | Reason | Artifact | Sections | Evidence |
|---|---|---|---|---|---|---|
| product_design_spec | APPLICABLE | BI-PF-1540 | review decision design | docs/REVIEW-MATERIAL-CHANGE-DESIGN.md | 1-6 | docs/REVIEW-MATERIAL-CHANGE-DESIGN.md |
| api_contract | APPLICABLE | BI-PF-1540 | new decisions endpoint | api/openapi.json | decisions | api/openapi.json |
| data_contract | N/A | BI-PF-1540 | decisions use the existing backlog item store |  |  |  |
| config_contract | APPLICABLE | BI-PF-1540 | review budget policy consumed | config/review-budget.json | all | config/review-budget.json |
| nfr_slo | N/A | BI-PF-1540 | tooling-only change |  |  |  |
| security_threat_model | APPLICABLE | BI-PF-1540 | operator-only append-only decisions | docs/REVIEW-MATERIAL-CHANGE-DESIGN.md | security | tests/test_review_material_change.py |
| migration_backfill | N/A | BI-PF-1540 | no database migration |  |  |  |
| rollback_dr | N/A | BI-PF-1540 | code revert only |  |  |  |
| observability_runbook | APPLICABLE | BI-PF-1540 | API errors and budget output | docs/REVIEW-MATERIAL-CHANGE-DESIGN.md | failure modes | tests/test_review_material_change.py |
| accessibility_i18n | N/A | BI-PF-1540 | No user interface exists in this tooling-only API change. |  |  |  |
| privacy_compliance | N/A | BI-PF-1540 | no personal data |  |  |  |
| implementation_plan | APPLICABLE | BI-PF-1540 | route and budget change | api/routers/backlog.py | decisions | tests/test_review_material_change.py |
| release_verification | APPLICABLE | BI-PF-1540 | tests verify release | tests/test_review_material_change.py | all | tests/test_review_material_change.py |


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
