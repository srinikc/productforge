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
