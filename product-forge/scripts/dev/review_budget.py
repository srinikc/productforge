"""One 1.5 + one 2.5 per item/mode (BI-PF-1485), unless HIL approves a material change."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT / "config" / "review-budget.json"
REVIEWS = ROOT / "engineering" / "reviews"
for p in (str(ROOT), str(ROOT / "scripts" / "dev")):
    if p not in sys.path:
        sys.path.insert(0, p)


def config() -> dict:
    try:
        return json.loads(CFG.read_text(encoding="utf-8-sig"))
    except Exception as e:
        raise RuntimeError(f"cannot read review-budget config: {e}")


def _evidence(item_id: str, mode: str) -> list[dict]:
    out = []
    for p in REVIEWS.glob(f"{item_id}-*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if str(d.get("mode") or "") == mode:
            out.append(d)
    return out


def _dt(value) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _material_ok(item: dict, mode: str, rows: list[dict]) -> bool:
    latest = max((_dt(d.get("at")) for d in rows if _dt(d.get("at"))), default=None)
    if latest is None:
        return False
    for d in item.get("decisions") or []:
        if str(d.get("decision") or "").upper() != "MATERIAL_CHANGE":
            continue
        if d.get("hil_confirmed") is not True or str(d.get("mode") or "") != mode:
            continue
        try:
            at = _dt(d.get("at"))
        except ValueError:
            continue
        if at is not None and at >= latest:
            return True
    return False


def _dt_safe(value):
    try:
        return _dt(value)
    except ValueError:
        return None


def problems(item: dict, only_mode: str = "") -> list[str]:
    c = config()
    iid = str(item.get("id") or "")
    if iid in (c.get("grandfather") or []):
        return []
    cutoff = str(c.get("enforce_from") or "")
    max_n = int(c.get("max_reviews_per_mode") or 1)
    bad = []
    for mode in ("design", "diff"):
        if only_mode and mode != only_mode:
            continue
        if (mode == "design" and c.get("freeze_design_after_gate1", True)
                and any(int(d.get("gate") or 0) == 1 for d in (item.get("decisions") or []))):
            continue
        if (mode == "diff" and c.get("freeze_diff_after_gate2", True)
                and any(int(d.get("gate") or 0) == 2 for d in (item.get("decisions") or []))):
            continue
        try:
            cutoff_dt = _dt(cutoff)
        except ValueError:
            bad.append(f"{mode}: REVIEW_BUDGET_CONFIG invalid enforce_from")
            continue
        if cutoff_dt is None:
            bad.append(f"{mode}: REVIEW_BUDGET_CONFIG missing enforce_from")
            continue
        rows = []
        invalid = 0
        for d in _evidence(iid, mode):
            try:
                at = _dt(d.get("at"))
            except ValueError:
                bad.append(f"{mode}: REVIEW_EVIDENCE_INVALID malformed review at")
                invalid += 1
                continue
            if at is None:
                bad.append(f"{mode}: REVIEW_EVIDENCE_INVALID missing review at")
                invalid += 1
                continue
            if at >= cutoff_dt and d.get("parsed_ok", True):
                rows.append(d)
        if len(rows) + invalid >= max_n and not (c.get("allow_hil_material_change") and _material_ok(item, mode, rows)):
            mats = [d for d in (item.get("decisions") or [])
                    if str(d.get("decision") or "").upper() == "MATERIAL_CHANGE"]
            if not mats:
                code = "MATERIAL_APPROVAL_MISSING"
            elif any(str(d.get("at") or "") and _dt_safe(d.get("at")) is None for d in mats):
                code = "MATERIAL_APPROVAL_INVALID"
            else:
                expiry = _dt(c.get("material_expiry"))
                code = ("MATERIAL_APPROVAL_EXPIRED" if expiry and datetime.now(timezone.utc) > expiry
                        else "MATERIAL_APPROVAL_ORDER")
            bad.append(f"{mode}: {len(rows)} reviews (budget {max_n}); {code}: material change needs HIL MATERIAL_CHANGE")
    return bad


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Review budget")
    ap.add_argument("--item", default="")
    ap.add_argument("--all-changed", action="store_true")
    ap.add_argument("--base", default="")
    a = ap.parse_args(argv)
    from core import backlog
    ids = []
    if a.all_changed:
        try:
            from gate2_completion_check import transitions
            ids = transitions(a.base)
        except Exception as e:
            print(f"review-budget: FAIL - cannot compute changed items: {e}")
            return 1
    elif a.item:
        ids = [a.item]
    else:
        print("review-budget: --item or --all-changed is required")
        return 2
    bad = []
    for iid in ids:
        item = backlog.get_epic("product_forge", None, iid) or {}
        bad += [f"{iid}: {p}" for p in problems(item)]
    print("review-budget: " + ("OK" if not bad else "FAIL"))
    for x in bad:
        print("  - " + x)
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
