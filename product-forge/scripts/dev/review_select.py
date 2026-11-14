"""Deterministic review-evidence selection shared by CI gate tools."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

CLOSED_STATUSES = {"completed", "closed", "done", "delivered", "duplicate",
                   "rejected", "wontfix", "archived"}


def _ts(value: str) -> datetime:
    s = str(value or "").strip()
    if not s:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def latest_review(reviews_dir: Path, item_id: str, mode: str = "diff",
                  prefer_sha: str = "", meta: dict | None = None) -> dict:
    """Newest review by recorded `at`; mtime is only a legacy tie-breaker."""
    best: dict = {}
    best_key: tuple | None = None
    used_fallback = False
    for p in Path(reviews_dir).glob(f"{item_id}-*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if (d.get("mode") or "diff") != mode:
            continue
        if prefer_sha and str(d.get("sha") or "") == prefer_sha:
            if meta is not None:
                meta["mtime_fallback"] = False
            return d
        key = (_ts(d.get("at")), p.stat().st_mtime)
        if best_key is None or key > best_key:
            best, best_key = d, key
            used_fallback = not bool(str(d.get("at") or "").strip())
    if meta is not None:
        meta["mtime_fallback"] = used_fallback
    return best


def is_closed(status) -> bool:
    from core import backlog
    value = str(status or "").lower()
    return value in CLOSED_STATUSES or backlog.section({"status": value}) == "done"
