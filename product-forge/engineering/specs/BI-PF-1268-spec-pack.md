# Conditional Spec Pack — BI-PF-1268 — Eventing SSOT (Go): event core - append-only store, emit, monotonic seq, cursor/since

- **Version:** 1
- **Status:** APPROVED
- **Functional spec:** engineering/specs/BI-PF-1268.md
- **Design pack:** engineering/design/BI-PF-1268.md

Every conditional spec is `APPLICABLE` with an artifact/sections/evidence, or `N/A` with a concrete reason.

| Spec | Status | Owner | Reason | Artifact | Sections | Evidence |
|---|---|---|---|---|---|---|
| product_design_spec | APPLICABLE | architecture | PG event core design defined. | engineering/design/BI-PF-1268.md | 4 | migrations/0024_events_authority.up.sql |
| api_contract | N/A | architecture | Internal A1 seam only; no public route change. |  |  |  |
| data_contract | APPLICABLE | architecture | events/outbox schema defined. | engineering/design/BI-PF-1268.md | 4 | migrations/0024_events_authority.up.sql |
| config_contract | APPLICABLE | architecture | Payload threshold and outbox flag defined. | engineering/specs/BI-PF-1268.md | config | engineering/specs/BI-PF-1268.md |
| nfr_slo | APPLICABLE | architecture | Cursor/outbox durability defined. | engineering/specs/BI-PF-1268.md | nfr | engineering/specs/BI-PF-1268.md |
| security_threat_model | N/A | security | Inherits EDP RLS/object policy; implementation test covers tenant binding. |  |  |  |
| migration_backfill | APPLICABLE | architecture | Migration 0024 and projection defined. | engineering/design/BI-PF-1268.md | 9 | migrations/0024_events_authority.up.sql |
| rollback_dr | APPLICABLE | architecture | Rollback to JSONL read path defined. | engineering/design/BI-PF-1268.md | 9 | engineering/design/BI-PF-1268.md |
| observability_runbook | APPLICABLE | platform | Outbox/cursor metrics defined. | engineering/design/BI-PF-1268.md | 8 | engineering/design/BI-PF-1268.md |
| accessibility_i18n | N/A | product | No user-facing surface. |  |  |  |
| privacy_compliance | N/A | security | No new personal data flow. |  |  |  |
| implementation_plan | APPLICABLE | architecture | Go core + migration + tests defined. | engineering/design/BI-PF-1268.md | 4 | engineering/design/BI-PF-1268.md |
| release_verification | N/A | release | CI tests and migration checks cover release. |  |  |  |
