# EDP-22 Operator Runbook

- Benchmarks: run only with `PF_BENCH_DSN` using `pf_readonly`; enable scheduling explicitly.
- Baselines: store under `engineering/benchmarks/BI-PF-1314/<store>/<env>/<git-sha>.json`.
- EXPLAIN: default sampling `0`; production cap `0.05`; read-only rollback; allowlisted queries only.
- Degradation: owner, reason, `expires_at`, max 15m; renewals alert; expired switch fails closed.
- SLO rules/dashboard: generate from `config/edp-slo.json` after measured baselines; validate drift.
