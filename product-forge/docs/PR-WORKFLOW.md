# PR / Branch Workflow (BI-0205)

Every change follows **branch → pre-check gates → review → merge**. Never commit to `develop`/`main`.

## 1. Branch
```
git checkout -b feature/<scope>       # one concern per branch
```

## 2. Pre-check gates (local, must pass)
```
# from product-forge/
python scripts/dev/precheck.py              # fast (default): per-phase
python scripts/dev/precheck.py --full       # merge/CI: + validation/lifecycle + full suite
python scripts/dev/precheck.py --release    # pre-release: + periodic full-tree sweeps
```
Three tiers (BI-PF-0384/BI-PF-0385) keep everyday work fast:
- **fast** (~20s) - compile, `wired_audit --fast` (core checks; advisory sub-audits skipped), store/lint,
  **diff-scoped secret scan**, workflow matrix, `pf-surface`, intent-trace, docs-fresh, changed-scoped tests.
- **`--full`** (merge/CI) - all area gates + validation/lifecycle + the **full test suite**. The secret scan
  stays **diff-scoped** (changed vs `develop`): a merge never walks the whole tree.
- **`--release`** (a few times before a release) - `--full` plus the **full-tree** secret sweep
  (`secret_scan.py --all`) and any other periodic audit.

`secret_scan.py` is **diff-scoped by default**; pass `--all` for the full-tree sweep (release/periodic).

The authoritative CI mirror is `.github/workflows/structure.yml` (also checks fresh generated
docs). Keep the two in sync.

## 3. Review
- Self-review the diff; keep it scoped to the branch's concern.
- Restore generated churn before committing: `git restore product-forge/dashboard/docs`.
- Commit message: `<Scope> (<BI-id>): <what>` + a body of the why/evidence.

## 4. Merge
```
git checkout develop
git merge --no-ff feature/<scope> -m "merge: <scope> (<BI-id>)"
git push origin develop
```
Record evidence on the backlog item: `python -m core.backlog status <id> completed --note "..."`.

## Rules
- One truth per concern, one writer per file (see `docs/STRUCTURE-CONTRACT.md`).
- Fail closed: unknown ⇒ blocked; never exit 0 on failure.
- Root-cause every defect via `docs/RCCA_productForge.md` (5-Why + a new guard).
