# Conditional Spec Pack — BI-PF-1534 — EDP: fail closed for unlisted backlog scopes when DB mode is on

- **Version:** 1
- **Status:** PROPOSED
- **Functional spec:** engineering/specs/BI-PF-1534.md
- **Design pack:** engineering/design/BI-PF-1534.md

Every conditional spec is `APPLICABLE` with an artifact/sections/evidence, or `N/A` with a concrete reason.

| Spec | Status | Owner | Reason | Artifact | Sections | Evidence |
|---|---|---|---|---|---|---|
| product_design_spec | N/A | core | No user-facing UI; this is a runtime authority guard. |  |  |  |
| api_contract | N/A | core | No API change. |  |  |  |
| data_contract | N/A | core | No schema change. |  |  |  |
| config_contract | APPLICABLE | core | Scope allowlist and DB mode behavior. | engineering/design/BI-PF-1534.md | design_pack.config_contract | config/env-flags.json |
| nfr_slo | APPLICABLE | core | No hot-path regression. | engineering/design/BI-PF-1534.md | design_pack.performance_capacity | docs/BACKLOG-DB-SSOT.md |
| security_threat_model | APPLICABLE | core | Fail-closed isolation guard. | engineering/design/BI-PF-1534.md | design_pack.security_model | core/backlog.py |
| migration_backfill | N/A | core | No migration. |  |  |  |
| rollback_dr | APPLICABLE | core | Explicit off rollback. | engineering/design/BI-PF-1534.md | design_pack.rollback_recovery | docs/BACKLOG-DB-SSOT.md |
| observability_runbook | APPLICABLE | core | Error code/runbook. | engineering/design/BI-PF-1534.md | design_pack.observability | docs/BACKLOG-DB-SSOT.md |
| accessibility_i18n | N/A | core | No user-facing/localized content; backend guard only. |  |  |  |
| privacy_compliance | N/A | core | No new data. |  |  |  |
| implementation_plan | APPLICABLE | core | Guard + tests + docs. | engineering/design/BI-PF-1534.md | design_pack.deployment_rollout | docs/BACKLOG-DB-SSOT.md |
| release_verification | APPLICABLE | core | Tests and runbook. | engineering/design/BI-PF-1534.md | design_pack.test_matrix | test-framework/tests/pipeline/test_backlog_db_cutover.py |
