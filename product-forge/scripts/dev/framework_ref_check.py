"""Fail if shipped code adds OpenCode runtime dependencies or legacy dashboard references."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BAD = re.compile(r"(?i)(?<![a-z0-9_])(opencode|\.opencode|dashboard)(?![a-z0-9_])")
ROOTS = ("core/", "api/", "adapters/", "go/")


def _rel(path: str) -> str:
    p = str(path or "").replace("\\", "/")
    return p[len("product-forge/"):] if p.startswith("product-forge/") else p


def _git(args: list[str]) -> str:
    r = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or f"git {' '.join(args)} failed")
    return r.stdout


def problems() -> list[str]:
    bad = []
    cur = ""
    base = _git(["merge-base", "origin/develop", "HEAD"]).strip()
    for line in _git(["diff", "--relative", "-U0", f"{base}..HEAD"]).splitlines():
        if line.startswith("+++ b/"):
            cur = _rel(line[6:])
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        if not any(cur.startswith(r) for r in ROOTS):
            continue
        if BAD.search(line[1:]):
            bad.append(f"{cur}: {line[1:].strip()[:140]}")
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Framework reference check")
    a = ap.parse_args(argv)
    bad = problems()
    if bad:
        print(f"framework-ref: FAIL ({len(bad)})")
        for p in bad:
            print(f"  - {p}")
        return 1
    print("framework-ref: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

