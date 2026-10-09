"""DOGFOOD Phase 3 (BI-PF-0460): scheduled dogfood cadence (API-first; no daemon).

Single writer of ``config/dogfood-schedule.json``. A tick enqueues DUE dogfood runs (through the Phase 1
``core.dogfood_run.start`` -> ``run_entry``) and is idempotent per period (``last_run``). Intended trigger: an
operator/cron calls ``POST /dogfood/schedule/tick``. No in-repo daemon; framework-agnostic; no dashboard coupling.
"""
import json
import os
from datetime import datetime, timedelta
from typing import Any, Optional

from core.paths import ROOT

CONFIG = os.path.join(str(ROOT), "config", "dogfood-schedule.json")
_DEFAULT: dict[str, Any] = {"_doc": "Dogfood schedule (BI-PF-0460). Owner: core/dogfood_schedule.py.",
                            "version": 1, "entries": []}


def load() -> dict:
    try:
        with open(CONFIG, encoding="utf-8-sig") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else dict(_DEFAULT)
    except Exception:
        return dict(_DEFAULT)


def save(data: dict) -> dict:
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    tmp = CONFIG + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, CONFIG)
    return data


def _parse(ts: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(ts))
    except Exception:
        return None


def due(now: Optional[datetime] = None, data: Optional[dict] = None) -> list[dict]:
    """Entries whose cadence has elapsed (enabled + last_run older than interval_hours)."""
    now = now or datetime.now()
    data = data if data is not None else load()
    out = []
    for e in (data.get("entries") or []):
        if not e.get("enabled"):
            continue
        last = _parse(e.get("last_run") or "")
        try:
            interval = float(e.get("interval_hours") or 24)
        except (TypeError, ValueError):
            interval = 24
        if last is None or now - last >= timedelta(hours=interval):
            out.append(e)
    return out


def run_due(products_dir: Optional[str] = None) -> dict:
    """Enqueue every DUE entry via the Phase 1 dogfood runner; update last_run (idempotent per period)."""
    from core import dogfood_run
    data = load()
    now = datetime.now()
    started: list[dict] = []
    due_entries = due(now, data)
    for e in due_entries:
        project = str(e.get("project") or "").strip()
        if not project:
            continue
        try:
            res = dogfood_run.start(str(e.get("idea") or ""), project,
                                    tier=str(e.get("tier") or "kctier"),
                                    auto=bool(e.get("auto", True)),
                                    caps=e.get("caps") or {}, target=str(e.get("target") or ""),
                                    products_dir=products_dir)
            started.append({"project": project, "run_id": res.get("run_id")})
            e["last_run"] = now.isoformat()
        except Exception as ex:  # noqa: BLE001
            started.append({"project": project, "error": type(ex).__name__})
    if started:
        save(data)
    return {"due": len(due_entries), "started": started}


def tick() -> dict:
    """Alias for ``run_due`` (the API/CLI trigger)."""
    return run_due()
