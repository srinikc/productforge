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
| `ObjectStore` (bytes) | **local FS** shipped (`go/objstore`, EDP-13), **S3-compatible** shipped (`go/s3store`, EDP-14), **GCS** shipped (`go/gcsstore`, BI-PF-1395); **Azure Blob / Google Drive** planned (new adapters); **NFS/SMB = `objstore` over a mount** (no new adapter) | EDP-13/14 (`BI-PF-1305/1306`) |
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

## ObjectStore adapters — current state (BI-PF-1395)

| backend | module | status | notes |
|---|---|---|---|
| Local FS / NFS / SMB | `go/objstore` | **shipped** | confined root, atomic writes, sha256; use over an NFS/SMB **mount** — no separate adapter (reuse, not a clone) |
| S3-compatible | `go/s3store` | **shipped** | minio-go (EDP-14) |
| Google Cloud Storage | `go/gcsstore` | **shipped (mock-conformant)** | stdlib REST via `go/objstorerest`; real-provider qualification (creds) pending |
| Azure Blob | — | planned | next adapter on `objstorerest` |
| Google Drive | — | planned | key<->fileID model must be designed first (no `/` paths, non-unique names, trash-vs-delete) |

**Shared core — `go/objstorerest`:** stdlib-only (auth/token seam, bounded retry/backoff honoring `Retry-After`,
context deadlines, portable error taxonomy, secret redaction). New REST adapters build on it; **no provider SDK**.

**Conformance honesty:** `datastore.ConformObjectStore` now uses a **unique** probe key, asserts real `List`
prefix filtering, and **capability honesty** (a *declared* capability must actually work). Mock/emulator
conformance is **not** provider parity — a real-provider run (creds) is required before an adapter is called
production-qualified.

**Wiring (one line — owner: `go/edpsvc/main.go` `buildObjectStore()`):**
```go
// --- object store backend selection (config-only; no call-site change) ---
case "gcs":
    st, err = gcsstore.New(gcsstore.Config{Bucket: os.Getenv("PF_GCS_BUCKET"), Auth: gcsAuth})
// "local" (objstore) and "s3" (s3store) already handled; "azure"/"gdrive" land per adapter item
```

**Known limitations (`gcsstore`, BI-PF-1395):** content is **buffered in memory** (large-object streaming +
resumable upload is a follow-up); GCS `uploadType=multipart` caps at **~5 MB** (use resumable for larger);
`SignedURL`/versioning/lock are **not implemented** (capabilities declared `false`). The `buildObjectStore()`
config switch is owned by `go/edpsvc/main.go` (apply the one-line case above). The adapter is
**mock-conformant, NOT production-qualified** until a real-provider (creds) run.
