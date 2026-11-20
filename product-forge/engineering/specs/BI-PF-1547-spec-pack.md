# Conditional Spec Pack — BI-PF-1547 — Canonical specification contract, compiler and cross-document consistency gate

- **Version:** 1
- **Status:** approved
- **Functional spec:** engineering/specs/BI-PF-1547.md
- **Design pack:** docs/SPEC-CONTRACT-DESIGN.md

Every conditional spec is `APPLICABLE` with an artifact/sections/evidence, or `N/A` with a concrete reason.

| Spec | Status | Owner | Reason | Artifact | Sections | Evidence |
|---|---|---|---|---|---|---|
| product_design_spec | APPLICABLE | BI-PF-1547 | compiler design | docs/SPEC-CONTRACT-DESIGN.md | all | docs/SPEC-CONTRACT-DESIGN.md |
| api_contract | N/A | BI-PF-1547 | Tooling-only precheck validator; no HTTP routes, endpoints, or network listeners. |  |  |  |
| data_contract | N/A | BI-PF-1547 | backlog field only |  |  |  |
| config_contract | APPLICABLE | BI-PF-1547 | Compiler settings and item enforcement allowlist | config/spec-contract.json | all | config/spec-contract.json |
| nfr_slo | N/A | BI-PF-1547 | no runtime |  |  |  |
| security_threat_model | APPLICABLE | BI-PF-1547 | Fail-closed precheck gate boundary protection ensuring spec drift cannot bypass architect review | docs/SPEC-CONTRACT-DESIGN.md | risks | docs/SPEC-CONTRACT-DESIGN.md |
| migration_backfill | N/A | BI-PF-1547 | no migration |  |  |  |
| rollback_dr | N/A | BI-PF-1547 | code revert |  |  |  |
| observability_runbook | APPLICABLE | BI-PF-1547 | compiler problems | docs/SPEC-CONTRACT-DESIGN.md | design | docs/SPEC-CONTRACT-DESIGN.md |
| accessibility_i18n | N/A | BI-PF-1547 | No user interface exists in this tooling-only compiler item. |  |  |  |
| privacy_compliance | N/A | BI-PF-1547 | no personal data |  |  |  |
| implementation_plan | APPLICABLE | BI-PF-1547 | compiler plan | docs/SPEC-CONTRACT-DESIGN.md | all | docs/SPEC-CONTRACT-DESIGN.md |
| release_verification | APPLICABLE | BI-PF-1547 | tests | docs/SPEC-CONTRACT-DESIGN.md | tests | docs/SPEC-CONTRACT-DESIGN.md |


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
