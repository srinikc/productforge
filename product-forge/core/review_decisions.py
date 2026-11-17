"""Validation helpers for review decisions (BI-PF-1540).

Kept in core so rollback of the HTTP route can retain validation/audit tests.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def latest_review_sha(item_id: str, mode: str) -> str:
    try:
        from core.paths import ROOT
    except Exception:
        return ""
    best = ("", "")
    for p in (ROOT / "engineering" / "reviews").glob(f"{item_id}-*.json"):
        if "-prev-" in p.name:
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if str(d.get("mode") or "") != mode:
            continue
        at = str(d.get("at") or "")
        if at >= best[0]:
            best = (at, str(d.get("sha") or ""))
    return best[1]


def material_change_errors(item_id: str, body: dict[str, Any]) -> list[str]:
    decision = str(body.get("decision") or "").strip().upper()
    mode = str(body.get("mode") or "").strip()
    reason = str(body.get("reason") or "").strip()
    by = str(body.get("by") or "").strip()
    bad = []
    if decision != "MATERIAL_CHANGE":
        bad.append("decision must be MATERIAL_CHANGE")
    if mode not in ("design", "diff"):
        bad.append("mode must be design or diff")
    if len(reason) < 20:
        bad.append("reason must be concrete (>=20 chars)")
    if body.get("hil_confirmed") is not True:
        bad.append("hil_confirmed=true required")
    actor = ""
    try:
        from core.paths import ROOT
        actor = str(json.loads((ROOT / "config" / "review-material-change.json").read_text(encoding="utf-8")).get("hil_actor") or "")
    except Exception:
        bad.append("HIL actor config unreadable")
    if not actor or by != actor:
        bad.append("by must match the configured HIL actor bound to the authenticated token")
    latest = latest_review_sha(item_id, mode)
    if not latest:
        bad.append(f"no {mode} review evidence for item")
    elif latest not in reason:
        bad.append(f"reason must cite latest review sha {latest}")
    return bad
