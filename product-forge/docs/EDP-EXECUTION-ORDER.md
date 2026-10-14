# EDP Execution Order (Enterprise Data Plane)

**Scope:** the authoritative execution order + dependencies for **EPIC `BI-PF-1292` (Enterprise Data Plane — DB & Storage)**.
Companion to `docs/Product_Forge_Enterprise_Performance_Security_DB_Storage_Roadmap.md` (§15) and `docs/merge-drift-conflict-github.md`.
Owner of the machine state: the **backlog** (`BI-PF-1292.children[]` + each item's `blocked_by`/`dependencies`). This document is the human-readable mirror; the backlog stays the SSOT.

> **Correction (BI-PF-1388):** the epic was previously ordered **isolation-first** (EDP-09 RLS before EDP-17 schema). RLS attaches to tables, so the **schema + data-access layer must come first**. The order below is schema/DAL-first and is reflected in the backlog dependencies (across all waves).

## Ordering principle
1. **Foundation:** ADR + migration framework + storage interfaces (EDP-01/07/08; threat model EDP-04).
2. **Schema & data access:** the canonical PostgreSQL **schema + DAL/CRUD + pooling + optimistic versioning** (**EDP-17**) — everything else attaches to it.
3. **Isolation on the schema:** tenant context + **RLS** (EDP-09), limits/quotas (EDP-10), residency registry/resolver (EDP-05/11/12).
4. **Data-plane services:** object store adapters (EDP-13/14), stored_objects/artifacts (EDP-15), lifecycle (EDP-16), job/outbox (EDP-19), audit (EDP-20), memory (EDP-21), cutover (EDP-18).
5. **Hardening:** backup/PITR (EDP-23), benchmarks/SLO (EDP-22), scale-out (EDP-24, evidence-gated).

## Wave-by-wave (corrected)

| Wave | Items | Depends on |
|---|---|---|
| **W0 — foundation** | EDP-01 ✅ · EDP-02 ✅ · EDP-03 ✅ · EDP-04 ✅ · EDP-07 ✅ · EDP-08 ✅ · **EDP-06** (baseline perf) | ADR / BI-PF-1300 |
| **W1 — schema & data access** | **EDP-17** (canonical PG schema + DAL/CRUD + pooling + optimistic versioning) · EDP-05 (residency policy registry) · EDP-13 (local ObjectStore adapter) | EDP-17 ← EDP-08/1300 · EDP-05 ← EDP-04 · EDP-13 ← EDP-07/EDP-04 |
| **W2 — isolation** | **EDP-09** (tenant context + RLS) · EDP-10 (limits/quotas) · EDP-14 (S3 adapter) · EDP-11 (RegionResolver) | EDP-09 ← EDP-17/EDP-04 · EDP-10 ← EDP-17 · EDP-14 ← EDP-13 · EDP-11 ← EDP-05 |
| **W3 — data-plane services** | EDP-15 (stored_objects/artifacts) · EDP-18 (cutover) · EDP-19 (job/outbox) · EDP-20 (audit) · EDP-12 (residency manifest) | EDP-15 ← EDP-17/EDP-13/EDP-09 · EDP-18 ← EDP-17/EDP-15 · EDP-19 ← EDP-17 · EDP-20 ← EDP-17/EDP-15 · EDP-12 ← EDP-11 |
| **W4 — memory & lifecycle** | EDP-21 (memory repository) · EDP-16 (object lifecycle) · EDP-23 (backup/PITR) | EDP-21 ← EDP-17/EDP-15 · EDP-16 ← EDP-15 · EDP-23 ← EDP-18 |
| **W5 — hardening** | EDP-22 (benchmarks/SLO) | ← EDP-18/19/20/21 |
| **W6 — scale-out** | EDP-24 (evidence-gated) | ← EDP-22/EDP-23 |

## Dependency edges (corrected, by item)

| Item | blocked_by | Notes |
|---|---|---|
| EDP-17 | EDP-08 (`BI-PF-1300`) | **schema before everything** (corrected) |
| EDP-09 | EDP-04 (`BI-PF-1296`), **EDP-17 (`BI-PF-1309`)** | RLS needs the schema (corrected) |
| EDP-10 | EDP-17 | quotas need the schema |
| EDP-15 | EDP-17, EDP-13, EDP-09 | artifacts metadata needs schema + store + RLS |
| EDP-18 | EDP-17, EDP-15 | cutover after schema + artifact store |
| EDP-19 | EDP-17 | job/outbox tables |
| EDP-20 | EDP-17, EDP-15 | audit tables + artifacts |
| EDP-21 | EDP-17, EDP-15 | memory metadata + objects |
| EDP-16 | EDP-15 | lifecycle over objects |
| EDP-14 | EDP-13 | S3 after local adapter |
| EDP-11 | EDP-05 | RegionResolver after residency registry |
| EDP-12 | EDP-11 | manifest after resolver |
| EDP-23 | EDP-18 | backup after cutover |
| EDP-22 | EDP-18, EDP-19, EDP-20, EDP-21 | benchmarks after data-plane services |
| EDP-24 | EDP-22, EDP-23 | scale-out, evidence-gated |

## Known blockers to "fully correct"
- **`BI-PF-1388`** — `POST /items/{id}/dependencies` with `blocked_by` updates the flat field but **does not clear the structured `dependencies`**, so a stale `REQUIRES` edge keeps the cycle-guard from accepting the corrected edge (observed: `EDP-09 ← EDP-17`). Fix: `blocked_by` must replace/clear the structured REQUIRES edges it owns.
- **Derived index drift** — `backlog.get`/`get_epic` reads the derived `open.json`/`closed.json`; if those are stale vs `items/`, item `GET`s return `NOT_FOUND`. Rebuild indexes on write (or make `get` fall back to `items/`).

## Maintenance
When the order changes, update it **in the backlog first** (item `blocked_by`/`dependencies` + epic `execution_order`), then update this document. Cited decisions are append-only.
