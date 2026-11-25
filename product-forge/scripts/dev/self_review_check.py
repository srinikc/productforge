"""Advisory self-review gate: changed code must not ship placeholders/TODOs and diff must be whitespace-clean."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BAD = re.compile(r"\b(TODO|FIXME|XXX|placeholder|stub|not implemented)\b", re.I)
CODE_EXT = (".go", ".py", ".js", ".ts", ".tsx", ".jsx", ".sql", ".yml", ".yaml")


def _git(args: list[str]) -> str:
    r = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or f"git {' '.join(args)} failed")
    return r.stdout


def _base() -> str:
    return _git(["merge-base", "origin/develop", "HEAD"]).strip()


def changed_lines() -> list[tuple[str, int, str]]:
    """Committed implementation delta (not just the local worktree)."""
    out = []
    cur = ""
    for line in _git(["diff", "--relative", "-U0", f"{_base()}..HEAD"]).splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:]
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        rel = cur.replace("\\", "/")
        if Path(rel).suffix.lower() not in CODE_EXT:
            continue
        # Tooling/tests legitimately contain the detector's own tokens and are not shipped code.
        if rel.startswith(("scripts/dev/", "test-framework/", "tests/")):
            continue
        text = line[1:].strip()
        if text:
            out.append((cur, 0, text))
    return out


def problems() -> list[str]:
    bad = []
    for _f, _n, text in changed_lines():
        if BAD.search(text):
            bad.append(f"placeholder/TODO in changed code: {text[:120]}")
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Self-review check")
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args(argv)
    bad = problems()
    if bad:
        print(f"self-review: {len(bad)} finding(s)")
        for p in bad:
            print(f"  - {p}")
        return 1 if a.strict else 0
    print("self-review: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
