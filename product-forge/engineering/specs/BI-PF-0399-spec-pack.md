# Conditional Spec Pack — BI-PF-0399 — A5: Runtime Dependency Compiler

- **Version:** 1
- **Status:** approved
- **Functional spec:** engineering/specs/BI-PF-0399.md
- **Design pack:** engineering/design/BI-PF-0399.md

Every conditional spec is `APPLICABLE` with an artifact/sections/evidence, or `N/A` with a concrete reason.

| Spec | Status | Owner | Reason | Artifact | Sections | Evidence |
|---|---|---|---|---|---|---|
| A5 Runtime Dependency Compiler | APPLICABLE | Srinikc | Authoritative composition engine + IP guard | go/pfcore/rdc.go | all | go/pfcore/rdc_test.go |
| Multi-Target OS/Arch Resolution | APPLICABLE | Srinikc | Supports linux/amd64, linux/arm64, windows/amd64, darwin/arm64 | go/pfcore/rdc.go | compose | test-framework/tests/pipeline/test_a5_rdc.py |
| Fail-Closed IP Leakage Guard | APPLICABLE | Srinikc | Strictly forbids raw .py source in customer packages | go/pfcore/rdc.go | validate_ip | test-framework/tests/pipeline/test_a5_rdc.py |
| Wire Seam Dispatch | APPLICABLE | Srinikc | Exposes rdc.compose and rdc.validate_ip via A1 wire | go/pfcore/pfcore.go | Handle | go/pfcore/rdc_test.go |
| REST API Exposure | APPLICABLE | Srinikc | Packaging endpoints for RDC composition | api/routers/packaging.py | rdc | test-framework/tests/pipeline/test_a5_rdc.py |

## Mandatory 360 Design & Functional Specification

Every item must provide all five before Gate 1:

1. Requirement understanding and analysis: objective, problem, users, requirements, ACs, existing
   behaviour, architecture, dependencies, gaps, ambiguities, assumptions, constraints, implicit
   requirements, WHAT/WHY/outcomes.
2. Complete functional and technical design: journeys, workflows, rules, UI/UX where applicable,
   architecture, components, APIs, data models, integrations, configuration, permissions, errors,
   notifications, dependencies, end-to-end interaction.
3. 360 scenario and impact coverage: normal, alternative, negative, boundary, edge, exception,
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
