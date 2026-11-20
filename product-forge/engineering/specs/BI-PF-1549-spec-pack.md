# Conditional Spec Pack — BI-PF-1549 — Dev-Ex: One-command Plane A delivery CLI (scripts/dev/deliver.py --item <ID>) with pre-commit separation and atomic landing

- **Version:** 1
- **Status:** approved
- **Functional spec:** engineering/specs/BI-PF-1549.md
- **Design pack:** engineering/design/BI-PF-1549.md

Every conditional spec is `APPLICABLE` with an artifact/sections/evidence, or `N/A` with a concrete reason.

| Spec | Status | Owner | Reason | Artifact | Sections | Evidence |
|---|---|---|---|---|---|---|
| product_design_spec | APPLICABLE | BI-PF-1549 | CLI delivery design | engineering/design/BI-PF-1549.md | all | engineering/design/BI-PF-1549.md |
| api_contract | N/A | BI-PF-1549 | Developer CLI tooling only; no HTTP endpoints or network listeners. |  |  |  |
| data_contract | N/A | BI-PF-1549 | No database schema additions; reuses existing backlog schema. |  |  |  |
| config_contract | N/A | BI-PF-1549 | No configuration file modified or added. |  |  |  |
| nfr_slo | N/A | BI-PF-1549 | Developer CLI tooling with no long-lived daemon SLO. |  |  |  |
| security_threat_model | APPLICABLE | BI-PF-1549 | Enforces pre-commit hook integrity and branch protections. | engineering/design/BI-PF-1549.md | security | engineering/design/BI-PF-1549.md |
| migration_backfill | N/A | BI-PF-1549 | No data migration or database schema backfill required. |  |  |  |
| rollback_dr | N/A | BI-PF-1549 | Code revert of scripts/dev/deliver.py without disaster recovery implications. |  |  |  |
| observability_runbook | APPLICABLE | BI-PF-1549 | Outputs JSON delivery diagnostics to stdout and stderr. | engineering/design/BI-PF-1549.md | observability | engineering/design/BI-PF-1549.md |
| accessibility_i18n | N/A | BI-PF-1549 | No user interface exists in this tooling-only compiler item. |  |  |  |
| privacy_compliance | N/A | BI-PF-1549 | No personal data handled by this CLI delivery tool. |  |  |  |
| implementation_plan | APPLICABLE | BI-PF-1549 | Plane A delivery implementation plan | engineering/design/BI-PF-1549.md | rollout | engineering/design/BI-PF-1549.md |
| release_verification | APPLICABLE | BI-PF-1549 | Delivery contract test execution | engineering/design/BI-PF-1549.md | tests | engineering/design/BI-PF-1549.md |


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
