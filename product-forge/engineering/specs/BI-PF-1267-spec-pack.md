# Conditional Spec Pack — BI-PF-1267 — Eventing SSOT: contracts (envelope+seq, subscription, alert-rule, webhook signature) + Go parity

- **Version:** 1
- **Status:** APPROVED
- **Functional spec:** engineering/specs/BI-PF-1267.md
- **Design pack:** engineering/design/BI-PF-1267.md

Every conditional spec is `APPLICABLE` with an artifact/sections/evidence, or `N/A` with a concrete reason.

| Spec | Status | Owner | Reason | Artifact | Sections | Evidence |
|---|---|---|---|---|---|---|
| product_design_spec | APPLICABLE | architecture | Contract shapes are defined. | engineering/design/BI-PF-1267.md | 4 | core/contracts.py |
| api_contract | N/A | architecture | No public runtime API shape change in this contract item. |  |  |  |
| data_contract | APPLICABLE | architecture | Envelope/subscription/alert/webhook fields are defined. | engineering/design/BI-PF-1267.md | 4 | core/contracts.py |
| config_contract | APPLICABLE | platform (BI-PF-1270) | WEBHOOK_HMAC_KEY_REF is a required secret reference; runtime startup validation is owned by BI-PF-1270. | engineering/design/BI-PF-1267.md | 4, 5 | core/contracts.py |
| nfr_slo | N/A | architecture | No runtime SLO in this contract-only item. |  |  |  |
| security_threat_model | APPLICABLE | security | HMAC and tenant fields are security-relevant. | engineering/design/BI-PF-1267.md | 5 | core/contracts.py, go/pfcore/contracts.go, test-framework/tests/pipeline/test_contracts.py |
| migration_backfill | N/A | architecture | No data migration in contract-only item. |  |  |  |
| rollback_dr | N/A | architecture | Revert the code change; no data migration. |  |  |  |
| observability_runbook | N/A | platform | No runtime component in this item. |  |  |  |
| accessibility_i18n | N/A | product | No user-facing surface. |  |  |  |
| privacy_compliance | N/A | security | No new personal data flow. |  |  |  |
| implementation_plan | APPLICABLE | architecture | Python/Go parity implementation is defined. | engineering/design/BI-PF-1267.md | 4 | core/contracts.py, go/pfcore/contracts.go, test-framework/tests/pipeline/test_contracts.py |
| release_verification | N/A | release | Contract parity is covered by CI tests. |  |  |  |
