"""Conditional spec pack: every spec is APPLICABLE with evidence or N/A with a reason."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "scripts" / "dev")):
    if p not in sys.path:
        sys.path.insert(0, p)
from core import backlog  # noqa: E402

SPEC_DIR = ROOT / "engineering" / "specs"
CFG = ROOT / "config" / "spec-pack.json"


def _cfg() -> dict:
    return json.loads(CFG.read_text(encoding="utf-8-sig"))


def _date(v) -> date | None:
    s = str(v or "")
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).date()
    except ValueError:
        return date.fromisoformat(s)


def should_enforce(item: dict, cfg: dict) -> bool:
    if str(item.get("id") or "") in (cfg.get("enforce_items") or []):
        return True
    created = _date(item.get("created_at"))
    start = _date(cfg.get("enforce_from"))
    return bool(created and start and created >= start)


def _exists(ref: str) -> bool:
    s = str(ref or "").strip()
    if not s:
        return False
    p = Path(s)
    if not p.is_absolute():
        p = ROOT / s
    return p.exists()


def problems(item: dict, cfg: dict | None = None) -> list[str]:
    cfg = cfg or _cfg()
    if not should_enforce(item, cfg):
        return []
    pack = item.get("spec_pack")
    if not isinstance(pack, dict) or not pack:
        return ["spec_pack missing"]
    bad: list[str] = []
    for k in ("version", "status", "functional_ref", "design_ref", "applicability"):
        if not pack.get(k):
            bad.append(f"spec_pack.{k} missing")
    rows = pack.get("applicability")
    if not isinstance(rows, list) or not rows:
        return bad + ["spec_pack.applicability must be a non-empty list"]
    required = list(cfg.get("required_specs") or [])
    seen = {}
    for i, r in enumerate(rows, 1):
        if not isinstance(r, dict):
            bad.append(f"applicability[{i}] must be an object")
            continue
        for k in cfg.get("required_row_fields") or []:
            if not str(r.get(k) or "").strip():
                bad.append(f"applicability[{i}].{k} missing")
        name = str(r.get("spec") or "")
        if name in seen:
            bad.append(f"duplicate spec row {name}")
        seen[name] = r
        status = str(r.get("status") or "").upper()
        if status not in (cfg.get("statuses") or []):
            bad.append(f"{name or '?'}.status must be APPLICABLE or N/A")
            continue
        if status == "N/A":
            reason = str(r.get("reason") or "").strip()
            if len(reason) < 8:
                bad.append(f"{name}.N/A reason must be concrete")
            continue
        for k in cfg.get("applicable_row_fields") or []:
            if not r.get(k):
                bad.append(f"{name}.{k} missing")
        if not _exists(str(r.get("artifact") or "")):
            bad.append(f"{name}.artifact not found: {r.get('artifact')}")
        if not isinstance(r.get("sections"), list) or not r.get("sections"):
            bad.append(f"{name}.sections must be a non-empty list")
        ev = r.get("evidence")
        if not isinstance(ev, list) or not ev:
            bad.append(f"{name}.evidence must be a non-empty list")
        else:
            for e in ev:
                if not _exists(str(e)):
                    bad.append(f"{name}.evidence not found: {e}")
    for name in required:
        if name not in seen:
            bad.append(f"applicability missing required spec: {name}")
    return bad


def _join(v) -> str:
    if isinstance(v, list):
        return "\n".join(f"- {x}" for x in v) or "- none"
    return str(v or "- none")


def render(item: dict) -> str:
    pack = item.get("spec_pack") or {}
    rows = []
    for r in pack.get("applicability") or []:
        if not isinstance(r, dict):
            continue
        sections = ", ".join(str(x) for x in (r.get("sections") or []))
        evidence = ", ".join(str(x) for x in (r.get("evidence") or []))
        rows.append(f"| {r.get('spec','')} | {r.get('status','')} | {r.get('owner','')} | {r.get('reason','')} | {r.get('artifact','')} | {sections} | {evidence} |")
    tpl = (ROOT / "templates" / "SPEC-PACK.md").read_text(encoding="utf-8-sig")
    return (tpl.replace("{{ITEM}}", str(item.get("id") or ""))
              .replace("{{TITLE}}", str(item.get("title") or ""))
              .replace("{{VERSION}}", str(pack.get("version") or 1))
              .replace("{{STATUS}}", str(pack.get("status") or ""))
              .replace("{{FUNCTIONAL_REF}}", str(pack.get("functional_ref") or ""))
              .replace("{{DESIGN_REF}}", str(pack.get("design_ref") or ""))
              .replace("{{ROWS}}", "\n".join(rows) or "| - | - | - | - | - | - | - |"))


def fresh(item: dict) -> bool:
    p = SPEC_DIR / f"{item.get('id')}-spec-pack.md"
    if not p.is_file():
        return False
    return p.read_text(encoding="utf-8").split("\n", 2)[-1] == render(item).split("\n", 2)[-1]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Conditional spec pack check/render")
    ap.add_argument("--item", default="")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--fresh", action="store_true")
    a = ap.parse_args(argv)
    cfg = _cfg()
    if a.all:
        bad = []
        for item in backlog.list_items("product_forge", None):
            if should_enforce(item, cfg):
                bad += [f"{item.get('id')}: {p}" for p in problems(item, cfg)]
                if a.fresh and not fresh(item):
                    bad.append(f"{item.get('id')}: generated spec pack is stale")
        print("spec-pack: " + ("OK" if not bad else "FAIL"))
        for x in bad:
            print("  - " + x)
        return 1 if bad else 0
    if not a.item:
        print("spec-pack: --item or --all required", file=sys.stderr)
        return 2
    item = backlog.get_epic("product_forge", None, a.item) or {}
    bad = problems(item, cfg)
    if a.render:
        SPEC_DIR.mkdir(parents=True, exist_ok=True)
        (SPEC_DIR / f"{a.item}-spec-pack.md").write_text(render(item), encoding="utf-8")
        print(f"spec-pack: wrote {SPEC_DIR / (a.item + '-spec-pack.md')}")
    if a.fresh and not fresh(item):
        bad.append("generated spec pack is stale")
    if a.check:
        print("spec-pack: " + ("OK" if not bad else "FAIL"))
        for x in bad:
            print("  - " + x)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
