"""Durable design pack (BI-PF-1484): validate + render engineering/design/<ID>.md."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "scripts" / "dev")):
    if p not in sys.path:
        sys.path.insert(0, p)
from core import backlog  # noqa: E402

DESIGN_DIR = ROOT / "engineering" / "design"
CFG = ROOT / "config" / "design-pack.json"
REQUIRED = ("requirements", "invariants", "contracts", "failure_matrix", "dependencies",
            "security", "observability", "performance", "test_matrix", "rollout", "rollback", "decisions")
CONTRACTS = ("api", "db", "files", "config")


def _cfg() -> dict:
    try:
        return json.loads(CFG.read_text(encoding="utf-8-sig"))
    except Exception as e:
        raise RuntimeError(f"cannot read design-pack config: {e}")


def check(item: dict) -> list[str]:
    bad = []
    pack = item.get("design_pack") or {}
    if not pack:
        return ["design_pack missing"]
    for k in REQUIRED:
        if not pack.get(k):
            bad.append(f"design_pack.{k} missing")
    contracts = pack.get("contracts") or {}
    for k in CONTRACTS:
        if k not in contracts:
            bad.append(f"design_pack.contracts.{k} missing")
    acs = item.get("acceptance_criteria") or []
    tests = pack.get("test_matrix") or []
    covered = {str(t.get("ac")) for t in tests if isinstance(t, dict)}
    for i, _ in enumerate(acs, 1):
        if f"AC-{i}" not in covered and str(i) not in covered:
            bad.append(f"test_matrix missing AC-{i}")
    return bad


def _join(v):
    if isinstance(v, list):
        return "\n".join(f"- {x}" for x in v) or "- none"
    return str(v or "- none")


def render(item: dict) -> str:
    pack = item.get("design_pack") or {}
    contracts = pack.get("contracts") or {}
    failures = pack.get("failure_matrix") or []
    tests = pack.get("test_matrix") or []
    tpl = (ROOT / "templates" / "DESIGN-PACK.md").read_text(encoding="utf-8-sig")
    return (tpl.replace("{{ITEM}}", str(item.get("id") or ""))
              .replace("{{TITLE}}", str(item.get("title") or ""))
              .replace("{{VERSION}}", str(pack.get("version") or 1))
              .replace("{{STATUS}}", str(item.get("status") or ""))
              .replace("{{REVIEW_SHA}}", str(pack.get("review_sha") or ""))
              .replace("{{GENERATED_AT}}", datetime.now(timezone.utc).isoformat())
              .replace("{{REQUIREMENTS}}", _join(item.get("acceptance_criteria") or pack.get("requirements")))
              .replace("{{SCOPE}}", _join(pack.get("scope")))
              .replace("{{INVARIANTS}}", _join(pack.get("invariants")))
              .replace("{{API}}", _join(contracts.get("api")))
              .replace("{{DB}}", _join(contracts.get("db")))
              .replace("{{FILES}}", _join(contracts.get("files")) + "\n" + _join(contracts.get("config")))
              .replace("{{FAILURES}}", "\n".join(f"| {f.get('case','')} | {f.get('expected','')} | {f.get('code','')} |" for f in failures) or "| - | - | - |")
              .replace("{{DEPENDENCIES}}", _join(pack.get("dependencies")))
              .replace("{{SECURITY}}", _join(pack.get("security")))
              .replace("{{OBSERVABILITY}}", _join(pack.get("observability")))
              .replace("{{PERFORMANCE}}", _join(pack.get("performance")))
              .replace("{{ROLLOUT}}", _join(pack.get("rollout")) + "\n" + _join(pack.get("rollback")))
              .replace("{{TESTS}}", "\n".join(f"| {t.get('ac','')} | {t.get('kind','')} | {t.get('test','')} |" for t in tests) or "| - | - | - |")
              .replace("{{DECISIONS}}", _join(pack.get("decisions"))))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Design pack check/render")
    ap.add_argument("--item", default="")
    ap.add_argument("--all", action="store_true", help="check items created on/after enforce_from")
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    if not a.render and not a.check:
        print("design-pack: choose --render and/or --check", file=sys.stderr)
        return 2
    if a.all:
        enforce = str(_cfg().get("enforce_from") or "9999-12-31")
        bad = []
        for item in backlog.list_items("product_forge", None):
            if str(item.get("created_at") or "") >= enforce:
                for p in check(item):
                    bad.append(f"{item.get('id')}: {p}")
        print("design-pack: " + ("OK" if not bad else "FAIL"))
        for x in bad:
            print("  - " + x)
        return 1 if bad else 0
    if not a.item:
        print("design-pack: --item is required unless --all", file=sys.stderr)
        return 2
    item = backlog.get_epic("product_forge", None, a.item) or {}
    bad = check(item)
    if a.render:
        DESIGN_DIR.mkdir(parents=True, exist_ok=True)
        out = DESIGN_DIR / f"{a.item}.md"
        out.write_text(render(item), encoding="utf-8")
        print(f"design-pack: wrote {out}")
    if a.check:
        print("design-pack: " + ("OK" if not bad else "FAIL"))
        for x in bad:
            print("  - " + x)
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
