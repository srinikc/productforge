# Conditional Spec Pack — BI-PF-1272 — Eventing SSOT: Python thin-client cutover of core/events.py over the A1 wire seam (edit-only)

- **Version:** 1
- **Status:** approved
- **Functional spec:** engineering/specs/BI-PF-1272.md
- **Design pack:** engineering/design/BI-PF-1272.md

Every conditional spec is `APPLICABLE` with an artifact/sections/evidence, or `N/A` with a concrete reason.

| Spec | Status | Owner | Reason | Artifact | Sections | Evidence |
|---|---|---|---|---|---|---|
| product_design_spec | APPLICABLE | BI-PF-1272 | Architectural cutover of Python events to Go core wire seam | engineering/design/BI-PF-1272.md | all | engineering/design/BI-PF-1272.md |
| api_contract | N/A | BI-PF-1272 | Internal Python library cutover; no HTTP endpoints modified. |  |  |  |
| data_contract | APPLICABLE | BI-PF-1272 | Canonical event envelope and sequence numbering contract | engineering/design/BI-PF-1272.md | contracts | engineering/design/BI-PF-1272.md |
| config_contract | N/A | BI-PF-1272 | No new configuration files or parameters introduced. |  |  |  |
| nfr_slo | APPLICABLE | BI-PF-1272 | Emission latency and fail-safe caller guarantees | engineering/specs/BI-PF-1272.md | nfr | engineering/specs/BI-PF-1272.md |
| security_threat_model | APPLICABLE | BI-PF-1272 | Event envelope sanitization and fail-safe execution | engineering/design/BI-PF-1272.md | security | engineering/design/BI-PF-1272.md |
| migration_backfill | N/A | BI-PF-1272 | Seamless append-only cutover; existing events.jsonl files remain valid. |  |  |  |
| rollback_dr | APPLICABLE | BI-PF-1272 | Git revert procedures for core/events.py | engineering/design/BI-PF-1272.md | rollback | engineering/design/BI-PF-1272.md |
| observability_runbook | APPLICABLE | BI-PF-1272 | Event emission logging and strangler fallback diagnostic signals | engineering/design/BI-PF-1272.md | observability | engineering/design/BI-PF-1272.md |
| accessibility_i18n | N/A | BI-PF-1272 | Backend event library; no user interface. |  |  |  |
| privacy_compliance | APPLICABLE | BI-PF-1272 | Redaction of sensitive fields in event payload | engineering/design/BI-PF-1272.md | security | engineering/design/BI-PF-1272.md |
| implementation_plan | APPLICABLE | BI-PF-1272 | Rollout plan for Python thin client over Go core | engineering/design/BI-PF-1272.md | scope | engineering/design/BI-PF-1272.md |
| release_verification | APPLICABLE | BI-PF-1272 | Verification of caller compatibility and monotonic seq assignment | engineering/design/BI-PF-1272.md | proof_plan | engineering/design/BI-PF-1272.md |


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
