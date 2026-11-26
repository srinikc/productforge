# Conditional Spec Pack — BI-PF-1553 — Next-Gen Web Console Packaging Specification: embed pre-compiled SPA distribution assets into Go platform server binary

- **Version:** 1
- **Status:** in_progress
- **Functional spec:** engineering/specs/BI-PF-1553.md
- **Design pack:** engineering/design/BI-PF-1553.md

Every conditional spec is `APPLICABLE` with an artifact/sections/evidence, or `N/A` with a concrete reason.

| Spec | Status | Owner | Reason | Artifact | Sections | Evidence |
|---|---|---|---|---|---|---|
| product_design_spec | APPLICABLE | BI-PF-1553 | Next-gen web console embedded packaging and distribution architecture | engineering/design/BI-PF-1553.md | all | engineering/design/BI-PF-1553.md |
| api_contract | N/A | BI-PF-1553 | Static SPA asset delivery and package validation; no REST API endpoints added |  |  |  |
| data_contract | N/A | BI-PF-1553 | No database schema additions; embedded static assets are immutable files |  |  |  |
| config_contract | APPLICABLE | BI-PF-1553 | EAP manifest registry and embedded console asset bundle configuration | config/eap-registry.json | all | config/eap-registry.json |
| nfr_slo | APPLICABLE | BI-PF-1553 | Sub-millisecond memory asset serving and transparent gzip transfer performance | engineering/design/BI-PF-1553.md | performance | engineering/design/BI-PF-1553.md |
| security_threat_model | APPLICABLE | BI-PF-1553 | Zero source code leakage guard and traversal boundary protection | engineering/design/BI-PF-1553.md | security | engineering/design/BI-PF-1553.md |
| migration_backfill | N/A | BI-PF-1553 | Additive packaging feature; no database migrations or data backfill |  |  |  |
| rollback_dr | APPLICABLE | BI-PF-1553 | Configuration fallback to external static directory if embed serving fails | engineering/design/BI-PF-1553.md | rollback | engineering/design/BI-PF-1553.md |
| observability_runbook | APPLICABLE | BI-PF-1553 | Structured failure tokens and build integrity logging | engineering/design/BI-PF-1553.md | observability | engineering/design/BI-PF-1553.md |
| accessibility_i18n | N/A | BI-PF-1553 | Packaging layer specification; frontend UI UX accessibility governed separately |  |  |  |
| privacy_compliance | N/A | BI-PF-1553 | No PII or customer personal data processed in packaging pipeline |  |  |  |
| implementation_plan | APPLICABLE | BI-PF-1553 | Three-phase implementation of Go handler, packaging validator, and tests | engineering/design/BI-PF-1553.md | all | engineering/design/BI-PF-1553.md |
| release_verification | APPLICABLE | BI-PF-1553 | Automated test suite verifying AC-1, AC-2, and AC-3 with candidate SHA pinning | test-framework/tests/pipeline/test_web_console_packaging.py | tests | test-framework/tests/pipeline/test_web_console_packaging.py |


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
