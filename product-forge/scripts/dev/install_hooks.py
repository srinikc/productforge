"""Install repo git hooks (author-time guards) — idempotent.

Currently installs a ``pre-commit`` hook that (0) folds ``origin/develop`` into the branch first (BI-PF-1318
per-worker sync; merge, never rebase/reset) and then runs the CHEAP, changed-file guards so a
store-contract/lint/branch violation is caught before it ever reaches the merge-time precheck:

  - scripts/dev/sync_develop.py   (stay close to develop; merge, never rebase - BI-PF-1318)
  - scripts/dev/branch_guard.py   (never commit directly on develop/main - BI-PF-0430)
  - scripts/dev/store_check.py   (new data-file literals must be registered)
  - scripts/dev/lint_check.py --strict  (ruff on changed files)

The hook never blocks on the full precheck (that stays the merge gate); it only fails on the
changed-file guards. Safe to re-run. Run from product-forge/: ``python scripts/dev/install_hooks.py``.

Also installs a ``pre-push`` hook that (1) folds ``origin/develop`` into the branch first (BI-PF-1290 per-worker
sync; merge, never rebase/reset), (2) runs the cheap backlog **id-audit** (BI-PF-0463), and (3) enforces the
test gate at the push boundary (BI-PF-1340): a shipped/sensitive change must add/update a test and the
changed/new tests must PASS before the push is allowed (skip with ``PF_SKIP_TEST_GATE=1``).
"""
import os
import stat
import subprocess

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

_REPO = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                       cwd=_ROOT, capture_output=True, text=True).stdout.strip() or _ROOT

_HOOK = """#!/bin/sh
# Product Forge author-time guard (installed by scripts/dev/install_hooks.py).
# Cheap changed-file checks only; the merge-time gate is scripts/dev/precheck.py.
set -e
PF="product-forge"
[ -d "$PF/scripts/dev" ] || exit 0
# BI-PF-1318: fold origin/develop into the branch before committing (per-worker sync; merge, never rebase).
# If it merged, it exits 1 -> re-run `git commit` (the merge is its own clean commit). Skips when up to date.
python "$PF/scripts/dev/sync_develop.py" --pre-commit || exit $?
# BI-PF-1249 + BI-PF-1374: keep DERIVED docs fresh whenever the backlog changes, so they ride the SAME commit.
# A bookkeeping-only commit then runs precheck's minimal tier (docs-fresh + compile) - never split the doc
# regeneration into its own PR and never use --no-verify.
if git diff --cached --name-only --diff-filter=ACM | grep -q '^product-forge/data/backlog/'; then
( cd "$PF" && python scripts/dev/gen_docs_index.py ) >/dev/null 2>&1 || true
( cd "$PF" && python scripts/dev/gen_backlog_summary.py ) >/dev/null 2>&1 || true
git add "$PF/docs/BACKLOG-SUMMARY.md" "$PF/docs/documentation-index.html" 2>/dev/null || true
fi
python "$PF/scripts/dev/branch_guard.py" || { echo "pre-commit: direct commit on develop/main is forbidden - create a feature branch (git checkout -b feature/<name>)"; exit 1; }
python "$PF/scripts/dev/store_check.py" || { echo "pre-commit: store-contract failed (register the data file in config/store-registry.json)"; exit 1; }
python "$PF/scripts/dev/dependency_catalog_check.py" || { echo "pre-commit: a new dependency has no tool-catalog entry (config/tool-catalog.json)"; exit 1; }
CHANGED_PY=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\\.py$' || true)
if [ -n "$CHANGED_PY" ]; then
python "$PF/scripts/dev/pycompat_check.py" $CHANGED_PY || { echo "pre-commit: Python 3.11-incompatible f-string (backslash inside {...}) - CI runs 3.11"; exit 1; }
fi
python "$PF/scripts/dev/lint_check.py" --strict || { echo "pre-commit: lint failed on changed files (fix or run: python -m ruff check --fix <files>)"; exit 1; }
exit 0
"""

_PREPUSH = """#!/bin/sh
# Product Forge pre-push guard (installed by scripts/dev/install_hooks.py).
# 1) BI-PF-1290: fold origin/develop into the branch first (per-worker sync; merge, never rebase/reset) so a
#    cross-session push stays small. If it merged, it exits 1 -> re-run `git push` to include the merge.
# 2) Belt-and-braces: fail the push on a duplicate backlog id (BI-PF-0463; the merge-time gate is precheck).
PF="product-forge"
[ -d "$PF/scripts/dev" ] || exit 0
python "$PF/scripts/dev/sync_develop.py" --pre-push || exit $?
python "$PF/scripts/dev/backlog_id_audit.py" || { echo "pre-push: duplicate backlog id(s) - renumber before pushing"; exit 1; }
# BI-PF-1340: a shipped/sensitive change MUST add/update a test, and the changed/new tests MUST pass BEFORE push
# (the same gate CI enforces at merge - here it is enforced at the push boundary). Skip with PF_SKIP_TEST_GATE=1.
if [ "$PF_SKIP_TEST_GATE" != "1" ]; then
python "$PF/scripts/dev/changed_tests_check.py" || { echo "pre-push: a shipped/sensitive change must add/update a test (or PF_ALLOW_NO_TEST=1 with a reason)"; exit 1; }
( cd "$PF" && python scripts/dev/precheck.py --tests-changed ) || { echo "pre-push: the changed/new tests must pass before pushing"; exit 1; }
fi
exit 0
"""


def _hooks_dir() -> str:
    """Resolve the git hooks dir (worktree-aware: `.git` is a FILE in a worktree, so ask git)."""
    r = subprocess.run(["git", "rev-parse", "--git-path", "hooks"],
                       cwd=_REPO, capture_output=True, text=True)
    p = (r.stdout or "").strip() or os.path.join(_REPO, ".git", "hooks")
    if not os.path.isabs(p):
        p = os.path.join(_REPO, p)
    return os.path.normpath(p)


def _install(name: str, body: str) -> str:
    hooks = _hooks_dir()
    os.makedirs(hooks, exist_ok=True)
    path = os.path.join(hooks, name)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return path


def main() -> int:
    print(f"installed pre-commit hook -> {_install('pre-commit', _HOOK)}")
    print(f"installed pre-push hook -> {_install('pre-push', _PREPUSH)}")
    # BI-PF-1176 / BI-PF-1290: register the pf-derived merge driver (regenerates the derived backlog indexes/docs
    # and max-merges counters from the shared stores)
    drv = os.path.join(_REPO, "product-forge", "scripts", "dev", "pf_merge_driver.py").replace("\\", "/")
    if os.path.isfile(drv):
        for k, v in (("merge.pf-derived.name", "PF derived backlog artifact (regenerate/max-merge)"),
                     ("merge.pf-derived.driver", f'python "{drv}" %O %A %B %P'),
                     ("merge.pf-item.name", "PF backlog work item (newest version wins)"),
                     ("merge.pf-item.driver", f'python "{drv}" %O %A %B %P')):
            subprocess.run(["git", "config", k, v], cwd=_REPO, capture_output=True, text=True)
        print("registered merge drivers: merge.pf-derived.driver, merge.pf-item.driver")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
