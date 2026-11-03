"""Generic design/delivery contract validator (no item-specific logic).

Checks an item's design pack for executable coverage: every AC maps to a real entrypoint,
call chain, adapter, failure cases, test, and evidence. No placeholders or fake proof.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from fnmatch import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "scripts" / "dev")):
    if str(p) not in sys.path:
        sys.path.insert(0, p)
from core import backlog  # noqa: E402

CFG = ROOT / "config" / "design-contract.json"
EVIDENCE_REF = re.compile(r"(?:^|[\s:])(?:[\w./-]+\.(?:go|py|md|json|sql|yml|yaml)|Test\w+|test_\w+)")


def _cfg() -> dict:
    return json.loads(CFG.read_text(encoding="utf-8-sig"))


def _date(v) -> date | None:
    s = str(v or "")
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(s)
        except ValueError:
            return None


def enforced(item: dict, cfg: dict) -> bool:
    if item.get("design_pack"):
        return True
    created = _date(item.get("created_at"))
    start = _date(cfg.get("enforce_from"))
    # A present-but-invalid date is a typo: fail closed. An absent date on a legacy
    # item without a design pack is outside this contract.
    if str(item.get("created_at") or "").strip() and not created:
        return True
    if not created or not start:
        return False
    return created >= start


def _iter_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _iter_strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _iter_strings(v)


def _token_in(text: str, token: str) -> bool:
    return bool(re.search(rf"(?<![a-z0-9_]){re.escape(token)}(?![a-z0-9_])", text.lower()))


def _placeholder(value, tokens) -> bool:
    text = str(value or "").strip().lower()
    return not text or any(_token_in(text, t) for t in tokens)


def _test_exists(test: str) -> bool:
    t = str(test or "").strip()
    if not t:
        return False
    if t.startswith(("go test", "python -m pytest", "pytest ")):
        return True
    if "::" in t:
        rel, name = t.split("::", 1)
        p = ROOT / rel
        return p.is_file() and name in p.read_text(encoding="utf-8", errors="ignore")
    p = ROOT / t
    return p.is_file()


def _evidence_exists(evidence: str) -> bool:
    e = str(evidence or "").strip()
    if not e:
        return False
    if "://" in e:
        return True
    return (ROOT / e).exists()


def problems(item_id: str, item: dict | None = None) -> list[str]:
    if item is None:
        item = backlog.get_epic("product_forge", None, item_id)
    if not item:
        return [f"item not found: {item_id}"]
    cfg = _cfg()
    if not enforced(item, cfg):
        return []
    bad = []
    pack = item.get("design_pack") or {}
    acs = item.get("acceptance_criteria") or []
    for key in cfg.get("required_pack") or []:
        if not pack.get(key):
            bad.append(f"design_pack.{key} missing")
    standards = pack.get("standards") or []
    if not isinstance(standards, list):
        bad.append("design_pack.standards must be a list")
        standards = []
    for rel in cfg.get("required_standards") or []:
        if rel not in standards:
            bad.append(f"design_pack.standards missing: {rel}")
        if not (ROOT / rel).is_file():
            bad.append(f"standard file missing: {rel}")
    guidelines = pack.get("code_guidelines") or []
    if not isinstance(guidelines, list) or not guidelines:
        bad.append("design_pack.code_guidelines missing")
        guidelines = []
    for rel in guidelines:
        if not (ROOT / str(rel)).is_file():
            bad.append(f"coding guideline missing: {rel}")
    try:
        guide_cfg = json.loads((ROOT / "config" / "coding-guidelines.json").read_text(encoding="utf-8-sig"))
        required_guides = set()
        for f in item.get("affected_files") or []:
            p = str(f).replace("\\", "/")
            for ext, rels in (guide_cfg.get("by_extension") or {}).items():
                if p.endswith(ext):
                    required_guides.update(rels)
            for prefix, rels in (guide_cfg.get("by_path") or {}).items():
                if p.startswith(prefix):
                    required_guides.update(rels)
        missing_guides = sorted(required_guides - set(str(x) for x in guidelines))
        for rel in missing_guides:
            bad.append(f"relevant coding guideline not cited: {rel}")
    except Exception as e:
        bad.append(f"coding-guidelines config error: {e}")
    gcfg_path = ROOT / "config" / "guideline-compliance.json"
    try:
        gcfg = json.loads(gcfg_path.read_text(encoding="utf-8-sig"))
    except Exception as e:
        gcfg = {"required_fields": ["guideline", "applies_to", "evidence", "check"],
                "allowed_check_prefixes": ["go test", "go vet", "python -m pytest", "pytest", "bash ", "sh "],
                "error": str(e)}
    gcov = pack.get("guideline_coverage") or []
    if not isinstance(gcov, list) or not gcov:
        bad.append("design_pack.guideline_coverage missing")
        gcov = []
    for i, row in enumerate(gcov, 1):
        if not isinstance(row, dict):
            bad.append(f"guideline_coverage[{i}] must be an object")
            continue
        for key in gcfg.get("required_fields") or []:
            if not row.get(key):
                bad.append(f"guideline_coverage[{i}].{key} missing")
        guide = str(row.get("guideline") or "")
        if guide and guide not in {str(x) for x in guidelines}:
            bad.append(f"guideline_coverage[{i}] guideline not cited in code_guidelines: {guide}")
        applies = str(row.get("applies_to") or "")
        if applies and applies not in {str(x) for x in (item.get("affected_files") or [])}:
            bad.append(f"guideline_coverage[{i}].applies_to not in affected_files: {applies}")
        ev = str(row.get("evidence") or "")
        if ev and not (ROOT / ev).exists():
            bad.append(f"guideline_coverage[{i}].evidence not found: {ev}")
        check = str(row.get("check") or "")
        if check and not any(check.startswith(p) for p in (gcfg.get("allowed_check_prefixes") or [])):
            bad.append(f"guideline_coverage[{i}].check has unsupported command: {check}")
    covered_guides = {str(r.get("guideline") or "") for r in gcov if isinstance(r, dict)}
    for rel in sorted(required_guides - covered_guides):
        bad.append(f"guideline_coverage missing evidence for guide: {rel}")
    scope = pack.get("review_scope") or {}
    if not isinstance(scope, dict):
        bad.append("design_pack.review_scope must be an object")
    else:
        for key in ("ac_ids", "components", "files", "exclude"):
            if not scope.get(key):
                bad.append(f"review_scope.{key} missing")
        ac_ids = {str(x) for x in (scope.get("ac_ids") or [])}
        valid_ac = {f"AC-{i}" for i in range(1, len(acs) + 1)}
        for ac in sorted(ac_ids - valid_ac):
            bad.append(f"review_scope.unknown AC: {ac}")
        affected = {str(x) for x in (item.get("affected_files") or [])}
        for fpath in scope.get("files") or []:
            if str(fpath) not in affected:
                bad.append(f"review_scope file not in affected_files: {fpath}")
    for key in cfg.get("required_item_fields") or []:
        if not item.get(key):
            bad.append(f"item.{key} missing")
    brief = item.get("brief") or {}
    if not isinstance(brief, dict):
        bad.append("item.brief must be an object")
    else:
        for key in cfg.get("required_brief_fields") or []:
            if not brief.get(key):
                bad.append(f"item.brief.{key} missing")
    review = item.get("review") or pack.get("review") or {}
    impact = review.get("impact_review") if isinstance(review, dict) else None
    if not isinstance(impact, list) or not impact:
        bad.append("review.impact_review missing")
        impact = []
    for i, row in enumerate(impact, 1):
        if not isinstance(row, dict):
            bad.append(f"review.impact_review[{i}] must be an object")
            continue
        for key in cfg.get("required_impact_fields") or []:
            if not row.get(key):
                bad.append(f"review.impact_review[{i}].{key} missing")
    risks = item.get("risks") or []
    if not risks:
        bad.append("item.risks missing")
    acs = item.get("acceptance_criteria") or []
    if not acs:
        bad.append("acceptance_criteria missing")
    if len(acs) > int(cfg.get("max_acs_per_item") or 5):
        bad.append("too many ACs for one capability; split the item")
    tokens = [str(x).lower() for x in (cfg.get("placeholder_tokens") or [])]
    for s in _iter_strings(pack):
        if any(_token_in(s, t) for t in tokens):
            bad.append(f"placeholder value in design_pack: {s!r}")
    coverage = pack.get("coverage") or []
    if not isinstance(coverage, list) or not coverage:
        bad.append("design_pack.coverage missing")
        coverage = []
    by_ac = {str(c.get("ac")): c for c in coverage if isinstance(c, dict)}
    for i, _ in enumerate(acs, 1):
        if f"AC-{i}" not in by_ac:
            bad.append(f"coverage missing AC-{i}")
    entrypoints = set()
    for ac, row in by_ac.items():
        if not isinstance(row, dict):
            bad.append(f"coverage {ac} is not an object")
            continue
        for key in cfg.get("required_coverage") or []:
            if not row.get(key):
                bad.append(f"coverage {ac}.{key} missing")
        if row.get("entrypoint") and row.get("runtime_capability", True):
            entrypoints.add(str(row["entrypoint"]))
        for test in row.get("tests") or []:
            if not _test_exists(str(test)):
                bad.append(f"coverage {ac} test not found: {test}")
        for ev in row.get("evidence") or []:
            if not _evidence_exists(str(ev)):
                bad.append(f"coverage {ac} evidence not found: {ev}")
    if len(entrypoints) > int(cfg.get("max_runtime_capabilities") or 1):
        bad.append("more than one runtime entrypoint; split the item")
    rc = pack.get("runtime_contract") or {}
    for key in ("trigger", "entrypoint", "call_sites", "adapter", "contract", "failure_behavior", "observable_result"):
        if not rc.get(key):
            bad.append(f"runtime_contract.{key} missing")
    proof = pack.get("proof_plan") or {}
    for key in ("failing_test", "red_evidence", "green_evidence"):
        if not proof.get(key):
            bad.append(f"proof_plan.{key} missing")
    if not pack.get("non_goals"):
        bad.append("non_goals missing")
    if not pack.get("stop_conditions"):
        bad.append("stop_conditions missing")
    for mode in ("design", "diff"):
        for sig, d in ((item.get("review_dispositions") or {}).get(mode) or {}).items():
            if str((d or {}).get("status") or "").upper() == "ACTIONED":
                note = str((d or {}).get("note") or "")
                if not EVIDENCE_REF.search(note):
                    bad.append(f"ACTIONED without evidence reference: {mode}/{sig}")
    return sorted(set(bad))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Design/delivery contract check")
    ap.add_argument("--item", required=True)
    a = ap.parse_args(argv)
    bad = problems(a.item)
    if bad:
        print(f"design-contract: FAIL ({len(bad)})")
        for p in bad:
            print(f"  - {p}")
        return 1
    print("design-contract: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
