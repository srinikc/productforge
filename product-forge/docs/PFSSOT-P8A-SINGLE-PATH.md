# PFSSOT-P8A — Single Submission Path + Optional/Removable Worker Layer

**Item:** BI-PF-0370 (epic BI-PF-0360) · fixes IS-PF-0035 · gap-close of doc §43(c)

## 1. One submission path (JobManager)

Every job submission goes `→ run_entry.enqueue → job_manager.enqueue`; only the sanctioned worker/CLI entry
runs `PipelineExecutor`. Fixed `IS-PF-0035`: `core/enhance.py` no longer calls `execute_pipeline()` directly —
it **submits via `core.run_entry`** so the queue/worker runs it. Guard `scripts/dev/single_path_check.py`
(baseline-aware) fails on any NEW direct `execute_pipeline()` outside the allowlist
(`core/pipeline_executor.py`, `scripts/run_pipeline.py`, `scripts/`).

## 2. Worker layer is optional + removable (runtime switch)

`WORKER_INTEGRATION_ENABLED` (central flag registry, default **on**). When `0`:
- worker endpoints (`/engineering/workers*`, `/work*`, `/adapters`, `/schedule/claim|lease|recover`) return **503 DEPENDENCY_UNAVAILABLE**;
- `work_pull.pull/start` refuse with `worker integration disabled`;
- **PF runs unchanged** — core imports **none** of the worker layer (asserted by the gate + test).

This is the "ship it but turn it off for a customer/deployment" switch. The "don't ship it at all" path
(build-time exclude) is a separate item: **BI-PF-0383**.

## 3. Seams / removability

The worker layer (`worker_registry.py`, `worker_adapters.py`, `work_pull.py` + their routes/gates) is
additive; nothing in `pipeline_executor`/`orchestrator`/agents imports it. `job_manager` gained lease
columns + `claim_next` (shared seam — left dormant if the layer is removed, never ripped out).

## Verification

```
python scripts/dev/single_path_check.py     # OK (one submission path; worker layer optional + removable)
python -m pytest .../test_single_path_and_pluggable.py   # 4 passed
python scripts/dev/precheck.py              # PASS
```
