"""Install repo git hooks (author-time guards) — idempotent.

Currently installs a ``pre-commit`` hook that runs the CHEAP, changed-file guards so a
store-contract/lint violation is caught before it ever reaches the merge-time precheck:

  - scripts/dev/store_check.py   (new data-file literals must be registered)
  - scripts/dev/lint_check.py --strict  (ruff on changed files)

The hook never blocks on the full precheck (that stays the merge gate); it only fails on the
changed-file guards. Safe to re-run. Run from product-forge/: ``python scripts/dev/install_hooks.py``.
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
python "$PF/scripts/dev/store_check.py" || { echo "pre-commit: store-contract failed (register the data file in config/store-registry.json)"; exit 1; }
python "$PF/scripts/dev/lint_check.py" --strict || { echo "pre-commit: lint failed on changed files (fix or run: python -m ruff check --fix <files>)"; exit 1; }
exit 0
"""


def main() -> int:
    hooks = os.path.join(_REPO, ".git", "hooks")
    os.makedirs(hooks, exist_ok=True)
    path = os.path.join(hooks, "pre-commit")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(_HOOK)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    print(f"installed pre-commit hook -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
