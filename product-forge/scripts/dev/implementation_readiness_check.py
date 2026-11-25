"""Fail-closed implementation-controls readiness check (BI-PF-1538).

Pre-code: every AC must have a complete implementation-controls row.
Final: declared symbols/tests/evidence must resolve in the working tree.

Run:
  python scripts/dev/implementation_readiness_check.py --item BI-PF-1234
  python scripts/dev/implementation_readiness_check.py --item BI-PF-1234 --final
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts" / "dev") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "dev"))

from core import backlog  # noqa: E402

FIELDS = ("id", "ac", "kind", "control", "symbol", "positive_test", "negative_test",
          "tenant_test", "concurrency_test", "observability", "evidence")
REQUIRED_KINDS = ("security", "tenant", "failure", "config", "observability")
def _config() -> dict:
    try:
        return json.loads((ROOT / "config" / "implementation-controls.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


PLACEHOLDERS = re.compile(r"\b(tbd|todo|fixme|pending|not specified|placeholder|n/a without reason)\b", re.I)
PATHLIKE = re.compile(r"(?:^|[\s(])((?:[\w.-]+/)+[\w.-]+\.(?:py|go|sql|json|yml|yaml|md|sh))")


def _placeholder(value) -> bool:
    text = " ".join(value) if isinstance(value, list) else str(value or "")
    return not text.strip() or bool(PLACEHOLDERS.search(text))


def problems(item: dict, final: bool = False, root: Path = ROOT) -> list[str]:
    bad: list[str] = []
    pack = item.get("design_pack") or {}
    rows = pack.get("implementation_controls")
    if not isinstance(rows, list) or not rows:
        return ["design_pack.implementation_controls missing or empty"]
    ids = set()
    kinds = set()
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            bad.append(f"row {i}: not an object")
            continue
        rid = str(row.get("id") or f"row-{i}")
        if rid in ids:
            bad.append(f"{rid}: duplicate id")
        ids.add(rid)
        kinds.add(str(row.get("kind") or ""))
        for f in FIELDS:
            if f not in row:
                bad.append(f"{rid}: missing {f}")
            elif _placeholder(row.get(f)):
                bad.append(f"{rid}: placeholder/empty {f}")
        if final:
            for f in ("symbol", "positive_test", "negative_test", "evidence"):
                for p in PATHLIKE.findall(str(row.get(f) or "")):
                    if not (root / p).exists():
                        bad.append(f"{rid}: {f} path does not exist: {p}")
            for f in ("negative_test", "tenant_test", "concurrency_test"):
                v = str(row.get(f) or "")
                if v and v.upper().startswith("N/A") and ":" not in v:
                    bad.append(f"{rid}: {f} N/A requires a reason")
    required_kinds = REQUIRED_KINDS
    if item.get("tooling") or (item.get("design_pack") or {}).get("tooling"):
        required_kinds = ("security", "failure", "config", "observability")
    for k in required_kinds:
        if k not in kinds:
            bad.append(f"missing required control kind: {k}")
    ac_count = len([a for a in (item.get("acceptance_criteria") or []) if str(a).strip()])
    covered = {str(r.get("ac")) for r in rows if isinstance(r, dict)}
    if ac_count and len(covered) < ac_count:
        bad.append(f"AC coverage: {len(covered)} mapped rows for {ac_count} acceptance criteria")
    cfg = root / "config" / "implementation-controls.json"
    try:
        checks = _config().get("checks") or []
        if not checks:
            bad.append("config/implementation-controls.json has no checks")
    except Exception as e:
        bad.append(f"config/implementation-controls.json unreadable: {e}")
    return bad


def all_problems(items, final: bool = False, cutoff: str = "") -> tuple[list[str], int]:
    bad: list[str] = []
    checked = 0
    for item in items:
        created = str(item.get("created_at") or "")
        if not created:
            bad.append(f"{item.get('id')}: created_at missing; cannot apply cutoff")
            continue
        if cutoff and created < cutoff:
            continue
        pack = item.get("design_pack") or {}
        if not pack:
            continue
        if pack.get("tooling") is not True and not pack.get("implementation_controls"):
            continue
        checked += 1
        if not pack.get("implementation_controls"):
            bad.append(f"{item.get('id')}: design_pack.implementation_controls missing")
            continue
        bad += [f"{item.get('id')}: {p}" for p in problems(item, final=final)]
    if checked == 0:
        bad.append("no enforced items checked (fail closed)")
    return bad, checked


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Implementation-controls readiness check")
    ap.add_argument("--item", default="")
    ap.add_argument("--all", action="store_true", help="check every item that declares a design pack")
    ap.add_argument("--final", action="store_true", help="verify declared symbols/tests/evidence exist")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.all:
        cutoff = str(_config().get("enforce_from") or "")
        bad, checked = all_problems(backlog.list_items("product_forge", None), final=a.final, cutoff=cutoff)
        out = {"ok": not bad, "checked": checked, "final": bool(a.final), "problems": bad}
        print(json.dumps(out, indent=2) if a.json else _render(out))
        return 0 if out["ok"] else 1
    if not a.item:
        ap.error("--item or --all required")
    item = backlog.get_epic("product_forge", None, a.item)
    if not item:
        out = {"ok": False, "problems": ["item not found"]}
    else:
        bad = problems(item, final=a.final)
        out = {"ok": not bad, "item": a.item, "final": bool(a.final), "problems": bad}
    print(json.dumps(out, indent=2) if a.json else _render(out))
    return 0 if out["ok"] else 1


def _render(out: dict) -> str:
    if out["ok"]:
        return f"implementation-readiness: OK ({out.get('item')})"
    return "implementation-readiness: FAIL\n" + "\n".join("  - " + p for p in out["problems"])


if __name__ == "__main__":
    raise SystemExit(main())
