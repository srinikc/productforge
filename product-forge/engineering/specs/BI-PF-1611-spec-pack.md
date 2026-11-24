# Conditional Spec Pack — BI-PF-1611 — Repair repository baseline gates: unscoped items, backlog context, and BI-PF-1566 completion trail

- **Version:** 2
- **Status:** draft
- **Functional spec:** engineering/specs/BI-PF-1611.md
- **Design pack:** engineering/design/BI-PF-1611.md

Every conditional spec is `APPLICABLE` with an artifact/sections/evidence, or `N/A` with a concrete reason.

| Spec | Status | Owner | Reason | Artifact | Sections | Evidence |
|---|---|---|---|---|---|---|
| product_design_spec | APPLICABLE | BI-PF-1611 | tooling predicate design | docs/BASELINE-GATE-REMEDIATION-DESIGN.md | all | docs/BASELINE-GATE-REMEDIATION-DESIGN.md |
| api_contract | N/A | BI-PF-1611 | No API surface change |  |  |  |
| data_contract | N/A | BI-PF-1611 | Read-only item status only |  |  |  |
| config_contract | APPLICABLE | BI-PF-1611 | backlog mode influences gate input | docs/BASELINE-GATE-REMEDIATION-DESIGN.md | config | docs/BASELINE-GATE-REMEDIATION-DESIGN.md |
| nfr_slo | APPLICABLE | BI-PF-1611 | determinism | docs/BASELINE-GATE-REMEDIATION-DESIGN.md | nfr | docs/BASELINE-GATE-REMEDIATION-DESIGN.md |
| security_threat_model | N/A | BI-PF-1611 | Read-only status predicate; no auth or data boundary |  |  |  |
| migration_backfill | N/A | BI-PF-1611 | No schema or data migration |  |  |  |
| rollback_dr | APPLICABLE | BI-PF-1611 | revert patch | docs/BASELINE-GATE-REMEDIATION-DESIGN.md | rollback | docs/BASELINE-GATE-REMEDIATION-DESIGN.md |
| observability_runbook | APPLICABLE | BI-PF-1611 | gate output | docs/BASELINE-GATE-REMEDIATION-DESIGN.md | observability | docs/BASELINE-GATE-REMEDIATION-DESIGN.md |
| accessibility_i18n | N/A | BI-PF-1611 | No UI surface in tooling predicates. |  |  |  |
| privacy_compliance | N/A | BI-PF-1611 | No personal data |  |  |  |
| implementation_plan | APPLICABLE | BI-PF-1611 | three predicate edits | docs/BASELINE-GATE-REMEDIATION-DESIGN.md | all | docs/BASELINE-GATE-REMEDIATION-DESIGN.md |
| release_verification | APPLICABLE | BI-PF-1611 | pytest regression | test-framework/tests/test_gates_skip_rejected.py | test | docs/BASELINE-GATE-REMEDIATION-DESIGN.md |


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
