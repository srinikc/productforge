"""Durable design pack (BI-PF-1484): validate + render engineering/design/<ID>.md."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
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


def _parse_date(value) -> date | None:
    v = str(value or "")
    if not v:
        return None
    try:
        return datetime.fromisoformat(v).date()
    except ValueError:
        return date.fromisoformat(v)


def should_enforce(item: dict, cfg: dict) -> bool:
    if str(item.get("id") or "") in (cfg.get("enforce_items") or []):
        return True
    try:
        created = _parse_date(item.get("created_at"))
        enforce = _parse_date(cfg.get("enforce_from"))
    except ValueError:
        return False
    if not created or not enforce:
        return False
    return created >= enforce


def _date_problems(item: dict, cfg: dict) -> list[str]:
    bad = []
    created = str(item.get("created_at") or "")
    enforce = str(cfg.get("enforce_from") or "")
    if not enforce:
        bad.append("enforce_from missing")
    if str(item.get("status") or "").lower() == "in_progress" and not created:
        bad.append("created_at missing")
    for label, value in (("created_at", created), ("enforce_from", enforce)):
        if value:
            try:
                _parse_date(value)
            except ValueError:
                bad.append(f"{label} invalid: {value!r}")
    return bad


def evaluate(item_id: str) -> list[str]:
    """Public Gate 1 entry: fail closed on unknown items/invalid dates."""
    item = backlog.get_epic("product_forge", None, item_id)
    if not item:
        return [f"item not found: {item_id}"]
    cfg = _cfg()
    bad = _date_problems(item, cfg)
    if bad:
        return bad
    if not should_enforce(item, cfg):
        return []
    return check(item)


def check(item: dict) -> list[str]:
    bad = []
    pack = item.get("design_pack") or {}
    if not pack:
        return ["design_pack missing"]
    try:
        cfg = _cfg()
        required = tuple(cfg.get("required_sections") or REQUIRED)
        contracts_req = tuple(cfg.get("required_contracts") or CONTRACTS)
    except Exception as e:
        return [f"design-pack config error ({type(e).__name__}): {e}"]
    for k in required:
        if not pack.get(k):
            bad.append(f"design_pack.{k} missing")
    contracts = pack.get("contracts") or {}
    for k in contracts_req:
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
    if a.all and (a.item or a.render):
        print("design-pack: --all cannot be combined with --item/--render", file=sys.stderr)
        return 2
    if a.all:
        try:
            cfg = _cfg()
            if not cfg.get("enforce_from"):
                raise RuntimeError("enforce_from missing")
            _parse_date(cfg.get("enforce_from"))
        except Exception as e:
            print(f"design-pack: FAIL - {e}")
            return 1
        bad = []
        for item in backlog.list_items("product_forge", None):
            for p in evaluate(str(item.get("id") or "")):
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
