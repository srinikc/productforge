"""Canonical specification contract compiler/validator (BI-PF-1547).

Validates the item's canonical spec contract against the generated design_pack,
functional_spec and spec_pack. Mechanical drift blocks Gate 1 before architect review.
"""
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

CFG = ROOT / "config" / "spec-contract.json"
PLACEHOLDERS = ("tbd", "todo", "unspecified", "not specified", "placeholder")


def _cfg() -> dict:
    try:
        return json.loads(CFG.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _norm(value) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    return str(value or "").strip()


def _bad_text(value) -> bool:
    text = _norm(value).lower()
    return not text or any(x in text for x in PLACEHOLDERS)


def problems(item: dict) -> list[str]:
    """Return mechanical contract problems; empty means consistent."""
    bad: list[str] = []
    design = item.get("design_pack") or {}
    func = item.get("functional_spec") or {}
    specs = item.get("spec_pack") or {}

    # One canonical rollback and config contract.
    if _norm(design.get("rollback")) != _norm(func.get("rollback")):
        bad.append("rollback differs between design_pack and functional_spec")
    dcfg = (design.get("contracts") or {}).get("config")
    fcfg = func.get("config_contract")
    if dcfg is not None and fcfg is not None and _norm(dcfg) != _norm(fcfg):
        bad.append("config_contract differs between design_pack and functional_spec")

    # AC/FR/control/test/evidence graph.
    acs = [str(x) for x in (item.get("acceptance_criteria") or []) if str(x).strip()]
    rows = design.get("implementation_controls") or []
    if not isinstance(rows, list) or not rows:
        bad.append("design_pack.implementation_controls missing")
        rows = []
    ids = set()
    ac_seen = set()
    kinds = set()
    for i, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            bad.append(f"control[{i}] not an object")
            continue
        rid = str(row.get("id") or "")
        if not rid or rid in ids:
            bad.append(f"control[{i}] missing/duplicate id")
        ids.add(rid)
        ac_seen.add(str(row.get("ac") or ""))
        kinds.add(str(row.get("kind") or ""))
        for key in ("ac", "fr", "kind", "control", "symbol", "positive_test", "negative_test", "evidence"):
            if _bad_text(row.get(key)):
                bad.append(f"{rid or i}.{key} missing or placeholder")
        if not str(row.get("candidate_sha") or "").strip():
            bad.append(f"{rid or i}.candidate_sha missing")
    for i in range(1, len(acs) + 1):
        if f"AC-{i}" not in ac_seen:
            bad.append(f"AC-{i} has no control row")
    required = ("security", "failure", "config", "observability")
    for kind in required:
        if kind not in kinds:
            bad.append(f"missing required control kind: {kind}")

    # Candidate SHA must be stable across evidence rows.
    shas = set()
    for row in (design.get("ac_evidence") or []):
        if isinstance(row, dict) and row.get("candidate_sha"):
            shas.add(str(row["candidate_sha"]))
    for row in (design.get("coverage") or []):
        if isinstance(row, dict) and row.get("candidate_sha"):
            shas.add(str(row["candidate_sha"]))
    for row in (func.get("traceability") or []):
        if isinstance(row, dict) and row.get("candidate_sha"):
            shas.add(str(row["candidate_sha"]))
    if not shas:
        bad.append("candidate_sha missing from AC evidence")
    elif len(shas) > 1:
        bad.append("candidate_sha differs across evidence rows")
    for row in (design.get("ac_evidence") or []):
        if isinstance(row, dict) and not str(row.get("candidate_sha") or "").strip():
            bad.append(f"{row.get('ac') or 'AC'}.candidate_sha missing")

    # API contract completeness when API is declared.
    impact = item.get("api_impact") or {}
    if impact.get("needs_api"):
        api = (design.get("contracts") or {}).get("api") or {}
        for key in ("method", "path", "auth", "validation"):
            if not str(api.get(key) or "").strip():
                bad.append(f"api contract missing {key}")

    # N/A reasons in spec pack must be concrete.
    for row in (specs.get("applicability") or []):
        if isinstance(row, dict) and str(row.get("status") or "").upper() == "N/A":
            if len(str(row.get("reason") or "").strip()) < 8:
                bad.append(f"{row.get('spec') or 'spec'}: N/A reason too short")
    return bad


def enforced(item: dict, cfg: dict) -> bool:
    if str(item.get("id") or "") in (cfg.get("enforce_items") or []):
        return True
    created = str(item.get("created_at") or "")
    return bool(created and created >= str(cfg.get("enforce_from") or ""))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Canonical spec contract compiler/validator")
    ap.add_argument("--item", default="")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    cfg = _cfg()
    bad = []
    checked = 0
    if a.all:
        for item in backlog.list_items("product_forge", None):
            if enforced(item, cfg):
                checked += 1
                bad += [f"{item.get('id')}: {p}" for p in problems(item)]
        if checked == 0:
            bad.append("no enforced items checked")
    else:
        if not a.item:
            ap.error("--item or --all required")
        item = backlog.get_epic("product_forge", None, a.item)
        if not item:
            bad.append("item not found")
        else:
            checked = 1
            bad = problems(item)
    out = {"ok": not bad, "checked": checked, "problems": bad}
    print(json.dumps(out, indent=2) if a.json else ("spec-contract: OK" if not bad else "spec-contract: FAIL\n" + "\n".join("  - " + p for p in bad)))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
