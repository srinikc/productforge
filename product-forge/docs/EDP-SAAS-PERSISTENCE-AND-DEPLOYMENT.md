# PF Persistence, Storage & SaaS Deployment

How Product Forge persists data, how DB and object storage are configured (and swapped), and what is required
to run PF as a multi-tenant SaaS. Owner: EDP (epic `BI-PF-1292`). Related: `docs/EDP-STORAGE-ADAPTERS.md`,
`docs/EDP-17-SCHEMA.md`, `config/store-registry.json`.

## 1. Persistence model (what lives where)

| Data | Where | Status |
|---|---|---|
| Runtime domain data (tenants/projects/runs/jobs/audit/memory/artifacts-meta/backlog_items…) | **PostgreSQL** (27 tables) | ✅ schema done |
| Payload bytes (files/blobs/artifacts/evidence) | **Object store** (local FS or S3), keyed by sha256 | ✅ adapter done |
| Global authored config | **Files / git** (54 stores) | ✅ by design |
| Derived projections | **DB views** (61) or regenerated files (7) | ✅ views done |
| Canonical backlog (control plane) | **Files today** → **Postgres (cutover in progress, `BI-PF-1399`)** | ⬜ cutover pending |

## 2. Why the control plane still uses files
ADR-0006: the HTTP API contract stays stable; only the **storage backend changes behind a cutover**. The EDP
data plane (Postgres schema + Go services + APIs) is built **behind** the control plane, but `core/*` (Python)
has **not been switched** to read/write it yet. That switch is `BI-PF-1399` (+ `BI-PF-1310` migration tooling).

## 3. Database — configure & customize
- The app is **DSN-driven**: set **`PF_DB_DSN`** (e.g. `postgres://pf_app:…@host:5432/productforge?sslmode=require`).
- **Any Postgres 16+ works** — local Docker (dev) or **managed** (RDS, Aurora, Cloud SQL, Neon, Supabase/Citus).
  No code change: point the DSN at the target.
- **Roles** (`migrations/0001_roles`): `pf_owner` (migrate), **`pf_runtime`/`pf_app`** (app, RLS-enforced),
  `pf_readonly`, `pf_backup`, `pf_admin` (`BYPASSRLS`).
- **Migrations are an explicit deploy step** (never on startup): `pfmigrate up` via `scripts/dev/db_migrate.py`.
- Pooling: `go/store` `PoolOptions` (max/min conns, timeouts), env-overridable.

## 4. Object storage — configure & customize
Select the adapter and its target with env vars (EDP-13/14):
- **Local:** `PF_OBJECT_BACKEND=local`, `PF_OBJECT_ROOT=<dir>`.
- **S3-compatible:** `PF_OBJECT_BACKEND=s3` + `PF_S3_ENDPOINT`, `PF_S3_BUCKET`, `PF_S3_ACCESS_KEY`,
  `PF_S3_SECRET_KEY`, `PF_S3_REGION`, `PF_S3_USE_SSL`.
- **Other backends** (NFS, Google Drive, Azure Blob, GCS, …) = **new adapters** implementing the same
  `datastore.ObjectStore` port + passing `ConformObjectStore` (tracked: `BI-PF-1395`). No domain changes.

## 5. Deploy workflow (dev → SaaS)
1. **Provision** Postgres (docker for dev; managed for prod) and an object store (local dir or S3 bucket).
2. **Roles** — apply `0001_roles`.
3. **Migrate** — `python scripts/dev/db_migrate.py up` (or `pfmigrate up`); idempotent, versioned.
4. **Bootstrap** — `python scripts/dev/db_bootstrap.py` (applies migrations; sets the `pf_app` dev password).
5. **Run services** — `python scripts/dev/dev_server.py` (control-plane API) and
   `python scripts/dev/run_edpsvc.py` (EDP data-plane API).
6. **Persist** — data in PG storage / object bucket; backups are EDP-23 (pending).

## 6. SaaS readiness checklist (gaps)
- ⬜ **Secrets manager** (Vault/KMS) instead of env vars for DB/storage creds.
- ⬜ **TLS**: prod DSN `sslmode=require|verify-full`.
- ⬜ **Per-tenant / per-region storage & DB routing** (residency) — EDP-11/12.
- ⬜ **Backup / PITR / restore drills** — EDP-23.
- ⬜ **IaC / one-command provisioning** — see §7 (automation backlog).
- ⬜ **Control-plane cutover to DB** — `BI-PF-1399`.

## 7. Automation (what a script should do — no manual steps)
A single bootstrap/automation entrypoint should (dev **and** SaaS), idempotently:
provision DB + roles → run migrations → bootstrap → configure object storage → wire env/secrets →
verify (healthchecks + parity). Tracked as a backlog item (see below). Until then, the manual scripts are
§5 steps 3–5.

## 8. Related items
`BI-PF-1399` (control-plane SoR cutover) · `BI-PF-1310`/EDP-18 (migration tooling) · `BI-PF-1395` (extra
storage adapters) · EDP-11/12 (residency) · EDP-23 (backup) · **automation item** (provisioning/migrations).
