# Backlog authority runbook (BI-PF-1509)

**Owner:** platform-oncall
**Service:** `edpsvc` / EDP data plane
**Endpoint:** `GET /admin/backlog/authority?tenant=<tenant>`
**Alert rules:** `ops/prometheus/backlog-authority.rules.yml`
**Prometheus config:** `ops/prometheus/prometheus.yml`

## Signals

- `edp_backlog_authority_startup_ok` - 1 when the latest authority check succeeded, 0 when it failed.
- `edp_backlog_authority_errors_total` - authority failures from endpoint 503s and startup/recheck failures.
- `edp_backlog_authority_success_timestamp_seconds` - last successful authority snapshot.

A single admin probe 503 is not paged. The error-rate page requires the condition to persist for the
10-minute alert window; it is not a one-shot probe alert. The rule file is loaded by
`ops/prometheus/prometheus.yml`. `/ready` intentionally remains a DB-connectivity probe: making it
fail on authority drift would cause restart storms; the startup check, periodic recheck, and the
admin endpoint are the authority-specific signals.

Probe callers must back off after a 503; the endpoint returns `Retry-After: 30`. Do not run a tight
probe loop during a DB outage.

## Triage

TLS/certificate failures are reported as `db_unavailable`; use the error log to distinguish identity/CA issues from endpoint outages: search `backlog authority` lines for `x509`, `certificate`, `tls handshake`, or `pg_hba`.

1. Call the endpoint with the EDP admin token and a known tenant.
2. If 503, check the edpsvc log for `principal=`, `source=`, request correlation id, and `reason_code=`. It is one of:
   - `migration_missing` - schema/0018 counter is absent or unreadable.
   - `row_missing` - the `authority='global'` allocation row is absent.
   - `timeout` - the DB query exceeded `PF_EDP_DB_TIMEOUT` or `statement_timeout`.
   - `db_unavailable` - connection/pool failure.
3. Verify migrations 0016, 0017, 0018, 0019, and 0020 are applied via `/admin/migrations/status`.
   0016/0017 are prerequisites; 0018/0019 are the counter and hardening changes.
4. Verify `SELECT authority, next_id, reservation_count FROM backlog_id_allocations;`.
5. If the counter is missing after 0018, re-run the deploy migration; it is idempotent.
   Reconcile drift explicitly:
   ```sql
   SELECT count(*) FROM backlog_id_reservations;
   SELECT reservation_count FROM backlog_id_allocations WHERE authority='global';
   UPDATE backlog_id_allocations a
   SET reservation_count=(SELECT count(*) FROM backlog_id_reservations)
   WHERE authority='global';
   ```
6. Before rollback, drain and verify no in-flight authority/reserve requests via /admin/limits pool stats. Rollback order: remove/disable the route first, then run migrations 0020, 0019, and 0018 down. Never run the
   down migration while the route is live.
7. The authority snapshot is read in one transaction with a 5-second `statement_timeout`; any observed
   skew is due to a concurrent write after the transaction, not a split read.
8. The tenant item count is admin-only and bounded by the DB timeout; alert on repeated 503s, not a
   single probe.

## Unlisted backlog scopes

Detect via structured `BACKLOG_DB_SCOPE_UNLISTED` logs until cross-process metrics infrastructure exists.
Recovery: add verified scope to `PF_BACKLOG_DB_SCOPES` or set `PF_BACKLOG_DB=off` explicitly; never allow silent file fallback.
