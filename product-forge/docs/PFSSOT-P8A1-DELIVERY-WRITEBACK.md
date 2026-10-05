# PFSSOT-P8A.1 — Auto Delivery + Evidence Write-Back on Completion

**Item:** BI-PF-0381 (epic BI-PF-0360) · extends `core/close_loop.py` (no new store)

When a run is **verified**, closing its backlog item now also **auto-writes provenance** — previously
`backlog.set_delivery` had **zero callers** (the DFoD step was done by hand).

## What is written

On `close_loop.verify_and_close(...)` → verified → `_finalize(project_dir, scope, project, item_id, run_id)`:

- `links.delivery` (via `backlog.set_delivery`, single writer):
  `{branch, merge_sha, commits[], pr, pr_url, at, note}`
- `links.evidence` (run-bound):
  `{run_id, commit_sha, pr, checks[], at}` — PR/checks from `github.build_evidence`

Branch/commits/merge SHA come from git in the project dir; PR + checks are aggregated read-only by
`core.github.build_evidence`. **One writer per store; no new store.**

## Applies to both completion paths

- **Regular (pipeline/run) path:** `job_manager.finish` → `close_loop.verify_and_close` (this change).
- **Worker path:** the same finalize runs when the item is closed after verification.

## Fail-closed

Only a **verified** run writes delivery. A failed verification marks the item `blocked` (existing behavior);
no provenance is fabricated. `github.build_evidence`/git failures degrade to empty fields — never a false merge.

## Verification

```
python -m pytest .../test_delivery_writeback.py   # 2 passed (delivery + evidence written)
python scripts/dev/precheck.py                     # PASS
```
