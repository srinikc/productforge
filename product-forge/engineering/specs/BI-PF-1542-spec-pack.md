# Conditional Spec Pack — BI-PF-1542 — Prompt mandate wiring for design and implementation agents

- **Version:** 1
- **Status:** approved
- **Functional spec:** engineering/specs/BI-PF-1542.md
- **Design pack:** docs/IMPLEMENTATION-CONTROLS-DESIGN.md

Every conditional spec is `APPLICABLE` with an artifact/sections/evidence, or `N/A` with a concrete reason.

| Spec | Status | Owner | Reason | Artifact | Sections | Evidence |
|---|---|---|---|---|---|---|
| product_design_spec | APPLICABLE | BI-PF-1542 | prompt design | docs/PROMPT-MANDATES.md | mandates | docs/PROMPT-MANDATES.md |
| api_contract | N/A | BI-PF-1542 | no API change |  |  |  |
| data_contract | N/A | BI-PF-1542 | no data change |  |  |  |
| config_contract | N/A | BI-PF-1542 | no new config |  |  |  |
| nfr_slo | N/A | BI-PF-1542 | prompt only |  |  |  |
| security_threat_model | APPLICABLE | BI-PF-1542 | prompt injection of security rules | docs/PROMPT-MANDATES.md | security | docs/PROMPT-MANDATES.md |
| migration_backfill | N/A | BI-PF-1542 | no migration |  |  |  |
| rollback_dr | N/A | BI-PF-1542 | prompt revert only |  |  |  |
| observability_runbook | APPLICABLE | BI-PF-1542 | prompt assertions | tests/test_prompt_mandates.py | all | tests/test_prompt_mandates.py |
| accessibility_i18n | N/A | BI-PF-1542 | No user interface exists in this prompt-only change. |  |  |  |
| privacy_compliance | N/A | BI-PF-1542 | no personal data |  |  |  |
| implementation_plan | APPLICABLE | BI-PF-1542 | prompt plan | core/orchestrator/prompt_builder.py | mandates | tests/test_prompt_mandates.py |
| release_verification | APPLICABLE | BI-PF-1542 | tests verify | tests/test_prompt_mandates.py | all | tests/test_prompt_mandates.py |


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
