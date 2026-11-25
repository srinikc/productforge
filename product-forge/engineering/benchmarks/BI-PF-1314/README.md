# EDP-22 benchmark evidence

Baselines are versioned JSON artifacts. Store per environment locally under:

`engineering/benchmarks/BI-PF-1314/<store>/<env>/<git-sha>.json`

Each artifact records the harness version, generation time, DSN, ops, and p50/p95/p99 per scenario.
Prometheus text output is generated alongside it. Do not commit secrets or tenant data.
