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
REVIEWS = ROOT / "engineering" / "reviews"


def _severity_map(item: dict) -> dict:
    """Map finding signature -> severity from committed review evidence."""
    from review_sig import digest
    out = {}
    iid = str(item.get("id") or "")
    for p in REVIEWS.glob(f"{iid}-*.json") if iid else []:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for sev in ("BLOCKER", "MAJOR", "MINOR", "NIT"):
            for text in (d.get("findings") or {}).get(sev) or []:
                if str(text).strip().lower() == "none":
                    continue
                out["sig:" + digest(text)] = sev
    return out


def cfg() -> dict:
    try:
        return json.loads(CFG.read_text(encoding="utf-8-sig"))
    except Exception as e:
        raise RuntimeError(f"cannot read review-dispositions config: {e}")


def _rows(item: dict, mode: str) -> dict:
    return ((item.get("review_dispositions") or {}).get(mode) or {})


def _approvals(item: dict, mode: str) -> list[dict]:
    c = cfg()
    out = []
    for d in item.get("decisions") or []:
        if str(d.get("decision") or "").upper() != str(c["approval_decision"]).upper():
            continue
        if d.get("hil_confirmed") is not True or not str(d.get("by") or "").startswith("hil:"):
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
    sev = _severity_map(item)
    bad = []
    exceptions = accepted + deferred
    max_exc = int(c.get("max_exceptions_per_mode") or 2)
    if len(exceptions) > max_exc:
        bad.append(f"{mode}: {len(exceptions)} HIL exceptions exceeds max {max_exc}")
    for k in exceptions:
        key = k if str(k).startswith("sig:") else "sig:" + str(k).split(":")[-1]
        severity = str(sev.get(key) or sev.get(k) or (rows.get(k) or {}).get("severity") or "MAJOR").upper()
        if severity == "BLOCKER":
            bad.append(f"{mode}/{k}: BLOCKER cannot be ACCEPTED/DEFERRED; fix it")
        if k in accepted and not c.get("accepted_allowed", True):
            bad.append(f"{mode}/{k}: ACCEPTED is not allowed")
    needs = exceptions if c.get("require_hil_approval_for_exceptions", True) else []
    approved = _approved_sigs(item, mode)
    missing = [k for k in needs if k not in approved]
    if missing:
        bad.append(f"{mode}: {len(missing)} ACCEPTED/DEFERRED without HIL DISPOSITION_APPROVAL ({', '.join(missing[:4])})")
    for k in deferred:
        note = str((rows.get(k) or {}).get("note") or "")
        found = [m.group(0) for m in FOLLOW_UP.finditer(note) if m.group(0) != item.get("id")]
        if not found:
            bad.append(f"{mode}/{k}: DEFERRED without an external backlog id")
        elif backlog_get:
            try:
                if not backlog_get(found[0]):
                    bad.append(f"{mode}/{k}: follow-up {found[0]} does not exist")
            except Exception as e:
                bad.append(f"{mode}/{k}: cannot verify follow-up {found[0]}: {e}")
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
