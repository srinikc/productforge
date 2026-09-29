# PR / Branch Workflow (BI-0205)

Every change follows **branch → pre-check gates → review → merge**. Never commit to `develop`/`main`.

## 1. Branch
```
git checkout -b feature/<scope>       # one concern per branch
```

## 2. Pre-check gates (local, must pass)
```
# from product-forge/
python scripts/dev/precheck.py
```
Runs the same gates as CI:
1. `python -m compileall -q core scripts dashboard` (syntax)
2. `python scripts/dev/wired_audit.py` (naming, store registry, wiring, destructive)
3. `python scripts/dev/workflow_matrix_check.py` (stage/agent matrix)
4. `python scripts/dev/e2e_backlog_check.py` (backlog chain)
5. `python scripts/dev/secret_scan.py` (**no hard-coded secrets**)
6. `python -m pytest test-framework/tests/pipeline -q -o addopts=""`

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
