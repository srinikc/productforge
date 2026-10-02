"""Lint gate (ruff) scoped to CHANGED files.

Part of the Definition of Done: review -> lint -> e2e -> merge. Runs ruff on the Python files changed on this
branch (vs the merge-base with the integration branch) plus any uncommitted changes, skipping the legacy/frozen
trees. Skips cleanly if ruff is not installed.

Default is ADVISORY (prints findings, exits 0) because the legacy tree predates lint; pass ``--strict`` to fail
on any finding in the changed files. Flip precheck to --strict once the changed-file debt is cleared.

Usage:
  python scripts/dev/lint_check.py            # advisory
  python scripts/dev/lint_check.py --strict   # fail on findings
"""
import argparse
import os
import subprocess
import sys

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_EXCLUDE = ("dashboard/", "archive/", "vendor/", "node_modules/", "products/", ".opencode/")
_INTEGRATION = "develop"
# git toplevel (may be the repo root ABOVE the product dir); git paths are relative to it.
_REPO_ROOT = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                            cwd=_ROOT, capture_output=True, text=True).stdout.strip() or _ROOT


def _git(*args):
    r = subprocess.run(["git", *args], cwd=_ROOT, capture_output=True, text=True)
    return (r.stdout or "").strip()


def _changed_py():
    files = set()
    base = _git("merge-base", _INTEGRATION, "HEAD")
    if base:
        for ln in _git("diff", "--name-only", f"{base}", "HEAD").splitlines():
            files.add(ln.strip())
    for ln in _git("diff", "--name-only", "HEAD").splitlines():
        files.add(ln.strip())
    out = []
    for f in files:
        f = f.replace("\\", "/")
        if not f.endswith(".py") or any(x in f for x in _EXCLUDE):
            continue
        # git lists paths relative to the repo root; ruff runs in _ROOT (the product dir).
        # Keep only files under _ROOT and make them relative to it.
        rel = os.path.relpath(os.path.join(_REPO_ROOT, f), _ROOT).replace("\\", "/")
        if rel.startswith(".."):  # outside the product tree
            continue
        out.append(rel)
    return sorted(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Lint changed files (ruff)")
    ap.add_argument("--strict", action="store_true", help="fail on any finding (default: advisory)")
    a = ap.parse_args(argv)

    try:
        import ruff  # noqa: F401
        have_ruff = True
    except Exception:
        have_ruff = subprocess.run([sys.executable, "-m", "ruff", "--version"],
                                   capture_output=True, text=True).returncode == 0
    if not have_ruff:
        print("lint: SKIP (ruff not installed)")
        return 0

    files = _changed_py()
    if not files:
        print("lint: OK (no changed Python files)")
        return 0
    r = subprocess.run([sys.executable, "-m", "ruff", "check", *files],
                       cwd=_ROOT, capture_output=True, text=True)
    if r.returncode == 0:
        print(f"lint: OK ({len(files)} changed file(s) clean)")
        return 0
    out = (r.stdout or "") + (r.stderr or "")
    count = sum(1 for ln in out.splitlines() if ln.strip() and ":" in ln and not ln.startswith(" "))
    print(f"lint: {count or '?'} finding(s) in {len(files)} changed file(s)")
    for ln in out.splitlines()[-12:]:
        print("   ", ln)
    if a.strict:
        print("lint: FAIL (--strict)")
        return 1
    print("lint: advisory (use --strict to fail) - debt on changed files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
