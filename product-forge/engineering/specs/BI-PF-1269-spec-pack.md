# Conditional Spec Pack — BI-PF-1269 — Eventing SSOT (Go): subscriber registry + dispatcher (cursor, at-least-once, dedupe, retry->DLQ)

- **Version:** 1
- **Status:** approved
- **Functional spec:** engineering/specs/BI-PF-1269.md
- **Design pack:** docs/EVENTING-ALERTING-SSOT-DESIGN.md

Every conditional spec is `APPLICABLE` with an artifact/sections/evidence, or `N/A` with a concrete reason.

| Spec | Status | Owner | Reason | Artifact | Sections | Evidence |
|---|---|---|---|---|---|---|
| product_design_spec | APPLICABLE | BI-PF-1269 | eventing design | docs/EVENTING-ALERTING-SSOT-DESIGN.md | dispatch | docs/EVENTING-ALERTING-SSOT-DESIGN.md |
| api_contract | N/A | BI-PF-1269 | no public API |  |  |  |
| data_contract | APPLICABLE | BI-PF-1269 | new tables | migrations/0025_event_subscriptions_dispatch.up.sql | all | migrations/0025_event_subscriptions_dispatch.up.sql |
| config_contract | N/A | BI-PF-1269 | no new config |  |  |  |
| nfr_slo | N/A | BI-PF-1269 | bounded batch |  |  |  |
| security_threat_model | APPLICABLE | BI-PF-1269 | tenant RLS | docs/EVENTING-ALERTING-SSOT-DESIGN.md | security | docs/EVENTING-ALERTING-SSOT-DESIGN.md |
| migration_backfill | APPLICABLE | BI-PF-1269 | additive migration | migrations/0025_event_subscriptions_dispatch.up.sql | all | migrations/0025_event_subscriptions_dispatch.up.sql |
| rollback_dr | APPLICABLE | BI-PF-1269 | down migration | migrations/0025_event_subscriptions_dispatch.down.sql | all | migrations/0025_event_subscriptions_dispatch.down.sql |
| observability_runbook | APPLICABLE | BI-PF-1269 | metrics | docs/EVENTING-ALERTING-SSOT-DESIGN.md | observability | docs/EVENTING-ALERTING-SSOT-DESIGN.md |
| accessibility_i18n | N/A | BI-PF-1269 | no UI |  |  |  |
| privacy_compliance | N/A | BI-PF-1269 | no personal data |  |  |  |
| implementation_plan | APPLICABLE | BI-PF-1269 | dispatcher plan | go/edpdata/event_dispatcher.go | all | go/edpdata/event_dispatcher_test.go |
| release_verification | APPLICABLE | BI-PF-1269 | tests | go/edpdata/event_dispatcher_test.go | all | go/edpdata/event_dispatcher_test.go |


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
