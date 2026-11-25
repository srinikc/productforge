"""Fail when a candidate adds a path outside the declared PF-SB implementation allowlist.

Usage:
  python scripts/dev/pf_sb_scope_guard.py --baseline %TEMP%/pf-sb-baseline.txt \
      --allow go/edpdata/backlog.go --allow go/edpsvc/main.go
  python scripts/dev/pf_sb_scope_guard.py --baseline %TEMP%/pf-sb-baseline.txt --write-baseline
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def package_path(path: str) -> str:
    """Normalize git paths to the product-forge package root (git root is its parent)."""
    p = path.strip().replace("\\", "/")
    prefix = ROOT.name + "/"
    if p.startswith(prefix):
        return p[len(prefix):]
    if p.startswith("../"):
        return p[3:]
    return p


def _git(args: list[str]) -> str:
    r = subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip() or r.returncode}")
    return r.stdout


def changed_paths(base: str = "") -> set[str]:
    diff = ["git", "diff", "--name-only", f"{base}...HEAD"] if base else ["git", "diff", "--name-only", "HEAD"]
    out = _git(diff)
    untracked = _git(["git", "ls-files", "--others", "--exclude-standard"])
    return {
        package_path(p)
        for p in (out + "\n" + untracked).splitlines()
        if p.strip()
    }


def disallowed_paths(current: set[str], baseline: set[str], allow: set[str]) -> set[str]:
    return {p for p in current - baseline if p not in allow}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="PF-SB scope guard")
    ap.add_argument("--baseline", required=True, help="baseline path list captured before implementation")
    ap.add_argument("--base", default="", help="committed git base (CI); compare base...HEAD")
    ap.add_argument("--allow", action="append", default=[], help="allowed candidate path (repeatable)")
    ap.add_argument("--write-baseline", action="store_true", help="write the current paths and exit")
    a = ap.parse_args(argv)
    baseline_file = Path(a.baseline)
    try:
        current = changed_paths(a.base)
    except RuntimeError as e:
        print(f"pf-sb-scope: FAIL - {e}", file=sys.stderr)
        return 2
    if a.write_baseline:
        baseline_file.parent.mkdir(parents=True, exist_ok=True)
        baseline_file.write_text("\n".join(sorted(current)) + ("\n" if current else ""), encoding="utf-8")
        print(f"pf-sb-scope: baseline written ({len(current)} path(s))")
        return 0
    try:
        baseline = {
            package_path(p)
            for p in baseline_file.read_text(encoding="utf-8").splitlines()
            if p.strip()
        }
    except Exception as e:
        print(f"pf-sb-scope: FAIL - cannot read baseline {baseline_file}: {e}", file=sys.stderr)
        return 2
    allow = {Path(p).as_posix() for p in a.allow}
    bad = disallowed_paths(current, baseline, allow)
    if bad:
        print("pf-sb-scope: FAIL - new paths outside the allowlist:")
        for p in sorted(bad):
            print(f"  - {p}")
        return 1
    print(f"pf-sb-scope: OK ({len(current - baseline)} new allowed path(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
