# Conditional Spec Pack — BI-PF-1550 — Prompt and Persona Asset Compiler: secure compilation and runtime encryption for proprietary agent instructions

- **Version:** 1
- **Status:** approved
- **Functional spec:** engineering/specs/BI-PF-1550.md
- **Design pack:** engineering/design/BI-PF-1550.md

Every conditional spec is `APPLICABLE` with an artifact/sections/evidence, or `N/A` with a concrete reason.

| Spec | Status | Owner | Reason | Artifact | Sections | Evidence |
|---|---|---|---|---|---|---|
| product_design_spec | APPLICABLE | BI-PF-1550 | Specification for prompt tokenization, encryption format, and packaging | engineering/design/BI-PF-1550.md | design_pack.requirements, design_pack.contracts.files | scripts/dev/prompt_compiler.py |
| api_contract | N/A | BI-PF-1550 | Offline build-time compilation CLI and internal in-memory Go library without public HTTP routes |  |  |  |
| data_contract | APPLICABLE | BI-PF-1550 | Encrypted binary asset bundle (.pfa) binary schema and header layout | engineering/design/BI-PF-1550.md | design_pack.contracts.files | scripts/dev/prompt_compiler.py |
| config_contract | APPLICABLE | BI-PF-1550 | PF_PROMPT_KEY and PF_PROMPT_BUNDLE configuration environment contract | engineering/design/BI-PF-1550.md | design_pack.contracts.config | scripts/dev/prompt_compiler.py |
| nfr_slo | APPLICABLE | BI-PF-1550 | Sub-10ms bundle decryption latency and zero scratch disk write enforcement | engineering/design/BI-PF-1550.md | design_pack.performance | test-framework/tests/pipeline/test_prompts_compiler.py |
| security_threat_model | APPLICABLE | BI-PF-1550 | Reverse engineering protection and authenticated cipher tamper rejection | engineering/design/BI-PF-1550.md | design_pack.security | scripts/dev/prompt_compiler.py |
| migration_backfill | N/A | BI-PF-1550 | Build-time packaging feature; no legacy database table backfill required |  |  |  |
| rollback_dr | APPLICABLE | BI-PF-1550 | Disable prompt compilation flag in packaging pipeline to revert cleanly | engineering/design/BI-PF-1550.md | design_pack.rollback | core/packaging.py |
| observability_runbook | APPLICABLE | BI-PF-1550 | Structured JSON logging with compilation duration, asset counts, and SHA-256 digests | engineering/design/BI-PF-1550.md | design_pack.observability | scripts/dev/prompt_compiler.py |
| accessibility_i18n | N/A | BI-PF-1550 | Backend packaging and compiler tooling with no end-user web UI elements |  |  |  |
| privacy_compliance | N/A | BI-PF-1550 | Operates on internal prompt assets and developer definitions; no customer PII |  |  |  |
| implementation_plan | APPLICABLE | BI-PF-1550 | Staged implementation: Go cipher package -> build-time compiler CLI -> packaging leakage scanner -> e2e tests | engineering/design/BI-PF-1550.md | design_pack.rollout | scripts/dev/prompt_compiler.py |
| release_verification | APPLICABLE | BI-PF-1550 | Automated pytest and Go test suite validating encryption, decryption, and leakage absence | engineering/design/BI-PF-1550.md | design_pack.test_matrix | test-framework/tests/pipeline/test_prompts_compiler.py |


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
