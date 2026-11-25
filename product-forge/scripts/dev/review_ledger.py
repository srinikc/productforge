"""Append-only review ledger; filesystem deletion cannot reset the full-review budget."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "scripts" / "dev")):
    if str(p) not in sys.path:
        sys.path.insert(0, p)
from core import backlog  # noqa: E402
import design_contract_check as dcc  # noqa: E402

FULL = "full_candidate"
DELTA = "delta"


def _item(item_id: str, scope: str, project: str | None) -> dict:
    return backlog.get_epic(scope, project, item_id) or {}


def _entry_scope(entry: dict) -> str:
    scope = str(entry.get("review_scope") or "").strip()
    if scope:
        return scope
    # Backfill-compatible inference from the evidence file for older ledger rows.
    ev = str(entry.get("evidence") or "").strip()
    if ev:
        try:
            d = json.loads((ROOT / "engineering" / "reviews" / ev).read_text(encoding="utf-8"))
            return str(d.get("review_scope") or FULL)
        except Exception:
            pass
    return FULL


def entries(item: dict, mode: str = "") -> list[dict]:
    out = item.get("review_ledger") or []
    return [e for e in out if not mode or str(e.get("mode") or "") == mode]


def full_entries(item: dict, mode: str = "") -> list[dict]:
    return [e for e in entries(item, mode) if _entry_scope(e) != DELTA]


def delta_entries(item: dict, mode: str = "") -> list[dict]:
    return [e for e in entries(item, mode) if _entry_scope(e) == DELTA]


def record(item_id: str, entry: dict, scope: str = "product_forge", project: str | None = None) -> dict:
    it = _item(item_id, scope, project)
    if not it:
        raise RuntimeError(f"item not found: {item_id}")
    ledger = list(it.get("review_ledger") or [])
    sha = str(entry.get("review_sha") or "")
    if sha and any(str(x.get("review_sha") or "") == sha for x in ledger):
        return it
    e = dict(entry)
    e.setdefault("review_scope", FULL)
    e.setdefault("at", datetime.now(timezone.utc).isoformat())
    ledger.append(e)
    return backlog.update(scope, project, item_id, review_ledger=ledger)


def _material_ok(item: dict, mode: str) -> bool:
    latest = max((str(e.get("at") or "") for e in full_entries(item, mode)), default="")
    for d in item.get("decisions") or []:
        if str(d.get("decision") or "").upper() != "MATERIAL_CHANGE":
            continue
        if d.get("hil_confirmed") is True and str(d.get("mode") or "") == mode and str(d.get("at") or "") >= latest:
            return True
    return False


def chain_problems(item: dict, mode: str = "diff") -> list[str]:
    """A delta review must be anchored to a prior full review (or prior delta)."""
    deltas = delta_entries(item, mode)
    if not deltas:
        return []
    full = full_entries(item, mode)
    if not full:
        return [f"{mode}: FULL_REVIEW_MISSING"]
    reviewed = {str(e.get("head_sha") or "") for e in full if e.get("head_sha")}
    bad = []
    for e in deltas:
        base = str(e.get("base_sha") or "")
        head = str(e.get("head_sha") or "")
        if not base or not head:
            bad.append(f"{mode}: delta review missing base/head")
        elif base not in reviewed:
            bad.append(f"{mode}: delta base {base[:12]} is not a reviewed head")
        else:
            reviewed.add(head)
    return bad


def problems(item: dict, mode: str, max_reviews: int = 1) -> list[str]:
    if dcc.enforced(item, dcc._cfg()) and not (item.get("review_ledger") or []):
        return [f"{mode}: REVIEW_LEDGER_MISSING"]
    full = full_entries(item, mode)
    if len(full) <= max_reviews:
        return []
    if _material_ok(item, mode):
        return chain_problems(item, mode)
    return [f"{mode}: {len(full)} full reviews (budget {max_reviews}); MATERIAL_APPROVAL_MISSING"]


def _backfill(scope: str, project: str | None) -> int:
    n = 0
    ev = ROOT / "engineering" / "reviews"
    for p in ev.glob("*.json") if ev.is_dir() else []:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        iid, mode, sha = str(d.get("item") or ""), str(d.get("mode") or ""), str(d.get("sha") or "")
        if not iid or not mode or not sha:
            continue
        it = _item(iid, scope, project)
        if not it:
            continue
        if any(str(x.get("review_sha") or "") == sha for x in entries(it, mode)):
            continue
        try:
            record(iid, {"mode": mode, "candidate_sha": d.get("head_sha") or "", "review_sha": sha,
                         "model": d.get("model") or "", "at": d.get("at") or "",
                         "review_scope": d.get("review_scope") or FULL,
                         "base_sha": d.get("base_sha") or "", "head_sha": d.get("head_sha") or "",
                         "findings": d.get("findings") or {}, "source": p.name}, scope, project)
            n += 1
        except Exception:
            continue
    return n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Append-only review ledger")
    ap.add_argument("--item", required=True)
    ap.add_argument("--mode", choices=("design", "diff"), default="")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--backfill", action="store_true")
    ap.add_argument("--scope", default="product_forge")
    ap.add_argument("--project", default=None)
    a = ap.parse_args(argv)
    if a.backfill:
        print(f"review-ledger: backfilled {_backfill(a.scope, a.project)} review(s)")
        return 0
    it = _item(a.item, a.scope, a.project)
    if not it:
        print(f"review-ledger: FAIL - item not found: {a.item}")
        return 2
    modes = [a.mode] if a.mode else ["design", "diff"]
    bad = []
    for mode in modes:
        bad += problems(it, mode)
        bad += chain_problems(it, mode) if mode == "diff" else []
    if bad:
        print("review-ledger: FAIL")
        for p in bad:
            print(f"  - {p}")
        return 1
    print("review-ledger: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
