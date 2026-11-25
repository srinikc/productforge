# Conditional Spec Pack — BI-PF-1266 — Eventing SSOT: ADR + design (Go-first bus, Python thin client, no-duplication, migration)

- **Version:** 1
- **Status:** APPROVED
- **Functional spec:** engineering/specs/BI-PF-1266.md
- **Design pack:** engineering/design/BI-PF-1266.md

Every conditional spec is `APPLICABLE` with an artifact/sections/evidence, or `N/A` with a concrete reason.

| Spec | Status | Owner | Reason | Artifact | Sections | Evidence |
|---|---|---|---|---|---|---|
| product_design_spec | APPLICABLE | architecture | Event authority and architecture are defined. | docs/EVENTING-ALERTING-SSOT-DESIGN.md | 3, 4, 6, 7 | docs/ARCHITECTURE-DECISIONS.md, docs/EVENTING-ALERTING-SSOT-DESIGN.md |
| api_contract | N/A | architecture | No request/response contract delta in this design item; existing events routes keep their shape and BI-PF-1274 implements cursor reads. |  |  |  |
| data_contract | APPLICABLE | architecture | PostgreSQL event row, cursor, and outbox are defined. | docs/EVENTING-ALERTING-SSOT-DESIGN.md | 4 | docs/ARCHITECTURE-DECISIONS.md |
| config_contract | APPLICABLE | architecture | Deployment payload/retention thresholds and startup validation are defined. | docs/EVENTING-ALERTING-SSOT-DESIGN.md | 4, 6 | docs/ARCHITECTURE-DECISIONS.md, docs/EVENTING-ALERTING-SSOT-DESIGN.md |
| nfr_slo | APPLICABLE | architecture | Cursor durability and outbox delivery are defined. | docs/EVENTING-ALERTING-SSOT-DESIGN.md | 4, 8 | docs/EVENTING-ALERTING-SSOT-DESIGN.md |
| security_threat_model | APPLICABLE | security | RLS/runtime-role and object-reference boundaries are defined. | docs/EVENTING-ALERTING-SSOT-DESIGN.md | 4, 8 | docs/ARCHITECTURE-DECISIONS.md, docs/EVENTING-ALERTING-SSOT-DESIGN.md |
| migration_backfill | APPLICABLE | architecture | JSONL projection and staged cutover are defined. | docs/EVENTING-ALERTING-SSOT-DESIGN.md | 5, 9, 10 | docs/EVENTING-ALERTING-SSOT-DESIGN.md |
| rollback_dr | APPLICABLE | architecture | Rollback to the existing read path is required. | docs/EVENTING-ALERTING-SSOT-DESIGN.md | 9, 10 | docs/ARCHITECTURE-DECISIONS.md |
| observability_runbook | APPLICABLE | platform | Outbox lag/DLQ/cursor health are named. | docs/EVENTING-ALERTING-SSOT-DESIGN.md | 8 | docs/EVENTING-ALERTING-SSOT-DESIGN.md |
| accessibility_i18n | N/A | product | No user-facing surface in this design item. |  |  |  |
| privacy_compliance | N/A | security | No new personal-data flow is introduced by this design. |  |  |  |
| implementation_plan | APPLICABLE | architecture | Phased delivery is defined. | docs/EVENTING-ALERTING-SSOT-DESIGN.md | 9 | docs/EVENTING-ALERTING-SSOT-DESIGN.md |
| release_verification | N/A | release | Design-only item; release verification lands with implementation. |  |  |  |
