# Conditional Spec Pack — BI-PF-1556 — Automated Deployment Rollback Orchestration: trigger instant rollback and record evidence on failed post-deploy smoke tests

- **Version:** 1
- **Status:** approved
- **Functional spec:** engineering/specs/BI-PF-1556.md
- **Design pack:** engineering/design/BI-PF-1556.md

Every conditional spec is `APPLICABLE` with an artifact/sections/evidence, or `N/A` with a concrete reason.

| Spec | Status | Owner | Reason | Artifact | Sections | Evidence |
|---|---|---|---|---|---|---|
| product_design_spec | APPLICABLE | eng:devops | Defines deployment architecture, fail-closed recovery, and rollback mechanisms. | engineering/design/BI-PF-1556.md | design_pack.product_design_spec | core/release_manager.py |
| api_contract | APPLICABLE | eng:devops | Defines health probe and authenticated evidence check API schemas. | engineering/design/BI-PF-1556.md | design_pack.api_contract | core/release_manager.py |
| data_contract | APPLICABLE | eng:devops | PostgreSQL expand-contract schema compatibility preserving state during rollback. | engineering/design/BI-PF-1556.md | design_pack.data_contract | core/release_manager.py |
| config_contract | APPLICABLE | eng:devops | Configuration contract parameters for retry thresholds and timeouts. | engineering/design/BI-PF-1556.md | design_pack.config_contract | core/release_manager.py |
| nfr_slo | APPLICABLE | eng:devops | Sub-30 second rollback SLA and fail-closed 45 second watchdog timeout. | engineering/design/BI-PF-1556.md | design_pack.nfr_slo | core/release_manager.py |
| security_threat_model | APPLICABLE | eng:devops | Tenant isolation and audited admin override token authorization. | engineering/design/BI-PF-1556.md | design_pack.security_threat_model | core/release_manager.py |
| migration_backfill | APPLICABLE | eng:devops | Expand-contract migration safety ensuring zero data loss during code rollback. | engineering/design/BI-PF-1556.md | design_pack.migration_backfill | core/release_manager.py |
| rollback_dr | APPLICABLE | eng:devops | Automated service-scoped reversion to prior stable platform revision. | engineering/design/BI-PF-1556.md | design_pack.rollback_dr | core/release_manager.py |
| observability_runbook | APPLICABLE | eng:devops | Structured JSON diagnostic traces and Prometheus metric emissions. | engineering/design/BI-PF-1556.md | design_pack.observability_runbook | core/release_manager.py |
| accessibility_i18n | N/A | eng:devops | N/A: Internal deployment automation tooling with no end-user localized web UI. | engineering/design/BI-PF-1556.md | design_pack.accessibility_i18n | core/release_manager.py |
| privacy_compliance | APPLICABLE | eng:devops | Deployment orchestrator processes no customer PII or sensitive personal data. | engineering/design/BI-PF-1556.md | design_pack.privacy_compliance | core/release_manager.py |
| implementation_plan | APPLICABLE | eng:devops | Sequential smoke assertion -> retry evaluation -> fail-closed rollback execution. | engineering/design/BI-PF-1556.md | design_pack.implementation_plan | core/release_manager.py |
| release_verification | APPLICABLE | eng:devops | Automated pytest suite verifying smoke assertions and rollback orchestration. | engineering/design/BI-PF-1556.md | design_pack.release_verification | core/release_manager.py |


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
