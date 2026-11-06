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

Apply migration `0016_backlog_db_authority` with the normal explicit deploy migration step.

It creates:

- `backlog_id_allocations` with one `global` authority row
- `backlog_id_reservations`
- global seed `1508` (1507 remains quarantined)

## Backfill

```bash
PF_EDP_API_URL=http://127.0.0.1:8030 \
PF_API_TOKEN=... \
python scripts/dev/backlog_db_backfill.py --dry-run

PF_EDP_API_URL=http://127.0.0.1:8030 \
PF_API_TOKEN=... \
python scripts/dev/backlog_db_backfill.py
```

The backfill scans PF-SB and generated-product item files. It is idempotent because
`BacklogStore.Put` upserts by item id.

## Activate

`PF_BACKLOG_DB` defaults to `on` for PF-SB/PF-GP. Keep the shared service and DB available; set it to `off` only for explicit legacy/offline tooling (repo precheck/docs projections) or tests. Set it for every process that reads/writes backlog:

```text
PF_BACKLOG_DB=on
PF_EDP_API_URL=http://127.0.0.1:8030
PF_API_TOKEN=<token accepted by edpsvc>
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

## Rollback

- Set `PF_BACKLOG_DB=off` and restart affected processes.
- Do not delete the DB tables; they are the basis for a later retry.
- Do not re-enable Git ID allocation for new items without an explicit decision.

## Agent workflow boundary

The DB cutover changes **storage/writer authority only**. PF-SB and PF-GP agent workflows, stage
definitions, prompts, and gates remain their existing workflows; they simply share one backlog SSOT.
