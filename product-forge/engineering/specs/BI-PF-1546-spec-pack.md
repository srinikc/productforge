# Conditional Spec Pack — BI-PF-1546 — Event dispatcher remediation: backoff, concurrency, cursor recovery, metrics and DLQ ownership

- **Version:** 1
- **Status:** approved
- **Functional spec:** engineering/specs/BI-PF-1546.md
- **Design pack:** docs/EVENTING-ALERTING-SSOT-DESIGN.md

Every conditional spec is `APPLICABLE` with an artifact/sections/evidence, or `N/A` with a concrete reason.

| Spec | Status | Owner | Reason | Artifact | Sections | Evidence |
|---|---|---|---|---|---|---|
| product_design_spec | APPLICABLE | BI-PF-1546 | remediation design | docs/EVENTING-ALERTING-SSOT-DESIGN.md | dispatch | go/edpdata/event_dispatcher_pg_integration_test.go |
| api_contract | N/A | BI-PF-1546 | no API change |  |  |  |
| data_contract | APPLICABLE | BI-PF-1546 | migration 0026 | migrations/0026_event_deliveries_created_at.up.sql | all | migrations/0026_event_deliveries_created_at.up.sql |
| config_contract | N/A | BI-PF-1546 | no new config |  |  |  |
| nfr_slo | N/A | BI-PF-1546 | bounded batch |  |  |  |
| security_threat_model | APPLICABLE | BI-PF-1546 | tenant collision handling | docs/EVENTING-ALERTING-SSOT-DESIGN.md | security | go/edpdata/event_dispatcher_pg_integration_test.go |
| migration_backfill | APPLICABLE | BI-PF-1546 | add column | migrations/0026_event_deliveries_created_at.up.sql | all | migrations/0026_event_deliveries_created_at.up.sql |
| rollback_dr | APPLICABLE | BI-PF-1546 | down migration | migrations/0026_event_deliveries_created_at.down.sql | all | migrations/0026_event_deliveries_created_at.down.sql |
| observability_runbook | APPLICABLE | BI-PF-1546 | metrics/logs | docs/EVENTING-ALERTING-SSOT-DESIGN.md | observability | go/edpdata/event_metrics_test.go |
| accessibility_i18n | N/A | BI-PF-1546 | No user interface exists in this dispatcher remediation. |  |  |  |
| privacy_compliance | N/A | BI-PF-1546 | no personal data |  |  |  |
| implementation_plan | APPLICABLE | BI-PF-1546 | dispatcher remediation | go/edpdata/event_dispatcher.go | all | go/edpdata/event_dispatcher_pg_integration_test.go |
| release_verification | APPLICABLE | BI-PF-1546 | tests | go/edpdata/event_dispatcher_pg_integration_test.go | all | go/edpdata/event_dispatcher_pg_integration_test.go |


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
