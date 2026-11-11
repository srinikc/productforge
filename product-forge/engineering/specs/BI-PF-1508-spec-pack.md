# Conditional Spec Pack — BI-PF-1508 — PF-SB pilot: EDP backlog authority readiness endpoint

- **Version:** 1
- **Status:** APPROVED
- **Functional spec:** engineering/specs/BI-PF-1508.md
- **Design pack:** engineering/design/BI-PF-1508.md

Every conditional spec is `APPLICABLE` with an artifact/sections/evidence, or `N/A` with a concrete reason.

| Spec | Status | Owner | Reason | Artifact | Sections | Evidence |
|---|---|---|---|---|---|---|
| product_design_spec | N/A | engineering | Backend admin API only; no user-facing UI. |  |  |  |
| api_contract | APPLICABLE | engineering | New admin endpoint contract. | engineering/design/BI-PF-1508.md | design_pack.contracts.api, design_pack.runtime_contract | go/edpsvc/main.go |
| data_contract | APPLICABLE | engineering | Counter migration and global reservation counter. | engineering/design/BI-PF-1508.md | design_pack.data_model, design_pack.contracts.db | migrations/0018_backlog_reservation_counter.up.sql |
| config_contract | APPLICABLE | engineering | Admin token and runtime DB config. | engineering/design/BI-PF-1508.md | design_pack.contracts.config | go/edpsvc/main.go |
| nfr_slo | APPLICABLE | engineering | Readiness and latency SLO. | engineering/design/BI-PF-1508.md | design_pack.performance | ops/prometheus/backlog-authority.rules.yml |
| security_threat_model | APPLICABLE | engineering | Admin-only access and tenant-scoped RLS. | engineering/design/BI-PF-1508.md | design_pack.security | go/edpsvc/main.go |
| migration_backfill | APPLICABLE | engineering | 0018 counter migration. | engineering/design/BI-PF-1508.md | design_pack.rollout | migrations/0018_backlog_reservation_counter.up.sql |
| rollback_dr | APPLICABLE | engineering | Migration down and route rollback. | engineering/design/BI-PF-1508.md | design_pack.rollback | migrations/0018_backlog_reservation_counter.down.sql |
| observability_runbook | APPLICABLE | engineering | Metrics/alert/runbook. | engineering/design/BI-PF-1508.md | design_pack.observability | docs/BACKLOG-AUTHORITY-RUNBOOK.md, ops/prometheus/backlog-authority.rules.yml |
| accessibility_i18n | N/A | engineering | No UI or localized content. |  |  |  |
| privacy_compliance | N/A | engineering | No new PII or regulated data. |  |  |  |
| implementation_plan | APPLICABLE | engineering | Endpoint, migration, rule, runbook order. | engineering/design/BI-PF-1508.md | design_pack.rollout | docs/BACKLOG-AUTHORITY-RUNBOOK.md |
| release_verification | APPLICABLE | engineering | Tests and alert/runbook verification. | engineering/design/BI-PF-1508.md | design_pack.test_matrix | go/edpsvc/main_test.go |
