# Conditional Spec Pack — BI-PF-1534 — EDP: fail closed for unlisted backlog scopes when DB mode is on

- **Version:** 1
- **Status:** PROPOSED
- **Functional spec:** engineering/specs/BI-PF-1534.md
- **Design pack:** engineering/design/BI-PF-1534.md

Every conditional spec is `APPLICABLE` with an artifact/sections/evidence, or `N/A` with a concrete reason.

| Spec | Status | Owner | Reason | Artifact | Sections | Evidence |
|---|---|---|---|---|---|---|
| product_design_spec | N/A | core | No user-facing UI; this is a runtime authority guard. |  |  |  |
| api_contract | N/A | core | No API change. |  |  |  |
| data_contract | N/A | core | No schema change. |  |  |  |
| config_contract | APPLICABLE | core | Scope allowlist and DB mode behavior. | engineering/design/BI-PF-1534.md | design_pack.config_contract | config/env-flags.json |
| nfr_slo | APPLICABLE | core | No hot-path regression. | engineering/design/BI-PF-1534.md | design_pack.performance_capacity | docs/BACKLOG-DB-SSOT.md |
| security_threat_model | APPLICABLE | core | Fail-closed isolation guard. | engineering/design/BI-PF-1534.md | design_pack.security_model | core/backlog.py |
| migration_backfill | N/A | core | No migration. |  |  |  |
| rollback_dr | APPLICABLE | core | Explicit off rollback. | engineering/design/BI-PF-1534.md | design_pack.rollback_recovery | docs/BACKLOG-DB-SSOT.md |
| observability_runbook | APPLICABLE | core | Error code/runbook. | engineering/design/BI-PF-1534.md | design_pack.observability | docs/BACKLOG-DB-SSOT.md |
| accessibility_i18n | N/A | core | No user-facing/localized content; backend guard only. |  |  |  |
| privacy_compliance | N/A | core | No new data. |  |  |  |
| implementation_plan | APPLICABLE | core | Guard + tests + docs. | engineering/design/BI-PF-1534.md | design_pack.deployment_rollout | docs/BACKLOG-DB-SSOT.md |
| release_verification | APPLICABLE | core | Tests and runbook. | engineering/design/BI-PF-1534.md | design_pack.test_matrix | test-framework/tests/pipeline/test_backlog_db_cutover.py |


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
