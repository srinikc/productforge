# Conditional Spec Pack — BI-PF-1538 — Mandatory implementation controls and tech-stack readiness gates

- **Version:** 1
- **Status:** approved
- **Functional spec:** engineering/specs/BI-PF-1538.md
- **Design pack:** docs/IMPLEMENTATION-CONTROLS-DESIGN.md

Every conditional spec is `APPLICABLE` with an artifact/sections/evidence, or `N/A` with a concrete reason.

| Spec | Status | Owner | Reason | Artifact | Sections | Evidence |
|---|---|---|---|---|---|---|
| product_design_spec | APPLICABLE | BI-PF-1538 | design is required | docs/IMPLEMENTATION-CONTROLS-DESIGN.md | 1-8 | docs/IMPLEMENTATION-CONTROLS-DESIGN.md |
| api_contract | APPLICABLE | BI-PF-1538 | new design-pack endpoint | api/openapi.json | design-pack | api/openapi.json |
| data_contract | N/A | BI-PF-1538 | no new runtime data store |  |  |  |
| config_contract | APPLICABLE | BI-PF-1538 | new executable checklist | docs/IMPLEMENTATION-CONTROLS-DESIGN.md | checks | docs/IMPLEMENTATION-CONTROLS-DESIGN.md |
| nfr_slo | N/A | BI-PF-1538 | tooling-only change with no runtime SLO |  |  |  |
| security_threat_model | APPLICABLE | BI-PF-1538 | operator-only API | docs/IMPLEMENTATION-CONTROLS-DESIGN.md | security | docs/IMPLEMENTATION-CONTROLS-DESIGN.md, docs/IMPLEMENTATION-CONTROLS-DESIGN.md |
| migration_backfill | N/A | BI-PF-1538 | no database migration |  |  |  |
| rollback_dr | N/A | BI-PF-1538 | no runtime deployment; rollback is code revert |  |  |  |
| observability_runbook | APPLICABLE | BI-PF-1538 | checker emits problems | docs/IMPLEMENTATION-CONTROLS-DESIGN.md | observability | docs/IMPLEMENTATION-CONTROLS-DESIGN.md |
| accessibility_i18n | N/A | BI-PF-1538 | no user interface |  |  |  |
| privacy_compliance | N/A | BI-PF-1538 | no personal data |  |  |  |
| implementation_plan | APPLICABLE | BI-PF-1538 | checker owns plan | docs/IMPLEMENTATION-CONTROLS-DESIGN.md | problems | docs/IMPLEMENTATION-CONTROLS-DESIGN.md |
| release_verification | APPLICABLE | BI-PF-1538 | tests verify release | docs/IMPLEMENTATION-CONTROLS-DESIGN.md | all | docs/IMPLEMENTATION-CONTROLS-DESIGN.md |


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
