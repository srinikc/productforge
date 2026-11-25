# Conditional Spec Pack — BI-PF-1270 — Eventing SSOT (Go): transports - inproc callbacks, webhook (HMAC+idempotency), notify/email

- **Version:** 1
- **Status:** approved
- **Functional spec:** engineering/specs/BI-PF-1270.md
- **Design pack:** docs/EVENT-TRANSPORTS-DESIGN.md

Every conditional spec is `APPLICABLE` with an artifact/sections/evidence, or `N/A` with a concrete reason.

| Spec | Status | Owner | Reason | Artifact | Sections | Evidence |
|---|---|---|---|---|---|---|
| product_design_spec | APPLICABLE | BI-PF-1270 | transport design | docs/EVENT-TRANSPORTS-DESIGN.md | all | docs/EVENT-TRANSPORTS-DESIGN.md |
| api_contract | APPLICABLE | BI-PF-1270 | notification endpoint | api/routers/events.py | notifications | docs/EVENT-TRANSPORTS-DESIGN.md |
| data_contract | APPLICABLE | BI-PF-1270 | existing notification store | core/notification_system.py | all | docs/EVENT-TRANSPORTS-DESIGN.md |
| config_contract | APPLICABLE | BI-PF-1270 | env flags | docs/EVENT-TRANSPORTS-DESIGN.md | configuration | docs/EVENT-TRANSPORTS-DESIGN.md |
| nfr_slo | APPLICABLE | BI-PF-1270 | timeouts | docs/EVENT-TRANSPORTS-DESIGN.md | risks | docs/EVENT-TRANSPORTS-DESIGN.md |
| security_threat_model | APPLICABLE | BI-PF-1270 | HMAC/SSRF/secrets | docs/EVENT-TRANSPORTS-DESIGN.md | security | docs/EVENT-TRANSPORTS-DESIGN.md |
| migration_backfill | N/A | BI-PF-1270 | no migration |  |  |  |
| rollback_dr | APPLICABLE | BI-PF-1270 | additive rollback | docs/EVENT-TRANSPORTS-DESIGN.md | rollout | docs/EVENT-TRANSPORTS-DESIGN.md |
| observability_runbook | APPLICABLE | BI-PF-1270 | transport signals | docs/EVENT-TRANSPORTS-DESIGN.md | failure matrix | docs/EVENT-TRANSPORTS-DESIGN.md |
| accessibility_i18n | N/A | BI-PF-1270 | no user interface |  |  |  |
| privacy_compliance | N/A | BI-PF-1270 | no personal data |  |  |  |
| implementation_plan | APPLICABLE | BI-PF-1270 | transport plan | docs/EVENT-TRANSPORTS-DESIGN.md | all | docs/EVENT-TRANSPORTS-DESIGN.md |
| release_verification | APPLICABLE | BI-PF-1270 | tests | docs/EVENT-TRANSPORTS-DESIGN.md | tests | docs/EVENT-TRANSPORTS-DESIGN.md |


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
