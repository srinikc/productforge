# EDP-22: Benchmarks, SLOs, EXPLAIN capture, quotas, and degradation

## Slices
1. Benchmark CLI + Prometheus SLO sink + baseline/SLO config + alert/dashboard guidance.
2. EXPLAIN(ANALYZE,BUFFERS) sampling capture with production guard.
3. Per-store quota/degradation switches with bounded alerts.
4. Baseline evidence run across DB/object/cache/queue stores.

## Rules
- Benchmark labels are bounded (`group`, `scenario`); no tenant IDs or secrets.
- EXPLAIN ANALYZE is sampling-only in production and defaults off.
- Degradation fails closed with a fixed error; it never returns a zeroed success.
- SLO thresholds are set from measured baselines, not invented targets.
- EDP-24 scale-out remains evidence-gated by EDP-22 baselines.

## Implemented commands

```bash
cd go/edpsvc
PF_BENCH_DSN=postgres://... go run ./cmd/bench   -ops 20 -out ../../engineering/benchmarks/BI-PF-1314/db/local/<git-sha>.json   -sink /tmp/edp-bench.prom -baseline ../../config/edp-slo.json -enforce
```

- Missing DSN fails unless `-allow-skip` is explicit.
- `edp_bench_p50_ms`, `edp_bench_p95_ms`, `edp_bench_p99_ms`, `edp_bench_scenario_errors` use bounded
  `group`/`scenario` labels.
- `edp_bench_last_run_unixtime` is unlabeled freshness.
- SLO budgets live in `config/edp-slo.json`; `-enforce` exits non-zero on violations.

## EXPLAIN capture

```bash
python scripts/dev/db_explain_capture.py --query backlog_items --env production --sample-rate 0.05   --per-minute 30 --out /tmp/explain.txt
```

- Production sample rate is capped at `0.05`; default is `0` (skip).
- Statements are allowlisted, read-only, use `statement_timeout=5s`, and always roll back.
- Output is redacted and should be stored in an access-controlled evidence path.

## Store metrics, degradation, quotas

- `go/edpsvc/internal/observe` emits bounded `edp_store_requests_total`, `edp_store_latency_ms`, and
  `edp_store_degraded` for `db`, `object`, `cache`, `queue`.
- `go/edpsvc/internal/degrade` requires `owner`, `reason`, and `expires_at`; expired switches fail closed.
- `config/edp-degradation.json` is limited to 900 seconds per switch.
- Alert rules: `ops/prometheus/edp-slo.rules.yml`; dashboard: `ops/grafana/edp-slo-dashboard.json`.

## Verification

```bash
cd go/edpsvc && go test ./...
python -m pytest test-framework/tests/test_db_explain_capture.py   test-framework/tests/test_edp_slo_config.py test-framework/tests/test_edp_degrade_config.py -q
```
