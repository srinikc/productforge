# Conditional Spec Pack — BI-PF-1531 — EDP: make PostgreSQL backlog authority the default for PF-SB and PF-GP scopes

- **Version:** 1
- **Status:** APPROVED
- **Functional spec:** engineering/specs/BI-PF-1531.md
- **Design pack:** engineering/design/BI-PF-1531.md

Every conditional spec is `APPLICABLE` with an artifact/sections/evidence, or `N/A` with a concrete reason.

| Spec | Status | Owner | Reason | Artifact | Sections | Evidence |
|---|---|---|---|---|---|---|
| product_design_spec | N/A | engineering | No user-facing UI or interaction change; backend/data-path only. |  |  |  |
| api_contract | N/A | engineering | No new public API; existing edpsvc /backlog routes and payloads are unchanged. |  |  |  |
| data_contract | APPLICABLE | engineering | Adds composite backlog key and traceability index. | engineering/design/BI-PF-1531.md | design_pack.data_model, design_pack.contracts.db | migrations/0021_backlog_scoped_uniqueness.up.sql, migrations/0022_traceability_tenant_index.up.sql |
| config_contract | APPLICABLE | engineering | Adds default-on mode and scoped allowlist. | engineering/design/BI-PF-1531.md | design_pack.runtime_contract, design_pack.contracts.config | config/env-flags.json, .env.example |
| nfr_slo | APPLICABLE | engineering | Adds performance/no-regression requirements. | engineering/design/BI-PF-1531.md | design_pack.performance, design_pack.observability | engineering/evidence/BI-PF-1531/bench-t1.json |
| security_threat_model | APPLICABLE | engineering | Tenant/RLS and fail-closed behavior change. | engineering/design/BI-PF-1531.md | design_pack.security_model, design_pack.rls_tenant | docs/BACKLOG-DB-SSOT.md |
| migration_backfill | APPLICABLE | engineering | Schema expansion, backfill, parity, and preflight are in scope. | engineering/design/BI-PF-1531.md | design_pack.deployment_rollout, design_pack.rollback_recovery | migrations/0021_backlog_scoped_uniqueness.up.sql, engineering/evidence/BI-PF-1531/parity.txt |
| rollback_dr | APPLICABLE | engineering | Rollback/export and backup/restore are required. | engineering/design/BI-PF-1531.md | design_pack.rollback_recovery, design_pack.rollback | engineering/evidence/BI-PF-1531/failclosed-rollback-tests.txt, docs/BACKLOG-DB-SSOT.md |
| observability_runbook | APPLICABLE | engineering | Authority failures must be observable and documented. | engineering/design/BI-PF-1531.md | design_pack.observability | docs/BACKLOG-DB-SSOT.md |
| accessibility_i18n | N/A | engineering | No user interface or localized content. |  |  |  |
| privacy_compliance | N/A | engineering | No new PII, consent, or regulated data; tenant isolation is preserved. |  |  |  |
| implementation_plan | APPLICABLE | engineering | Ordered migration/cutover/PR sequence is required. | engineering/design/BI-PF-1531.md | design_pack.deployment_rollout, design_pack.test_matrix | engineering/evidence/BI-PF-1531/current-sha-control.txt |
| release_verification | APPLICABLE | engineering | CI/parity/rollback verification is required before enablement. | engineering/design/BI-PF-1531.md | design_pack.rollout, design_pack.test_matrix, design_pack.ac_evidence | engineering/evidence/BI-PF-1531/current-sha-control.txt |
