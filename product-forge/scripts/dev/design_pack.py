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
            "security", "observability", "performance", "test_matrix", "rollout", "rollback",
            "decisions", "guardrails", "learnings")
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


def runtime_should_enforce(item: dict, cfg: dict) -> bool:
    """Runtime-proof contract is enforced only for items created on/after its date."""
    try:
        created = _parse_date(item.get("created_at"))
        enforce = _parse_date(cfg.get("runtime_enforce_from"))
    except ValueError:
        return False
    if not created or not enforce:
        return False
    return created >= enforce


def _validate_cfg(cfg: dict) -> str:
    if not isinstance(cfg, dict):
        return "config is not an object"
    enforce = cfg.get("enforce_from")
    if not enforce:
        return "enforce_from missing"
    try:
        _parse_date(enforce)
    except ValueError:
        return f"enforce_from invalid: {enforce!r}"
    if "enforce_items" in cfg and not isinstance(cfg.get("enforce_items"), list):
        return "enforce_items must be a list"
    if "required_sections" in cfg and not isinstance(cfg.get("required_sections"), list):
        return "required_sections must be a list"
    if "required_contracts" in cfg and not isinstance(cfg.get("required_contracts"), list):
        return "required_contracts must be a list"
    if "runtime_enforce_from" in cfg:
        try:
            _parse_date(cfg.get("runtime_enforce_from"))
        except ValueError:
            return f"runtime_enforce_from invalid: {cfg.get('runtime_enforce_from')!r}"
    if "runtime_required_sections" in cfg and not isinstance(cfg.get("runtime_required_sections"), list):
        return "runtime_required_sections must be a list"
    return ""


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


def evaluate(item_id: str, item: dict | None = None) -> list[str]:
    """Public Gate 1 entry: fail closed on unknown items/invalid dates."""
    if item is None:
        item = backlog.get_epic("product_forge", None, item_id)
    if not item:
        return [f"item not found: {item_id}"]
    cfg = _cfg()
    cfg_problem = _validate_cfg(cfg)
    if cfg_problem:
        # Config defects short-circuit item date checks by design: a malformed config
        # cannot be trusted to classify dates, and fixing it first avoids misleading output.
        return [cfg_problem]
    bad = _date_problems(item, cfg)
    if bad:
        return bad
    if not should_enforce(item, cfg):
        return []
    return check(item)


def _areas_enforced(item: dict, cfg: dict) -> bool:
    start = _parse_date(cfg.get("areas_enforce_from"))
    created = _parse_date(item.get("created_at"))
    return bool(start and created and created >= start)


def _area_problems(areas) -> list[str]:
    bad = []
    if not isinstance(areas, list) or not areas:
        return ["design_pack.design_areas missing"]
    allowed = {"APPLICABLE", "N/A"}
    for i, a in enumerate(areas, 1):
        if not isinstance(a, dict):
            bad.append(f"design_areas[{i}] must be an object")
            continue
        area = str(a.get("area") or "").strip()
        status = str(a.get("status") or "").strip().upper()
        reason = str(a.get("reason") or "").strip()
        if not area:
            bad.append(f"design_areas[{i}].area missing")
        if status not in allowed:
            bad.append(f"design_areas[{i}].status must be APPLICABLE or N/A")
        if not reason:
            bad.append(f"design_areas[{i}].reason missing (N/A and APPLICABLE both require a reason)")
        if status == "APPLICABLE" and not (a.get("sections") or []):
            bad.append(f"design_areas[{i}].sections missing")
        if status == "APPLICABLE" and not (a.get("evidence") or []):
            bad.append(f"design_areas[{i}].evidence missing")
    return bad


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
    if pack.get("design_areas") is not None:
        bad += _area_problems(pack.get("design_areas"))
    elif _areas_enforced(item, cfg):
        bad.append("design_pack.design_areas missing (base + inferred areas required)")
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

    if runtime_should_enforce(item, cfg):
        for k in tuple(cfg.get("runtime_required_sections") or ()):
            if not pack.get(k):
                bad.append(f"design_pack.{k} missing (runtime contract)")
        rc = pack.get("runtime_contract")
        if not isinstance(rc, dict):
            bad.append("design_pack.runtime_contract must be an object")
        else:
            for k in ("trigger", "entrypoint", "call_sites", "adapter", "contract",
                      "failure_behavior", "observable_result"):
                if not rc.get(k):
                    bad.append(f"design_pack.runtime_contract.{k} missing")
        proof = pack.get("proof_plan")
        if not isinstance(proof, dict):
            bad.append("design_pack.proof_plan must be an object")
        else:
            for k in ("failing_test", "red_evidence", "green_evidence"):
                if not proof.get(k):
                    bad.append(f"design_pack.proof_plan.{k} missing")
        if not pack.get("ac_evidence"):
            bad.append("design_pack.ac_evidence missing (runtime contract)")
        if not pack.get("stop_conditions"):
            bad.append("design_pack.stop_conditions missing (runtime contract)")
    return bad


def _join(v):
    if isinstance(v, list):
        return "\n".join(f"- {x}" for x in v) or "- none"
    return str(v or "- none")


def _join_mapping(v):
    if isinstance(v, dict):
        return "\n".join(f"- **{k}**: {_join(x)}" for k, x in v.items()) or "- none"
    return _join(v)


def _areas(areas) -> str:
    if not isinstance(areas, list) or not areas:
        return "- none declared"
    lines = []
    for a in areas:
        if not isinstance(a, dict):
            lines.append(f"- invalid area row: {a!r}")
            continue
        lines.append(f"- **{a.get('area') or '?'}** ? {a.get('status') or '?'}: {a.get('reason') or ''}"
                     f" | sections: {', '.join(a.get('sections') or []) or '-'}"
                     f" | evidence: {', '.join(a.get('evidence') or []) or '-'}")
    return "\n".join(lines)


def render(item: dict) -> str:
    pack = item.get("design_pack") or {}
    contracts = pack.get("contracts") or {}
    failures = pack.get("failure_matrix") or []
    tests = pack.get("test_matrix") or []
    rc = pack.get("runtime_contract") or {}
    proof = pack.get("proof_plan") or {}
    tpl = (ROOT / "templates" / "DESIGN-PACK.md").read_text(encoding="utf-8-sig")
    return (tpl.replace("{{ITEM}}", str(item.get("id") or ""))
              .replace("{{TITLE}}", str(item.get("title") or ""))
              .replace("{{VERSION}}", str(pack.get("version") or 1))
              .replace("{{STATUS}}", str(item.get("status") or ""))
              .replace("{{REVIEW_SHA}}", str(pack.get("review_sha") or ""))
              .replace("{{GENERATED_AT}}", datetime.now(timezone.utc).isoformat())
              .replace("{{STANDARDS}}", _join(pack.get("standards")))
              .replace("{{CODE_GUIDELINES}}", _join(pack.get("code_guidelines")))
              .replace("{{REQUIREMENTS}}", _join(item.get("acceptance_criteria") or pack.get("requirements")))
              .replace("{{SCOPE}}", _join(pack.get("scope")))
              .replace("{{NON_GOALS}}", _join(pack.get("non_goals")))
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
              .replace("{{DECISIONS}}", _join(pack.get("decisions")))
              .replace("{{RUNTIME_TRIGGER}}", _join(rc.get("trigger")))
              .replace("{{RUNTIME_ENTRYPOINT}}", _join(rc.get("entrypoint")))
              .replace("{{RUNTIME_CALL_SITES}}", _join(rc.get("call_sites")))
              .replace("{{RUNTIME_ADAPTER}}", _join(rc.get("adapter")))
              .replace("{{RUNTIME_CONTRACT}}", _join(rc.get("contract")))
              .replace("{{RUNTIME_FAILURE}}", _join(rc.get("failure_behavior")))
              .replace("{{RUNTIME_RESULT}}", _join(rc.get("observable_result")))
              .replace("{{PROOF_PLAN}}", _join_mapping(proof))
              .replace("{{AC_EVIDENCE}}", _join_mapping(pack.get("ac_evidence")))
              .replace("{{STOP_CONDITIONS}}", _join(pack.get("stop_conditions")))
              .replace("{{DESIGN_AREAS}}", _areas(pack.get("design_areas"))))


def _norm(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.startswith("- **Generated:**"))


def fresh(item: dict) -> bool:
    p = DESIGN_DIR / f"{item.get('id')}.md"
    if not p.is_file():
        return False
    return _norm(p.read_text(encoding="utf-8")) == _norm(render(item))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Design pack check/render")
    ap.add_argument("--item", default="")
    ap.add_argument("--all", action="store_true", help="check items created on/after enforce_from")
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--fresh", action="store_true", help="generated MD must match item.design_pack")
    a = ap.parse_args(argv)
    if not a.render and not a.check and not a.fresh:
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
            if a.fresh and should_enforce(item, cfg) and not fresh(item):
                bad.append(f"{item.get('id')}: generated design MD is stale")
        print("design-pack: " + ("OK" if not bad else "FAIL"))
        for x in bad:
            print("  - " + x)
        return 1 if bad else 0
    if not a.item:
        print("design-pack: --item is required unless --all", file=sys.stderr)
        return 2
    item = backlog.get_epic("product_forge", None, a.item) or {}
    bad = evaluate(a.item, item=item)
    if a.render:
        DESIGN_DIR.mkdir(parents=True, exist_ok=True)
        out = DESIGN_DIR / f"{a.item}.md"
        out.write_text(render(item), encoding="utf-8")
        print(f"design-pack: wrote {out}")
    if a.fresh and not fresh(item):
        print(f"design-pack: STALE {DESIGN_DIR / (a.item + '.md')}", file=sys.stderr)
        return 1
    if a.check:
        print("design-pack: " + ("OK" if not bad else "FAIL"))
        for x in bad:
            print("  - " + x)
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
