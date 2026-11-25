# EDP-24 Evidence Gate

Decision: **do not implement scale-out yet**.

Evidence from EDP-22 local baseline (`engineering/benchmarks/BI-PF-1314/db/local/baseline.json`):
- p95 latency: 1.5?3.6 ms across artifact/project/run/memory/job/db scenarios
- p99 latency: same order of magnitude
- no measured saturation, replica pressure, or partitioning pressure

EDP-24 remains evidence-gated. Re-open implementation only when one or more triggers is met:
- DB p95 > 50 ms or p99 > 200 ms for 7 days under production load
- hot table > 100M rows or > 500 GB
- documented tenant SLA requiring dedicated DB/cell isolation
- residency requirement requiring an additional region cell

Until then, read replicas, partitioning, dedicated cells, and region migration add operational risk without measured benefit.
