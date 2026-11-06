"""FR -> design -> test -> evidence conformance for PF-SB functional specs."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "scripts" / "dev")):
    if p not in sys.path:
        sys.path.insert(0, p)
from core import backlog  # noqa: E402

CFG = ROOT / "config" / "functional-spec.json"


def _cfg() -> dict:
    return json.loads(CFG.read_text(encoding="utf-8-sig"))


def _enforced(item: dict, cfg: dict) -> bool:
    if str(item.get("id") or "") in (cfg.get("enforce_items") or []):
        return True
    from functional_spec import should_enforce
    return should_enforce(item, cfg)


def problems(item: dict, cfg: dict | None = None) -> list[str]:
    cfg = cfg or _cfg()
    if not _enforced(item, cfg):
        return []
    fs = item.get("functional_spec") or {}
    frs = [str(r.get("id")) for r in (fs.get("requirements") or []) if isinstance(r, dict) and r.get("id")]
    if not frs:
        return ["functional_spec.requirements has no FR ids"]
    pack = item.get("design_pack") or {}
    if not str(pack.get("functional_ref") or "").strip():
        return ["design_pack.functional_ref missing"]
    cov = pack.get("coverage") or []
    if not isinstance(cov, list) or not cov:
        return ["design_pack.coverage missing"]
    bad = []
    by_fr = {}
    for i, row in enumerate(cov, 1):
        if not isinstance(row, dict):
            bad.append(f"coverage[{i}] must be an object")
            continue
        fr = str(row.get("fr") or "")
        if not fr:
            bad.append(f"coverage[{i}].fr missing")
            continue
        by_fr.setdefault(fr, []).append(row)
        if fr not in frs:
            bad.append(f"coverage[{i}] references unknown {fr}")
    for fr in frs:
        rows = by_fr.get(fr) or []
        if not rows:
            bad.append(f"coverage missing {fr}")
            continue
        if not any(r.get("tests") and r.get("evidence") for r in rows):
            bad.append(f"{fr} has no coverage row with tests + evidence")
    trace = fs.get("traceability") or []
    tmap = {str(r.get("fr")): r for r in trace if isinstance(r, dict)}
    for fr in frs:
        row = tmap.get(fr)
        if not row:
            bad.append(f"functional traceability missing {fr}")
            continue
        for key in ("design", "test", "evidence"):
            if not row.get(key):
                bad.append(f"functional traceability {fr} missing {key}")
    for fr in set(tmap) - set(frs):
        bad.append(f"functional traceability references unknown {fr}")
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Functional conformance check")
    ap.add_argument("--item", default="")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args(argv)
    cfg = _cfg()
    if a.all:
        bad = []
        for item in backlog.list_items("product_forge", None):
            bad += [f"{item.get('id')}: {p}" for p in problems(item, cfg)]
        print("conformance: " + ("OK" if not bad else "FAIL"))
        for x in bad:
            print("  - " + x)
        return 1 if bad else 0
    if not a.item:
        print("conformance: --item or --all required", file=sys.stderr)
        return 2
    item = backlog.get_epic("product_forge", None, a.item) or {}
    bad = problems(item, cfg)
    print("conformance: " + ("OK" if not bad else "FAIL"))
    for x in bad:
        print("  - " + x)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
