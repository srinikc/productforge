"""Install repo git hooks (author-time guards) — idempotent.

Currently installs a ``pre-commit`` hook that runs the CHEAP, changed-file guards so a
store-contract/lint/branch violation is caught before it ever reaches the merge-time precheck:

  - scripts/dev/branch_guard.py   (never commit directly on develop/main - BI-PF-0430)
  - scripts/dev/store_check.py   (new data-file literals must be registered)
  - scripts/dev/lint_check.py --strict  (ruff on changed files)

The hook never blocks on the full precheck (that stays the merge gate); it only fails on the
changed-file guards. Safe to re-run. Run from product-forge/: ``python scripts/dev/install_hooks.py``.

Also installs a ``pre-push`` hook that runs the cheap backlog **id-audit** (BI-PF-0463) so a duplicate backlog id
is caught at the push boundary too (belt-and-braces on top of precheck/CI).
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
# Belt-and-braces: fail the push on a duplicate backlog id (BI-PF-0463; the merge-time gate is precheck).
PF="product-forge"
[ -d "$PF/scripts/dev" ] || exit 0
python "$PF/scripts/dev/backlog_id_audit.py" || { echo "pre-push: duplicate backlog id(s) - renumber before pushing"; exit 1; }
exit 0
"""


def _install(name: str, body: str) -> str:
    hooks = os.path.join(_REPO, ".git", "hooks")
    os.makedirs(hooks, exist_ok=True)
    path = os.path.join(hooks, name)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return path


def main() -> int:
    print(f"installed pre-commit hook -> {_install('pre-commit', _HOOK)}")
    print(f"installed pre-push hook -> {_install('pre-push', _PREPUSH)}")
    # BI-PF-1176: register the pf-derived merge driver (regenerates backlog indexes from items/)
    drv = os.path.join(_REPO, "product-forge", "scripts", "dev", "pf_merge_driver.py").replace("\\", "/")
    if os.path.isfile(drv):
        for k, v in (("merge.pf-derived.name", "PF derived backlog index (regenerate)"),
                     ("merge.pf-derived.driver", f'python "{drv}" %O %A %B')):
            subprocess.run(["git", "config", k, v], cwd=_REPO, capture_output=True, text=True)
        print("registered merge driver: merge.pf-derived.driver")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
