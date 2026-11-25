# EDP-22 Operator Runbook

## Benchmarks
- Use a read-only `PF_BENCH_DSN`; do not use an admin/superuser role.
- Run `go run ./cmd/bench -ops N -out <artifact> -sink <metrics.prom> -enforce`.
- Missing DSN is an error unless `-allow-skip` is explicit.
- Baseline freshness: `edp_bench_last_run_unixtime`; alert after 24h.

## EXPLAIN
- Default sample rate is `0`; production maximum is `0.05`.
- Run `python scripts/dev/db_explain_capture.py --query <name> --env production --sample-rate 0.05`.
- Statements are allowlisted, read-only, `statement_timeout=5s`, rolled back, and redacted.
- Store artifacts in an access-controlled path; never paste tenant literals.

## Degradation
- Every switch requires `owner`, `reason`, and `expires_at`.
- Maximum duration is 900 seconds; expired switches fail closed.
- Alert on `edp_store_degraded` and record start/expiry in the audit log.

## SLO assets
- Budgets: `config/edp-slo.json`
- Rules: `ops/prometheus/edp-slo.rules.yml`
- Dashboard: `ops/grafana/edp-slo-dashboard.json`
- Validate offline: `python scripts/dev/validate_edp_slo.py`
