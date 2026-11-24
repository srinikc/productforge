# Conditional Spec Pack — BI-PF-1566 — Canonical Memory Record Contract: schema definition, 6-type taxonomy classification, and storage mapping

- **Version:** 1
- **Status:** approved
- **Functional spec:** engineering/specs/BI-PF-1566.md
- **Design pack:** engineering/design/BI-PF-1566.md

Every conditional spec is `APPLICABLE` with an artifact/sections/evidence, or `N/A` with a concrete reason.

| Spec | Status | Owner | Reason | Artifact | Sections | Evidence |
|---|---|---|---|---|---|---|
| product_design_spec | APPLICABLE | BI-PF-1566 | Canonical Memory Record Contract and 6-type memory taxonomy specification | engineering/design/BI-PF-1566.md | Requirements, Contracts | engineering/design/BI-PF-1566.md |
| api_contract | APPLICABLE | BI-PF-1566 | Go package API contract and optional HTTP schema validation route /api/v1/memory/records/validate | engineering/design/BI-PF-1566.md | API Contract, Go API | go/memory/record.go |
| data_contract | APPLICABLE | BI-PF-1566 | MemoryRecord struct schema, 6-kind taxonomy enum, and authority tiers in Go | engineering/design/BI-PF-1566.md | Data Contract, Schema Invariants | go/memory/record.go |
| config_contract | APPLICABLE | BI-PF-1566 | Shared canonical legacy mapping table config/memory_legacy_mapping.json | config/memory_legacy_mapping.json | Taxonomy Mapping | config/memory_legacy_mapping.json |
| nfr_slo | APPLICABLE | BI-PF-1566 | Zero-allocation Go schema validation under 50 microseconds per record | engineering/design/BI-PF-1566.md | Performance | go/memory/record_test.go |
| security_threat_model | APPLICABLE | BI-PF-1566 | Multi-tenant tenant_id and project_id isolation with fail-closed validation | engineering/design/BI-PF-1566.md | Security Threat Model | go/memory/record_test.go |
| migration_backfill | N/A | BI-PF-1566 | Stateless schema contract in Go; no database backfill or state rewrite required in this item |  |  |  |
| rollback_dr | APPLICABLE | BI-PF-1566 | Reverting git commit for go/memory package and mapping json with zero downstream runtime side effects | engineering/design/BI-PF-1566.md | Rollback Plan | engineering/design/BI-PF-1566.md |
| observability_runbook | APPLICABLE | BI-PF-1566 | Thread-safe audit hook SetAuditCallback for validation metrics and rejection logging | engineering/design/BI-PF-1566.md | Observability | go/memory/record.go |
| accessibility_i18n | N/A | BI-PF-1566 | Backend pure Go data contract with no user-facing UI or internationalization surface |  |  |  |
| privacy_compliance | APPLICABLE | BI-PF-1566 | Enforces tenant boundary checks and prevents cross-tenant memory record leakage | engineering/design/BI-PF-1566.md | Privacy and Multi-Tenancy | go/memory/record.go |
| implementation_plan | APPLICABLE | BI-PF-1566 | Step-by-step Go implementation, unit testing, and taxonomy integration plan | engineering/design/BI-PF-1566.md | Implementation Plan | engineering/design/BI-PF-1566.md |
| release_verification | APPLICABLE | BI-PF-1566 | Go test suite covering 16/16 unit tests for all taxonomy kinds and validation rules | engineering/design/BI-PF-1566.md | Test Matrix | go/memory/record_test.go |


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
