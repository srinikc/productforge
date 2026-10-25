"""Disposition policy (BI-PF-1484): cap ACCEPTED and require HIL approval for ACCEPTED/DEFERRED."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT / "config" / "review-dispositions.json"
FOLLOW_UP = re.compile(r"BI-(?:[A-Za-z0-9]+-)?\d+")
STATUSES = ("ACCEPTED", "DEFERRED")


def cfg() -> dict:
    try:
        return json.loads(CFG.read_text(encoding="utf-8-sig"))
    except Exception:
        return {"max_accepted_per_mode": 2, "require_hil_approval_for_accepted": True,
                "require_hil_approval_for_deferred": True,
                "approval_decision": "DISPOSITION_APPROVAL", "approval_scope": "disposition_approval"}


def _rows(item: dict, mode: str) -> dict:
    return ((item.get("review_dispositions") or {}).get(mode) or {})


def _approvals(item: dict, mode: str) -> list[dict]:
    c = cfg()
    out = []
    for d in item.get("decisions") or []:
        if str(d.get("decision") or "").upper() != str(c["approval_decision"]).upper():
            continue
        if d.get("hil_confirmed") is not True:
            continue
        if str(d.get("scope") or "") != c["approval_scope"]:
            continue
        if str(d.get("mode") or "") == mode:
            out.append(d)
    return out


def _approved_sigs(item: dict, mode: str) -> set:
    out = set()
    for d in _approvals(item, mode):
        out.update(str(x) for x in (d.get("sigs") or []))
    return out


def problems(item: dict, mode: str, backlog_get=None) -> list[str]:
    c = cfg()
    rows = _rows(item, mode)
    accepted = [k for k, v in rows.items() if str((v or {}).get("status") or "").upper() == "ACCEPTED"]
    deferred = [k for k, v in rows.items() if str((v or {}).get("status") or "").upper() == "DEFERRED"]
    bad = []
    if len(accepted) > int(c["max_accepted_per_mode"]):
        bad.append(f"{mode}: {len(accepted)} ACCEPTED exceeds cap {c['max_accepted_per_mode']}")
    needs = []
    if accepted and c.get("require_hil_approval_for_accepted"):
        needs += accepted
    if deferred and c.get("require_hil_approval_for_deferred"):
        needs += deferred
    approved = _approved_sigs(item, mode)
    missing = [k for k in needs if k not in approved]
    if missing:
        bad.append(f"{mode}: {len(missing)} ACCEPTED/DEFERRED without HIL DISPOSITION_APPROVAL ({', '.join(missing[:4])})")
    for k in deferred:
        note = str((rows.get(k) or {}).get("note") or "")
        m = FOLLOW_UP.search(note)
        if not m:
            bad.append(f"{mode}/{k}: DEFERRED without backlog id")
        elif backlog_get:
            try:
                if not backlog_get(m.group(0)):
                    bad.append(f"{mode}/{k}: follow-up {m.group(0)} does not exist")
            except Exception:
                pass
    return bad


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--item", required=True)
    ap.add_argument("--mode", choices=("design", "diff"), required=True)
    a = ap.parse_args()
    sys.path.insert(0, str(ROOT))
    from core import backlog
    it = backlog.get_epic("product_forge", None, a.item) or {}
    b = problems(it, a.mode, lambda i: backlog.get_epic("product_forge", None, i))
    print("disposition-policy: " + ("OK" if not b else "FAIL"))
    for x in b:
        print("  - " + x)
    raise SystemExit(1 if b else 0)
