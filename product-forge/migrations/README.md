# Database migrations (EDP-08 / BI-PF-1300)

Versioned, reviewed schema migrations for Product Forge's **PostgreSQL system of record** (ADR-0006).
The runner lives in `go/migrate` (`productforge/migrate`); it applies these through the provider-neutral
`datastore.RelationalStore` interface (EDP-07), so no provider-specific code is duplicated here.

## Rules

1. **Versioned + ordered.** One file per change: `NNNN_<slug>.sql`. `NNNN` is monotonic and unique.
   Never edit an already-applied file — add a new one.
2. **No auto-migrate on startup.** Migrations run only via the explicit deploy step
   (`migrate.Up`); the application never mutates schema at boot (ADR-0006 §9).
3. **Reviewed + reversible.** Every migration pairs an `Up` and a `Down`. Use expand/contract
   (add → backfill → switch → drop) so a `Down` is always safe.
4. **Separate roles.** The **schema owner** (`pf_owner`) applies migrations; the **runtime**
   role (`pf_runtime`) has DML only (no DDL) and is **not** `BYPASSRLS`. See `0001_roles.sql`.
5. **One truth per concern.** Table ownership follows ADR-0006; do not create a table that
   duplicates an existing owner store.

## Roles (ADR-0006 §5.1)

| Role | Purpose | Key attributes |
|---|---|---|
| `pf_owner` | schema owner; applies migrations | owns objects; may DDL |
| `pf_runtime` | application runtime | DML only; **no** DDL; **not** `BYPASSRLS` (RLS enforced) |
| `pf_readonly` | analytics / read-only | `SELECT` only |
| `pf_backup` | backup/restore | `pg_read_all_data` |
| `pf_admin` | break-glass cross-tenant admin | `BYPASSRLS`; **audited**; usage recorded |

## Applying

```sh
# explicit deploy step (never on app startup)
go run ./go/migrate ...   # or the deploy wrapper; see EDP-18 for the cutover tooling
```

State is tracked in `schema_migrations`; re-running is a no-op for already-applied versions.
