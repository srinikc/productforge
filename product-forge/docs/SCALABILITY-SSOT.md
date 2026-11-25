# Scalability SSOT - Capacity Tiers, Performance Goals, and Scale-Out Order

Status: binding planning SSOT for PF platform capacity.
Scope: PF-SB platform data plane and shared backlog/storage/observability. PF-GP products declare their own runtime targets.
Related: `docs/Product_Forge_Enterprise_Performance_Security_DB_Storage_Roadmap.md`, `docs/EDP-22-BENCHMARKS-SLOS.md`, `docs/EDP-24-EVIDENCE-GATE.md`, `docs/BACKLOG-DB-SSOT.md`.

## 0. Statement of scale and performance goals

Product Forge is planned and operated in explicit capacity tiers. A tier is supported only after staging load, latency, isolation, and restore tests at that workload pass. Local benchmarks are not capacity proof.

PF-SB scale is measured by factory throughput and platform data-plane capacity. PF-GP scale is measured by each generated product's own users, traffic, data, availability, and recovery targets.

The system must scale **out** when measured capacity requires it and scale **in** when the workload no longer justifies the cost. Tier changes require evidence, not preference.

## 1. Workload units

- tenant: customer organisation
- user: member/seat
- project: portfolio project or generated product
- active run: concurrent pipeline execution
- backlog item: active work item
- audit row: retained audit event
- object: artifact/evidence bytes
- API RPS: control/data-plane requests
- concurrent worker/run: parallel execution capacity

## 2. Capacity tiers (planning targets, not current claims)

| Tier | Tenants | Users | Projects | Concurrent runs | Active backlog items | Runs/day | Audit rows retained | Object storage | API RPS | Isolation |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| T0 Local | 1 | 10 | 10 | 1 | 10k | 100 | 1M | 10 GB | 5 | local |
| T1 Team | 10 | 100 | 1k | 10 | 1M | 1k | 10M | 100 GB | 25 | shared DB |
| T2 Business | 100 | 2k | 10k | 100 | 10M | 10k | 100M | 1 TB | 100 | shared DB + quotas |
| T3 Enterprise | 1k | 20k | 100k | 1k | 100M | 100k | 1B | 10 TB | 500 | shared + dedicated options |
| T4 Dedicated cell | per cell | per cell | per cell | per cell | per cell | per cell | per cell | per cell | dedicated DB/cell |

T4 is per cell, not one global deployment. Cell size is set by measured DB and operational limits; a starting cell envelope is 10k users, 50k projects, 5k concurrent runs, and 50 TB.

## 3. PF-SB performance goals

| Metric | T1 | T2 | T3 | T4 |
|---|---:|---:|---:|---:|
| Control-plane API p95 | 150 ms | 100 ms | 150 ms | 100 ms |
| Control-plane API p99 | 500 ms | 300 ms | 500 ms | 300 ms |
| DB read p95 | 50 ms | 50 ms | 75 ms | 50 ms |
| DB write p95 | 100 ms | 75 ms | 100 ms | 75 ms |
| Job/queue claim p95 | 200 ms | 100 ms | 100 ms | 100 ms |
| Error rate | <1% | <0.5% | <0.5% | <0.1% |
| Availability | 99.5% | 99.9% | 99.9% | 99.95% |
| RPO | 1h | 15m | 5m | 1m |
| RTO | 8h | 4h | 1h | 30m |
| PF-SB items/day | 20 | 50 | 250 | 1k |
| Concurrent workers | 5 | 10 | 50 | 200 |
| Precheck fast p95 | 5m | 5m | 3m | 3m |

A tier claim must publish measured p50/p95/p99, error rate, saturation, RPO/RTO evidence, and the exact workload shape used.

## 4. PF-GP generated-product goals

PF-GP does not inherit PF-SB numbers. Each generated product declares its own API latency, UI performance, throughput, availability, data volume, RPO/RTO, accessibility, security, region/residency, and cost targets in its design/architecture.

Default generated-product template (override allowed):
- API p95 < 500 ms; p99 < 1.5 s
- availability 99.9%; error rate < 0.5%
- RPO 15m; RTO 4h
- WCAG AA
- load test before launch

These are product defaults, not PF platform guarantees.

## 5. Required platform capability by tier

| Tier | Required capability |
|---|---|
| T1 | shared PostgreSQL, object store, RLS, quotas, backups, baseline SLOs |
| T2 | pool budgeting, SLO alerts, degradation, restore drills, per-tenant isolation proof |
| T3 | read replicas, hot-table partitioning, distributed quota coordination, per-tenant auth |
| T4 | dedicated DB/cell, region cells, cross-region DR, per-cell observability |

T3/T4 are where EDP-24 starts. T3/T4 implementation is trigger-gated and must not be built speculatively.

## 6. Scale-out / scale-in triggers

A tier upgrade or scale-out requires at least one measured trigger sustained over the stated window:

- DB p95 > 50 ms or p99 > 200 ms for 7 days at production load
- hot table > 100M rows or > 500 GB
- connection-pool saturation > 80% for 1 hour on 3 days in a week
- queue latency p95 > 1s for 24 hours
- object-store metadata latency p95 > 200 ms for 24 hours
- contracted tenant SLA requires dedicated DB/cell isolation
- residency/legal requirement requires another region cell
- capacity forecast exceeds 70% of the current tier's DB/storage envelope within 90 days

Scale-in requires:
- measured load below 50% of the lower tier's envelope for 30 days
- no active contracted isolation/residency requirement
- restore and rollback evidence for the target tier
- HIL capacity decision

## 7. Execution order

1. **T1 readiness now**
   - staging workload at T1 shape
   - guardrail verification (RPM, concurrency, pool, timeout, object limits)
   - SLO dashboards/alerts
   - backup/restore drill
   - capacity report and HIL acceptance

2. **T2 readiness now**
   - production-like T2 load and data volume
   - p95/p99, error rate, pool saturation, lock waits, queue latency
   - per-tenant isolation test
   - RPO/RTO drill
   - cost envelope
   - HIL acceptance

3. **T3 decision gate**
   - use T2 evidence against triggers
   - if no trigger: do not implement EDP-24; keep monitoring
   - if triggered: run EDP-24 design/Gate 1, then replicas/partitioning/distributed quotas
   - T3 acceptance requires measured evidence and restore proof

4. **T4 decision gate**
   - only after T3 is stable and contracted isolation/residency requires it
   - dedicated cell/region design, migration dry-run/cutover/rollback
   - T4 acceptance requires cell-level isolation, region restore, and residency evidence

5. **Scale-in review**
   - quarterly or after major traffic change
   - downshift only with measured headroom and rollback plan

## 7.1 Dependency and execution edges

- `BI-PF-1527` (T1) produces the first capacity report.
- `BI-PF-1528` (T2) is blocked by T1 and produces the business-scale evidence.
- `BI-PF-1529` (T3 decision gate) is blocked by T2 only.
- T3 decides whether to activate `BI-PF-1317` (EDP-24). EDP-24 is **not** a prerequisite for T3.
- `BI-PF-1530` (T4 decision gate) is blocked by T3.
- T1/T2 do not require EDP-24. EDP-24 remains trigger-gated until T3 evidence says otherwise.

## 8. PF-SB T1/T2 immediate plan

1. Define the staging workload fixture: tenants, users, projects, runs, backlog, audit, objects.
2. Extend the EDP-22 benchmark matrix to include API/gate/queue/object paths, not only store operations.
3. Run T1 and T2 shapes; record p50/p95/p99, throughput, errors, saturation, pool waits, queue depth, RPO/RTO.
4. Compare to this SSOT; publish a capacity report.
5. File defects or child items for every missed target.
6. HIL accepts or rejects the tier claim.

Do not claim T1/T2 supported until steps 1-6 complete.

## 9. Backlog tracking

| Item | Purpose |
|---|---|
| `BI-PF-1526` | EPIC: Scalability & Capacity Tiers (T1-T4) |
| `BI-PF-1527` | T1 team-scale capacity validation |
| `BI-PF-1528` | T2 business-scale capacity validation |
| `BI-PF-1529` | T3 enterprise scale-out decision gate |
| `BI-PF-1530` | T4 dedicated cell/region decision gate |
| `BI-PF-1317` | EDP-24 scale-out implementation (trigger-gated) |
| `BI-PF-1314` | EDP-22 benchmarks/SLOs/observability (completed) |
| `BI-PF-1315` | EDP-23 backup/PITR/restore (completed) |
| `BI-PF-1310` | EDP-18 migration tooling (completed) |

## 10. Change control

- This SSOT is the source of truth for PF platform capacity tiers.
- Changing a tier number, SLO, trigger, or isolation requirement requires a backlog item and HIL approval.
- Per-product PF-GP targets live in the generated product's design, not here.
- Any tier claim without measured evidence is invalid.
