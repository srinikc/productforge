"""Verify excluded paths contain only generated/evidence content (BI-PF-1485).

Review diffs exclude engineering/**, data/backlog/**, id-blocks, baseline and derived docs. This gate
fails closed if a changed file under those paths does not match its expected schema/header, so code cannot
hide in an excluded path.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXCLUDED = (
    "engineering/reviews/", "engineering/trails/", "engineering/design/",
    "data/backlog/", "config/id-blocks.json", "config/architect-review-baseline.json",
    "docs/BACKLOG-SUMMARY.md", "docs/documentation-index.html",
)


def _git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {(r.stderr or '').strip()}")
    return (r.stdout or "").strip()


def changed(base: str = "") -> list[str]:
    start = base or _git("merge-base", "origin/develop", "HEAD")
    return [x.strip().replace("\\", "/") for x in _git("diff", "--name-only", f"{start}..HEAD").splitlines()
            if x.strip()]


def _json(raw: bytes) -> dict:
    d = json.loads(raw.decode("utf-8-sig"))
    return d if isinstance(d, dict) else {}


def problem(rel: str, raw: bytes) -> str:
    if not any(rel.startswith(e) for e in EXCLUDED):
        return ""
    if rel.startswith("engineering/reviews/"):
        if not rel.endswith(".json") or "-" not in Path(rel).stem:
            return "review evidence must be <item>-<sha>.json"
        d = _json(raw)
        if not all(d.get(k) for k in ("item", "sha", "mode")) or not isinstance(d.get("findings"), dict):
            return "review evidence schema invalid"
        return ""
    if rel.startswith("engineering/trails/"):
        if not rel.endswith(".json"):
            return "trail evidence must be .json"
        d = _json(raw)
        if d.get("schema") != "pf.execution-trail/1" or not isinstance(d.get("events"), list):
            return "trail schema invalid"
        return ""
    if rel.startswith("engineering/design/"):
        if not rel.endswith(".md"):
            return "design evidence must be .md"
        text = raw.decode("utf-8-sig")
        if not text.startswith("# Design Pack"):
            return "design file is not generated (missing header)"
        return ""
    if rel.startswith("data/backlog/"):
        if rel.endswith(".jsonl"):
            for line in raw.decode("utf-8-sig").splitlines():
                if line.strip():
                    json.loads(line)
            return ""
        if rel.endswith(".json"):
            _json(raw)
            return ""
        return "backlog data must be .json/.jsonl"
    if rel == "config/id-blocks.json":
        d = _json(raw)
        return "" if isinstance(d.get("blocks"), dict) else "id-blocks schema invalid"
    if rel == "config/architect-review-baseline.json":
        d = _json(raw)
        return "" if isinstance(d.get("shas"), list) else "baseline schema invalid"
    if rel in ("docs/BACKLOG-SUMMARY.md", "docs/documentation-index.html"):
        return ""
    return "unclassified excluded file"


def problems(files: list[str]) -> list[str]:
    bad = []
    for rel in files:
        p = ROOT / rel
        if not p.is_file():
            continue
        try:
            msg = problem(rel, p.read_bytes())
        except Exception as e:
            msg = f"invalid content: {e}"
        if msg:
            bad.append(f"{rel}: {msg}")
    return bad


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Excluded-path content verifier")
    ap.add_argument("--base", default="")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args(argv)
    try:
        bad = problems(changed(a.base))
    except Exception as e:
        print(f"excluded-content: FAIL - {e}")
        return 0 if a.report else 1
    print("excluded-content: " + ("OK" if not bad else "FAIL"))
    for x in bad:
        print("  - " + x)
    return 0 if a.report or not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
