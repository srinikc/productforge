# Conditional Spec Pack — BI-PF-1552 — Dual-Engine RAG and Memory Storage Adapter: embedded SQLite-vss for local editions and PostgreSQL pgvector for enterprise

- **Version:** 1
- **Status:** approved
- **Functional spec:** engineering/specs/BI-PF-1552.md
- **Design pack:** docs/DUAL-VECTOR-STORE-DESIGN.md

Every conditional spec is `APPLICABLE` with an artifact/sections/evidence, or `N/A` with a concrete reason.

| Spec | Status | Owner | Reason | Artifact | Sections | Evidence |
|---|---|---|---|---|---|---|
| product_design_spec | APPLICABLE | BI-PF-1552 | Dual-engine vector and memory storage adapter specification | docs/DUAL-VECTOR-STORE-DESIGN.md | Section 1, Section 2, Section 3 | docs/DUAL-VECTOR-STORE-DESIGN.md |
| api_contract | APPLICABLE | BI-PF-1552 | datastore.MemoryRepository Go interface contract and edpsvc memory endpoints | docs/DUAL-VECTOR-STORE-DESIGN.md | Section 2, Section 3 | go/dualvec/dualvec.go |
| data_contract | APPLICABLE | BI-PF-1552 | MemoryEntry schema, float blob packing, and PostgreSQL memory table contract | docs/DUAL-VECTOR-STORE-DESIGN.md | Section 3 | go/dualvec/sqlite_store.go |
| config_contract | APPLICABLE | BI-PF-1552 | PF_MEMORY_DSN environment variable and dualvec.Config structure | docs/DUAL-VECTOR-STORE-DESIGN.md | Section 1, Section 3 | go/dualvec/dualvec.go |
| nfr_slo | APPLICABLE | BI-PF-1552 | Pure Go zero-allocation vector comparison and low-latency retrieval SLOs | docs/DUAL-VECTOR-STORE-DESIGN.md | Section 4 | go/dualvec/dualvec_test.go |
| security_threat_model | APPLICABLE | BI-PF-1552 | Cross-tenant and cross-project memory isolation and ACL privacy enforcement | docs/DUAL-VECTOR-STORE-DESIGN.md | Section 2, Section 3 | go/dualvec/dualvec_test.go |
| migration_backfill | N/A | BI-PF-1552 | New dual-engine storage adapter with idempotent CREATE TABLE IF NOT EXISTS on startup; no backfill needed |  |  |  |
| rollback_dr | APPLICABLE | BI-PF-1552 | Fail-closed typed errors and zero-impact fallback by unsetting PF_MEMORY_DSN | docs/DUAL-VECTOR-STORE-DESIGN.md | Section 4, Section 5 | docs/DUAL-VECTOR-STORE-DESIGN.md |
| observability_runbook | APPLICABLE | BI-PF-1552 | Structured logs and Prometheus metrics dualvec_operations_total and dualvec_duration_seconds | docs/DUAL-VECTOR-STORE-DESIGN.md | Section 4 | go/dualvec/dualvec.go |
| accessibility_i18n | N/A | BI-PF-1552 | Backend data plane storage layer; zero user-interface elements |  |  |  |
| privacy_compliance | APPLICABLE | BI-PF-1552 | Server-side ACL boundary checks ensuring private entries are visible only to authenticated owner | docs/DUAL-VECTOR-STORE-DESIGN.md | Section 3 | go/dualvec/dualvec_test.go |
| implementation_plan | APPLICABLE | BI-PF-1552 | Staged delivery: go/dualvec package -> shared tests -> edpsvc integration | docs/DUAL-VECTOR-STORE-DESIGN.md | Section 5 | docs/DUAL-VECTOR-STORE-DESIGN.md |
| release_verification | APPLICABLE | BI-PF-1552 | Shared conformance test suite and negative leakage tests across both backends | docs/DUAL-VECTOR-STORE-DESIGN.md | Section 6 | go/dualvec/dualvec_test.go |


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
