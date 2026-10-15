# EDP Ports & Adapters (persistence)

**Purpose:** one authoritative map of Product Forge's **persistence architecture** — every store is a
**port** with **swappable adapters**, so the backend (Postgres, S3, local disk, NFS, Google Drive, Redis,
MongoDB, …) can change **without touching domain code**. Companion to `docs/EDP-17-SCHEMA.md` (DB schema),
`docs/EDP-EXECUTION-ORDER.md` (order), and `go/datastore` (the ports).

## Principle
- **Domain depends on ports, never on a provider.** Ports live in `go/datastore` (`datastore.go`).
- **Every backend is an adapter** implementing a port.
- **`go/datastore/conformance.go`** (`ConformObjectStore`, `ConformRelationalStore`) proves an adapter
  conforms *before* it is plugged in — swap safely.
- **To change a backend: add an adapter.** No domain/query changes at the call sites.

## Ports → adapters (status)

| Port (in `go/datastore`) | Adapters: shipped / planned / later | Owning item |
|---|---|---|
| `RelationalStore` (SQL SoR) | **PostgreSQL (pgx)** shipped (`go/store/pg.go`) | EDP-17 (`BI-PF-1309`) |
| **Repository ports** (`TenantRepository`, `ProjectRepository`, …) | **PostgreSQL adapter** shipped (`go/store/pg_repos.go`); later another SQL DB / **MongoDB** = new adapter | EDP-17 |
| `ObjectStore` (bytes) | **local FS** (planned `BI-PF-1305`), **S3-compatible** (planned `BI-PF-1306`); later **NFS / Google Drive / Azure Blob / GCS** = new adapters | EDP-13/14 (`BI-PF-1305/1306`) |
| `CacheStore` | in-memory / Redis / file | EDP-19 |
| `SecretStore` | file / vault / cloud KMS | EDP (security) |
| `JobStore` / `OutboxStore` | PostgreSQL | EDP-19 (`BI-PF-1311`) |
| `MemoryRepository` / `SearchProvider` | PG FTS → pgvector | EDP-21 (`BI-PF-1313`) |
| `AuditStore` | append-only PostgreSQL | EDP-20 (`BI-PF-1312`) |
| `BackupProvider` | PITR / snapshot providers | EDP-23 (`BI-PF-1315`) |

## The two layers (don't confuse them)
1. **Provider port** (`RelationalStore`, `ObjectStore`, …) — neutral shape; lets you swap **providers of the
   same kind** (Postgres↔another SQL via a conformant adapter; local↔S3 object store).
2. **Repository port** (`TenantRepository`, `ProjectRepository`, …) — the **domain-facing** boundary. Swapping
   to a **different data model** (e.g. MongoDB) means a **new adapter implementing the repository ports** —
   not just a driver swap. This is why EDP-17 exposes repository ports in `go/store/store.go`.

> Note: the PostgreSQL adapter's *SQL* is Postgres-flavored (`$1`, `now()`), so a full relational-provider
> swap re-implements the adapter's SQL — that is expected; the ports keep it contained.

## Recipe: add a storage/DB adapter
1. Implement the port (e.g. `datastore.ObjectStore` or the repository interfaces) in a new file/module.
2. Add the shared **conformance** test (`ConformObjectStore`) and run it (self-skips/uses a local backend).
3. Wire it behind the port via config (no call-site changes).
4. Register any new config store in `config/store-registry.json`; raise a backlog item if the port is new.

## Status
- **Shipped:** Postgres `RelationalStore` adapter + repository ports (`go/store`, PR #178); schema + bootstrap
  (`docs/EDP-17-SCHEMA.md`).
- **Next:** `ObjectStore` local adapter (EDP-13 `BI-PF-1305`) → S3 (EDP-14 `BI-PF-1306`).
