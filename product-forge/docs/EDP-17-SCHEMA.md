# EDP-17 Canonical Schema — Domain & Relationship Model

**Owner:** EDP-17 (`BI-PF-1309`), epic `BI-PF-1292`. Migration: `product-forge/migrations/0002_core_schema.{up,down}.sql`.
**Source of truth for the backlog-side model:** `config/store-registry.json` (233 stores, 24 kinds) + `core/` owners + `api/routers/`.

## Reference conventions (must be mirrored as DB relationships)
- **Work traceability:** every artifact about work references **`item_id`** (`BI-####`); technical detail adds **`feature_id`** (`F-x`). These are **soft refs** (cross-scope/backlog may be in another scope) — indexed columns, not hard FKs.
- **Item ↔ epic:** an item has one parent (`epic`/`parent`); an epic holds `children[]` (membership). ⇒ `backlog_items.parent_id` self-FK.
- **Item ↔ item:** `links` keys (`cp_ids`, `iteration_ids`, `commit`, `artifacts`, `paired_with`, `backend_capability`, `capability_ref`), `dependencies`/`blocked_by` (`REQUIRES|BLOCKS|RELATED` + `required_state`), `unlocks`, and reciprocal **`paired_with`**. ⇒ `item_links` (from_id, to_id, type, required_state, reciprocal).
- **Pipeline:** tenant → memberships; tenant → projects → **runs** → **stages** → **attempts**. ⇒ FKs `runs.project_id`, `stages.run_id`, `attempts.stage_id`.
- **Agent work ledger:** keyed by `item_id`/`feature_id` ⇒ `agent_runs` soft-ref + FK to `agents`.
- **Tests:** test-run results keyed by `feature_id` ⇒ `test_runs`/`test_results` soft-ref `feature_id`.

## Domain ownership map
| Domain | Tables | Owner |
|---|---|---|
| Identity/tenancy/security | `tenants`, `memberships`, `roles`, `secrets_refs` | **EDP-17** (+RLS EDP-09) |
| Products/projects/packaging/deploy | `products`, `projects`, `releases`, `deployments` | **EDP-17** |
| Pipeline / dynamic workflow | `pipelines`, `pipeline_versions`, `stage_defs`, `transitions`, `runs`, `stages`, `attempts` | **EDP-17** |
| Agents / runtime env | `agents`, `agent_versions`, `agent_capabilities`, `agent_runs` | **EDP-17** |
| Multimodal / artifacts | `artifact_types`, `artifacts`, `stored_objects` | **EDP-15** (EDP-17 defines `artifact_types`) |
| Memory / RAG / embeddings | `memory_entries`, `memory_types`, `embeddings` (pgvector) | **EDP-21** |
| Events / jobs / outbox / cache | `events`, `outbox`, `jobs`, `leases`, `cache_entries` | **EDP-19** |
| Audit | `audit_log` (append-only) | **EDP-20** |
| Intake / PF backlogs / internal systems | `intake_items`, `backlog_items`, `epics`, `item_links`, `status_history` | **EDP-18** (cutover) |
| Usage / quotas | `usage`, `quotas` | **EDP-17** |
| Tests / evidence / traceability | `test_runs`, `test_results`, `evidence`, `traceability_edges` | **EDP-15/20** |
| Knowledge / registry / problems / insights | `knowledge_bases`, `registries`, `problems`, `insights` | **EDP-21/16** |
| UI/dashboard | — legacy/frozen; **no schema owner** (read-only projections) | — |

## Extensibility contract (every EDP table)
- **Tenant-scoped:** `tenant_id TEXT NOT NULL REFERENCES tenants(id)` + index (RLS added by EDP-09).
- **Mutable rows:** `version BIGINT NOT NULL DEFAULT 0` (optimistic concurrency) + `created_at`/`updated_at TIMESTAMPTZ`.
- **Work-referencing rows:** `item_id TEXT` (+ `feature_id TEXT`), indexed (soft refs).
- **Blobs:** one owner — `stored_objects` (EDP-15); metadata references it, never duplicates bytes.
- **IDs:** `TEXT` (opaque, ULID/uuid-shaped) — no DB-generated sequences (app/allocation owns ids).
- **Migrations** via `go/migrate` (`NNNN_*.up.sql`/`.down.sql`), applied by the deploy step (never on startup); roles from `0001_roles`.

## Slice 1 (this migration, `0002_core_schema`)
Delivered tables (EDP-17-owned core): `tenants`, `memberships`, `projects`, `runs`, `stages`, `attempts`, `usage`, `quotas`.
Deferred (owned by later items, attach by FK): `artifacts`/`stored_objects` (EDP-15), `events`/`jobs` (EDP-19), `audit_log` (EDP-20), `memory_*`/`embeddings` (EDP-21), `backlog_*`/`intake_*` (EDP-18), `agents`/`pipelines`/`releases` (next EDP-17 slices).

## Status
Model approved in principle; remaining EDP-17 slices (agents, pipelines, products/releases, artifact_types) + the Go DAL (`product-forge/go/store`) follow. Order model: `docs/EDP-EXECUTION-ORDER.md`.
