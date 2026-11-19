# Conditional Spec Pack — BI-PF-1508 — PF-SB pilot: EDP backlog authority readiness endpoint

- **Version:** 1
- **Status:** APPROVED
- **Functional spec:** engineering/specs/BI-PF-1508.md
- **Design pack:** engineering/design/BI-PF-1508.md

Every conditional spec is `APPLICABLE` with an artifact/sections/evidence, or `N/A` with a concrete reason.

| Spec | Status | Owner | Reason | Artifact | Sections | Evidence |
|---|---|---|---|---|---|---|
| product_design_spec | N/A | engineering | Backend admin API only; no user-facing UI. |  |  |  |
| api_contract | APPLICABLE | engineering | New admin endpoint contract. | engineering/design/BI-PF-1508.md | design_pack.contracts.api, design_pack.runtime_contract | go/edpsvc/main.go |
| data_contract | APPLICABLE | engineering | Counter migration and global reservation counter. | engineering/design/BI-PF-1508.md | design_pack.data_model, design_pack.contracts.db | migrations/0018_backlog_reservation_counter.up.sql |
| config_contract | APPLICABLE | engineering | Admin token and runtime DB config. | engineering/design/BI-PF-1508.md | design_pack.contracts.config | go/edpsvc/main.go |
| nfr_slo | APPLICABLE | engineering | Readiness and latency SLO. | engineering/design/BI-PF-1508.md | design_pack.performance | ops/prometheus/backlog-authority.rules.yml |
| security_threat_model | APPLICABLE | engineering | Admin-only access and tenant-scoped RLS. | engineering/design/BI-PF-1508.md | design_pack.security | go/edpsvc/main.go |
| migration_backfill | APPLICABLE | engineering | 0018 counter migration. | engineering/design/BI-PF-1508.md | design_pack.rollout | migrations/0018_backlog_reservation_counter.up.sql |
| rollback_dr | APPLICABLE | engineering | Migration down and route rollback. | engineering/design/BI-PF-1508.md | design_pack.rollback | migrations/0018_backlog_reservation_counter.down.sql |
| observability_runbook | APPLICABLE | engineering | Metrics/alert/runbook. | engineering/design/BI-PF-1508.md | design_pack.observability | docs/BACKLOG-AUTHORITY-RUNBOOK.md, ops/prometheus/backlog-authority.rules.yml |
| accessibility_i18n | N/A | engineering | No UI or localized content. |  |  |  |
| privacy_compliance | N/A | engineering | No new PII or regulated data. |  |  |  |
| implementation_plan | APPLICABLE | engineering | Endpoint, migration, rule, runbook order. | engineering/design/BI-PF-1508.md | design_pack.rollout | docs/BACKLOG-AUTHORITY-RUNBOOK.md |
| release_verification | APPLICABLE | engineering | Tests and alert/runbook verification. | engineering/design/BI-PF-1508.md | design_pack.test_matrix | go/edpsvc/main_test.go |


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
