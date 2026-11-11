# Conditional Spec Pack — BI-PF-1527 — T1: validate team-scale capacity and guardrails

- **Version:** 1
- **Status:** PROPOSED
- **Functional spec:** engineering/specs/BI-PF-1527.md
- **Design pack:** engineering/design/BI-PF-1527.md

Every conditional spec is `APPLICABLE` with an artifact/sections/evidence, or `N/A` with a concrete reason.

| Spec | Status | Owner | Reason | Artifact | Sections | Evidence |
|---|---|---|---|---|---|---|
| product_design_spec | N/A | engineering | No user-facing UI in capacity validation. |  |  |  |
| api_contract | N/A | engineering | No new API. |  |  |  |
| data_contract | APPLICABLE | engineering | Synthetic T1 dataset and read-only DB. | engineering/design/BI-PF-1527.md | design_pack.data_model | config/edp-slo.json |
| config_contract | APPLICABLE | engineering | T1 profile and SLO config. | engineering/design/BI-PF-1527.md | design_pack.config_contract | config/edp-slo.json |
| nfr_slo | APPLICABLE | engineering | T1 SLOs. | engineering/design/BI-PF-1527.md | design_pack.performance | engineering/benchmarks/BI-PF-1527/README.md |
| security_threat_model | APPLICABLE | engineering | Read-only role/RLS. | engineering/design/BI-PF-1527.md | design_pack.security | docs/BACKLOG-AUTHORITY-RUNBOOK.md |
| migration_backfill | N/A | engineering | No schema migration in validation item. |  |  |  |
| rollback_dr | APPLICABLE | engineering | Restore drill and tier rollback. | engineering/design/BI-PF-1527.md | design_pack.rollback_recovery | docs/EDP-22-RUNBOOK.md |
| observability_runbook | APPLICABLE | engineering | SLO alerts/runbook. | engineering/design/BI-PF-1527.md | design_pack.observability | ops/prometheus/backlog-authority.rules.yml |
| accessibility_i18n | N/A | engineering | No user-facing localization or accessibility surface. |  |  |  |
| privacy_compliance | N/A | engineering | Synthetic data only. |  |  |  |
| implementation_plan | APPLICABLE | engineering | Harness ? load ? report ? HIL. | engineering/design/BI-PF-1527.md | design_pack.rollout | engineering/benchmarks/BI-PF-1527/README.md |
| release_verification | APPLICABLE | engineering | Capacity report + restore evidence. | engineering/design/BI-PF-1527.md | design_pack.test_matrix | engineering/benchmarks/BI-PF-1527/README.md |
