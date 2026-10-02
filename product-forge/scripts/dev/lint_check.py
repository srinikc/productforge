"""Lint gate (ruff) scoped to CHANGED files, baseline-aware.

Part of the Definition of Done: review -> lint -> e2e -> merge. Runs ruff on the Python files changed
on this branch (vs the merge-base with the integration branch) plus any uncommitted changes, skipping the
legacy/frozen trees.

Baseline-aware: `--strict` fails only on findings **introduced** by this change (compare the working-tree
findings against the same files at HEAD). This keeps the legacy whole-file debt from blocking a change
that merely touches a legacy file, while still failing on NEW findings. Default is ADVISORY.

Usage:
  python scripts/dev/lint_check.py            # advisory
  python scripts/dev/lint_check.py --strict   # fail on NEW findings (baseline-aware)
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
        rel = os.path.relpath(os.path.join(_REPO_ROOT, f), _ROOT).replace("\\", "/")
        if rel.startswith(".."):
            continue
        out.append(rel)
    return sorted(out)


def _ruff(files):
    """Return (count, output) for ruff on the given files (empty => 0)."""
    if not files:
        return 0, ""
    r = subprocess.run([sys.executable, "-m", "ruff", "check", *files],
                       cwd=_ROOT, capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    count = sum(1 for ln in out.splitlines() if ln.strip() and ":" in ln and not ln.startswith(" "))
    return count, out


def _baseline_findings(files):
    """Findings on the SAME files at HEAD (repository version), as a set of identifiers."""
    import re
    idents = set()
    pat = re.compile(r"^(?P<f>.+?):(?P<line>\d+):(?P<col>\d+): (?P<code>[A-Z]+\d+)")
    for rel in files:
        head = subprocess.run(["git", "show", f"HEAD:product-forge/{rel}"], cwd=_REPO_ROOT,
                              capture_output=True, text=True).stdout
        if not head:
            continue
        r = subprocess.run([sys.executable, "-m", "ruff", "check", "--stdin-filename", rel, "-"],
                           cwd=_ROOT, input=head, capture_output=True, text=True)
        for ln in ((r.stdout or "") + (r.stderr or "")).splitlines():
            m = pat.match(ln.strip())
            if m:
                idents.add((rel, m.group("code")))
    return idents


def _current_findings_ident(files):
    import re
    idents = set()
    pat = re.compile(r"^(?P<f>.+?):(?P<line>\d+):(?P<col>\d+): (?P<code>[A-Z]+\d+)")
    for rel in files:
        p = os.path.join(_ROOT, rel)
        if not os.path.isfile(p):
            continue
        r = subprocess.run([sys.executable, "-m", "ruff", "check", rel], cwd=_ROOT,
                           capture_output=True, text=True)
        for ln in ((r.stdout or "") + (r.stderr or "")).splitlines():
            m = pat.match(ln.strip())
            if m:
                idents.add((rel, m.group("code")))
    return idents


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Lint changed files (ruff, baseline-aware)")
    ap.add_argument("--strict", action="store_true", help="fail on NEW findings (default: advisory)")
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

    count, out = _ruff(files)
    if count == 0:
        print(f"lint: OK ({len(files)} changed file(s) clean)")
        return 0

    base = _baseline_findings(files)
    cur = _current_findings_ident(files)
    new = sorted(cur - base)
    print(f"lint: {count} finding(s) in {len(files)} changed file(s); "
          f"{len(new)} NEW vs HEAD, {len(cur & base)} pre-existing")
    for ln in out.splitlines()[-12:]:
        print("   ", ln)
    if new:
        print("lint: NEW findings (fix these):")
        for f, code in new[:20]:
            print(f"    {code}  {f}")
    if a.strict and new:
        print("lint: FAIL (--strict: new findings)")
        return 1
    print("lint: advisory (use --strict to fail new findings) - pre-existing debt on changed files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
