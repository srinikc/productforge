"""Encoding guard (BI-PF-1484): changed source/config files must be valid UTF-8 without BOM.

Shell writes (PowerShell Set-Content) can add a BOM and break Go/module parsers. Prefer the explicit
Write/Edit tools for source, config, tests and docs. This gate catches the symptom before review.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CODE_EXT = {".py", ".go", ".mod", ".sum", ".json", ".toml", ".yaml", ".yml", ".md", ".sh", ".ps1"}
SKIP = ("engineering/reviews/", "engineering/trails/", "products/", "test-framework/tests/fixtures/")


def _git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {(r.stderr or '').strip()}")
    return (r.stdout or "").strip()


def changed(base: str = "") -> list[str]:
    start = base or _git("merge-base", "origin/develop", "HEAD")
    names = set()
    for rng in (f"{start}..HEAD", "HEAD"):
        for line in _git("diff", "--name-only", rng).splitlines():
            names.add(line.strip().replace("\\", "/"))
    for line in _git("ls-files", "--others", "--exclude-standard").splitlines():
        names.add(line.strip().replace("\\", "/"))
    out = []
    for p in sorted(names):
        if not p or any(s in p for s in SKIP):
            continue
        if Path(p).suffix.lower() in CODE_EXT:
            out.append(p)
    return out


def problems(files: list[str]) -> list[str]:
    bad = []
    for rel in files:
        p = ROOT / rel
        if not p.is_file():
            continue
        try:
            raw = p.read_bytes()
        except Exception as e:
            bad.append(f"{rel}: unreadable: {e}")
            continue
        if raw.startswith(b"\xef\xbb\xbf"):
            bad.append(f"{rel}: UTF-8 BOM (use Write/Edit, not PowerShell Set-Content)")
            continue
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError as e:
            bad.append(f"{rel}: not valid UTF-8: {e}")
    return bad


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Encoding guard")
    ap.add_argument("--base", default="")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args(argv)
    try:
        bad = problems(changed(a.base))
    except Exception as e:
        print(f"encoding: FAIL - cannot compute changed files: {e}")
        return 1
    print("encoding: " + ("OK" if not bad else "FAIL"))
    for x in bad:
        print("  - " + x)
    return 0 if a.report or not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
