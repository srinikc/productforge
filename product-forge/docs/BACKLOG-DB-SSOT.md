# Backlog DB SSOT and One-Writer Cutover

**Scope:** all Product Forge backlog scopes. PF-SB (`product_forge`) and PF-GP (generated product scopes)
share the same PostgreSQL backlog store, the same Go writer, and one global ID authority.

## Authority

- **Item writes:** Go `edpsvc` → `edpdata.BacklogStore` → PostgreSQL `backlog_items`.
- **ID writes:** Go `edpsvc /backlog/ids:reserve` → one global
  `backlog_id_allocations` row + idempotent `backlog_id_reservations`.
- **Python:** `core/backlog.py` and `core/id_allocator.py` are thin HTTP clients in DB mode.
- **No fallback:** when `PF_BACKLOG_DB=on`, there is no Git/local ID allocation for any scope.
- **One global ID space:** PF-SB and PF-GP never receive the same numeric ID, even if they use the
  same tag. Scope/project still partition the backlog item rows.

## Migration

Apply migrations through `0021_backlog_scoped_uniqueness` with the normal explicit deploy migration step. Migration 0021 allows legacy duplicate IDs across tenants while new IDs remain globally unique.

It creates:

- `backlog_id_allocations` with one `global` authority row
- `backlog_id_reservations`
- global seed `1508` (1507 remains quarantined)

## Backfill

```bash
PF_EDP_API_URL=http://127.0.0.1:8030 \
PF_EDP_TOKEN=... \
python scripts/dev/backlog_db_backfill.py --dry-run

PF_EDP_API_URL=http://127.0.0.1:8030 \
PF_EDP_TOKEN=... \
python scripts/dev/backlog_db_backfill.py
```

The backfill scans PF-SB and generated-product item files. It is idempotent because
`BacklogStore.Put` upserts by `(tenant_id, id)`.

Verify parity per tenant:

```bash
PF_DB_DSN=... python scripts/dev/backlog_db_parity.py --tenant product_forge
```


## Activate

`PF_BACKLOG_DB` defaults to `on` for PF-SB/PF-GP. Keep the shared service and DB available; set it to `off` only for explicit legacy/offline tooling (repo precheck/docs projections) or tests. Set it for every process that reads/writes backlog:

```text
PF_BACKLOG_DB=on
PF_EDP_API_URL=http://127.0.0.1:8030
PF_EDP_TOKEN=<token accepted by edpsvc>
```

`edpsvc` must be running with the PostgreSQL DSN and migrations applied.

## Verify

1. `GET /backlog?tenant=product_forge&limit=...` and a generated product's `/backlog` both return
   their backfilled items.
2. `POST /backlog/ids:reserve` returns a new global block.
3. Repeating the same reservation returns the same block.
4. Two different reservations, including PF-SB and PF-GP, are disjoint.
5. Creating an item writes only to PostgreSQL; no new authoritative `items/*.json` is created.
6. `PF_BACKLOG_DB=on` with the DB unavailable fails closed; no Git/local fallback.

1. Take a verified backup/snapshot of `backlog_items`, `backlog_id_allocations`, `backlog_id_reservations`, and `traceability` before any schema change.
2. Set `PF_BACKLOG_DB=off` and restart affected processes.
3. Verify file-mode reads/writes and ID allocation still work.
4. Do not delete the DB tables; they are the basis for a later retry.
5. Migration 0021 down refuses to run while legacy cross-tenant duplicate IDs exist; restore from the verified backup instead of forcing the down migration.
6. Do not re-enable Git ID allocation for new items without an explicit decision.

## Generated products

PF-GP uses the same DB/ID authority. Generated-product source files may live outside this repository; when they are absent, parity is verified only for tenants with local file sources. DB-only legacy tenants are preserved and are not deleted by backfill/parity.

## Agent workflow boundary

The DB cutover changes **storage/writer authority only**. PF-SB and PF-GP agent workflows, stage
definitions, prompts, and gates remain their existing workflows; they simply share one backlog SSOT.

## Rollback / reconcile

Export/preflight use `PF_DB_DSN`; use the runtime role where RLS/audit coverage is required. Before setting `PF_BACKLOG_DB=off` after DB-mode writes: stop/quiesce backlog writers, export DB authority to file projections, run parity, then flip the flag and restart writers. Writes between export and flip are otherwise lost.

```bash
PF_DB_DSN="$PF_RUNTIME_DSN" python scripts/dev/backlog_db_export.py --tenant product_forge --dry-run
PF_DB_DSN="$PF_RUNTIME_DSN" python scripts/dev/backlog_db_export.py --tenant product_forge --overwrite --prune --confirm-prune
```

Then run parity and only afterwards switch to file mode. Never drop backlog tables as part of rollback.

```bash
PF_DB_DSN="$PF_RUNTIME_DSN" PF_BACKUP_CONFIRMED=1 python scripts/dev/backlog_migration_preflight.py
```

## Deploy order and 0021 remediation

1. Stop old backlog writers before applying 0021; an old binary uses `ON CONFLICT (id)`, which is invalid under the new composite key.
2. Confirm backup, run the preflight, apply 0021, then 0022 (traceability index), then 0023 (global-ID guard), then start the new binary.
3. If preflight reports NULL/mismatched traceability tenant rows, repair `traceability.tenant_id` from the owning item, then rerun. Do not skip the check.
4. Keep the backup until the fleet is fully on the new binary and parity is green.

`dual` and `shadow` are migration-only modes; unknown values raise `BACKLOG_DB_MODE_INVALID`. `BACKLOG_DB_UNAVAILABLE` is logged with tenant and the Go service exports `edp_backlog_authority_*` metrics.

## Generated-product tenants

`PF_BACKLOG_DB_SCOPES` defaults to `product_forge` and `ProductForge-Dashboard`. Every additional PF-GP tenant must be added explicitly after parity is proven. An unlisted scope raises `BACKLOG_DB_SCOPE_UNLISTED` in on/dual/shadow mode; it never falls back to files. Use explicit `PF_BACKLOG_DB=off` only for legacy file mode.

## Backfill sequencing

Backfill and parity run with `PF_BACKLOG_DB=on` in a maintenance/integration window because tooling is a DB writer. `dual`/`shadow` are application migration modes, not backfill modes. The operational sequence is: backup -> migrate -> backfill/parity with on -> enable app traffic; rollback uses export --prune --confirm-prune -> parity -> off.
