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
