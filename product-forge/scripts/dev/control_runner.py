"""Execute item controls and append current-SHA evidence to the item."""
from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "scripts" / "dev")):
    if str(p) not in sys.path:
        sys.path.insert(0, p)
from core import backlog  # noqa: E402

CFG = ROOT / "config" / "control-matrix.json"


def current_sha() -> str:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT), capture_output=True,
                          text=True, encoding="utf-8", errors="replace").stdout.strip()
    diff = subprocess.run(
        ["git", "diff", "--binary", "HEAD", "--", ".", ":(exclude)data/backlog/**",
         ":(exclude)dashboard/**", ":(exclude)engineering/trails/**",
         ":(exclude)engineering/evidence/**"],
        cwd=str(ROOT), capture_output=True,
    ).stdout
    return f"{head}-{hashlib.sha256(diff).hexdigest()[:12]}"


def controls(item: dict) -> list[dict]:
    return list((item.get("design_pack") or {}).get("controls") or item.get("controls") or [])


def run(item_id: str, phase: str, only: str = "") -> int:
    it = backlog.get_epic("product_forge", None, item_id) or {}
    if not it:
        print(f"control-runner: FAIL - item not found: {item_id}", file=sys.stderr)
        return 2
    cfg = json.loads(CFG.read_text(encoding="utf-8-sig"))
    rows = controls(it)
    if only:
        rows = [r for r in rows if str(r.get("id")) == only]
    if not rows:
        print("control-runner: FAIL - no controls", file=sys.stderr)
        return 1
    evidence = list(it.get("control_evidence") or [])
    start = len(evidence)
    bad = 0
    for c in rows:
        check = str(c.get("check") or "")
        cwd = (ROOT / str(c.get("cwd") or ".")).resolve()
        if cwd != ROOT.resolve() and ROOT.resolve() not in cwd.parents:
            print(f"control-runner: FAIL - cwd escapes repo for {c.get('id')}: {cwd}", file=sys.stderr)
            bad += 1
            continue
        try:
            argv = shlex.split(check)
        except ValueError as e:
            print(f"control-runner: FAIL - invalid check for {c.get('id')}: {e}", file=sys.stderr)
            bad += 1
            continue
        if not argv:
            print(f"control-runner: FAIL - empty check for {c.get('id')}", file=sys.stderr)
            bad += 1
            continue
        prefixes = [shlex.split(str(p)) for p in (cfg.get("allowed_check_prefixes") or [])]
        if not any(argv[:len(p)] == p for p in prefixes if p):
            print(f"control-runner: FAIL - unsupported check for {c.get('id')}: {check}", file=sys.stderr)
            bad += 1
            continue
        r = subprocess.run(argv, cwd=str(cwd), shell=False, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        evrel = str(c.get("evidence") or f"engineering/trails/{item_id}-{c.get('id')}.txt").replace("\\", "/")
        if not (evrel.startswith("engineering/trails/") or evrel.startswith("engineering/evidence/")):
            print(f"control-runner: FAIL - evidence must be under engineering/trails or engineering/evidence: {evrel}", file=sys.stderr)
            bad += 1
            continue
        out = (ROOT / evrel).resolve()
        root_res = ROOT.resolve()
        if out != root_res and root_res not in out.parents:
            print(f"control-runner: FAIL - evidence escapes repo for {c.get('id')}: {evrel}", file=sys.stderr)
            bad += 1
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text((r.stdout or "") + ("\n" + r.stderr if r.stderr else ""), encoding="utf-8")
        result = "PASS" if r.returncode == 0 else "FAIL"
        evidence.append({"control_id": c.get("id"), "phase": phase, "sha": "",
                         "result": result, "returncode": r.returncode,
                         "evidence": str(out.relative_to(root_res)).replace("\\", "/"),
                         "at": datetime.now(timezone.utc).isoformat()})
        print(f"control-runner: {c.get('id')} {result}")
        if result != "PASS":
            bad += 1
    sha = current_sha()
    for e in evidence[start:]:
        e["sha"] = sha
    backlog.update("product_forge", None, item_id, control_evidence=evidence)
    return 1 if bad else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run item controls")
    ap.add_argument("--item", required=True)
    ap.add_argument("--phase", choices=("pre", "post", "fix"), default="post")
    ap.add_argument("--only", default="")
    a = ap.parse_args(argv)
    return run(a.item, a.phase, a.only)


if __name__ == "__main__":
    raise SystemExit(main())
