"""Validate design controls and current-SHA control/fix evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "scripts" / "dev")):
    if str(p) not in sys.path:
        sys.path.insert(0, p)
from core import backlog  # noqa: E402
import design_contract_check as dcc  # noqa: E402

CFG = ROOT / "config" / "control-matrix.json"


def current_sha() -> str:
    """Stable review-relevant candidate SHA: base + committed diff, never HEAD/evidence.

    Committing control evidence must not invalidate the evidence it records.
    """
    mb = subprocess.run(["git", "merge-base", "origin/develop", "HEAD"], cwd=str(ROOT),
                        capture_output=True, text=True, encoding="utf-8",
                        errors="replace")
    if mb.returncode != 0 or not (mb.stdout or "").strip():
        raise RuntimeError(f"cannot resolve origin/develop for control evidence: {(mb.stderr or '').strip()}")
    base = mb.stdout.strip()
    diff = subprocess.run(
        ["git", "diff", "--binary", f"{base}..HEAD", "--", ".",
         ":(exclude)data/backlog/**", ":(exclude)dashboard/**",
         ":(exclude)engineering/trails/**", ":(exclude)engineering/evidence/**"],
        cwd=str(ROOT), capture_output=True,
    ).stdout
    return f"{base}-{hashlib.sha256(diff).hexdigest()[:12]}"


def controls(item: dict) -> list[dict]:
    return list((item.get("design_pack") or {}).get("controls") or item.get("controls") or [])


def problems(item_id: str, phase: str = "design", item: dict | None = None) -> list[str]:
    if item is None:
        item = backlog.get_epic("product_forge", None, item_id)
    if not item:
        return [f"item not found: {item_id}"]
    if not dcc.enforced(item, dcc._cfg()):
        return []
    cfg = json.loads(CFG.read_text(encoding="utf-8-sig"))
    rows = controls(item)
    bad = []
    if not rows:
        return ["no controls defined"]
    for c in rows:
        for key in cfg.get("required_control_fields") or []:
            if not c.get(key):
                bad.append(f"control {c.get('id') or '?'} missing {key}")
        check = str(c.get("check") or "")
        if check and not any(check.startswith(p) for p in (cfg.get("allowed_check_prefixes") or [])):
            bad.append(f"control {c.get('id') or '?'} unsupported check")
    if phase == "design":
        return sorted(set(bad))
    sha = current_sha()
    ev = list(item.get("control_evidence") or [])
    for c in rows:
        hit = [e for e in ev if str(e.get("control_id")) == str(c.get("id"))
               and str(e.get("sha")) == sha and str(e.get("result")).upper() == "PASS"]
        if not hit:
            bad.append(f"control {c.get('id')} has no PASS evidence for current SHA {sha}")
    if phase == "fix":
        fixes = list(item.get("fix_evidence") or [])
        if not fixes:
            bad.append("fix_evidence missing")
        for f in fixes:
            for key in ("finding_sig", "origin_class", "regression_test", "controls_rerun",
                        "result", "evidence"):
                if not f.get(key):
                    bad.append(f"fix_evidence missing {key}")
            if str(f.get("result")).upper() != "PASS":
                bad.append(f"fix_evidence not PASS: {f.get('finding_sig')}")
    return sorted(set(bad))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Control gate")
    ap.add_argument("--item", required=True)
    ap.add_argument("--phase", choices=("design", "implementation", "fix"), default="design")
    a = ap.parse_args(argv)
    bad = problems(a.item, a.phase)
    if bad:
        print(f"control-gate: FAIL ({len(bad)})")
        for p in bad:
            print(f"  - {p}")
        return 1
    print("control-gate: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
