# Conditional Spec Pack — BI-PF-1536 — Gate tooling: deterministic review selection and skip closed items

- **Version:** 1
- **Status:** APPROVED
- **Functional spec:** engineering/specs/BI-PF-1536.md
- **Design pack:** engineering/design/BI-PF-1536.md

Every conditional spec is `APPLICABLE` with an artifact/sections/evidence, or `N/A` with a concrete reason.

| Spec | Status | Owner | Reason | Artifact | Sections | Evidence |
|---|---|---|---|---|---|---|
| product_design_spec | APPLICABLE | engineering | Review selection design is defined. | engineering/design/BI-PF-1536.md | 4 | scripts/dev/review_select.py |
| api_contract | N/A | engineering | No API change. |  |  |  |
| data_contract | N/A | engineering | No runtime data store. |  |  |  |
| config_contract | N/A | engineering | No config change. |  |  |  |
| nfr_slo | N/A | engineering | CI tooling only. |  |  |  |
| security_threat_model | N/A | security | No tenant/runtime data. |  |  |  |
| migration_backfill | N/A | engineering | No data migration. |  |  |  |
| rollback_dr | N/A | engineering | Revert the tooling PR. |  |  |  |
| observability_runbook | N/A | platform | Guard output is the observability. |  |  |  |
| accessibility_i18n | N/A | product | No user surface. |  |  |  |
| privacy_compliance | N/A | security | No personal data. |  |  |  |
| implementation_plan | APPLICABLE | engineering | Single selector helper plus two callers. | engineering/design/BI-PF-1536.md | 4 | scripts/dev/fix_guard.py, scripts/dev/architect_review.py |
| release_verification | N/A | release | CI tests cover behavior. |  |  |  |
