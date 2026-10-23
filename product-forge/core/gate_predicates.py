"""Shared gate predicates for the review lifecycle (BI-PF-1469).

One source of truth used by precheck/CI gates AND core.backlog.set_status so local/CI cannot diverge:
  * findings_digest(view): sha256 over sig|status of the current dispositions;
  * approval(item, gate, evidence_sha, view, allow_missing_view=False): approval is valid only when it names
    the current evidence sha and (when evidence exists) the current findings digest;
  * baseline_state(iid): ACTIVE | EXPIRED | UNKNOWN | NONE (fail-closed on unknown/expired).
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "config" / "gate-baseline.json"
APPROVED = {"APPROVE", "APPROVE_WITH_ATTENTION"}
MAX_BASELINE_DAYS = 90
MAX_BASELINE_ENTRIES = 10


def load_baseline(path: Path | None = None) -> dict:
    try:
        d = json.loads((path or BASELINE).read_text(encoding="utf-8"))
    except Exception:
        return {}
    items = d.get("items") if isinstance(d, dict) else {}
    return items if isinstance(items, dict) else {}


def baseline_state(iid: str, today: date | None = None) -> str:
    entry = load_baseline().get(iid)
    if not isinstance(entry, dict):
        return "NONE"
    try:
        until = date.fromisoformat(str(entry.get("until") or ""))
    except Exception:
        return "UNKNOWN"
    today = today or datetime.now(timezone.utc).date()
    return "EXPIRED" if today > until else "ACTIVE"


def baseline_problems() -> list[str]:
    """Governance: bounded, dated, owned entries (expired entries are gate failures, not silent allows)."""
    bad: list[str] = []
    items = load_baseline()
    if len(items) > MAX_BASELINE_ENTRIES:
        bad.append(f"baseline has {len(items)} entries (max {MAX_BASELINE_ENTRIES})")
    for iid, e in items.items():
        if not isinstance(e, dict):
            bad.append(f"{iid}: baseline entry is not an object")
            continue
        if not str(e.get("reason") or "").strip():
            bad.append(f"{iid}: baseline entry has no reason")
        if not str(e.get("owner_item") or "").strip():
            bad.append(f"{iid}: baseline entry has no owner_item")
        try:
            until = date.fromisoformat(str(e.get("until") or ""))
        except Exception:
            bad.append(f"{iid}: baseline until is not an ISO date")
            continue
        span = (until - datetime.now(timezone.utc).date()).days
        if span > MAX_BASELINE_DAYS:
            bad.append(f"{iid}: baseline until is more than {MAX_BASELINE_DAYS} days out")
    return bad


def findings_digest(view: dict | None) -> str:
    dis = (view or {}).get("dispositions") or {}
    rows = sorted(f"{k}|{str((v or {}).get('status') or 'PENDING').upper()}" for k, v in dis.items())
    return hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()[:12]


def _evidence_sha(view: dict | None) -> str:
    return str(((view or {}).get("review") or {}).get("sha") or "")


def approval(item: dict, gate: int, evidence_sha: str, view: dict | None,
             allow_missing_view: bool = False) -> tuple[bool, str]:
    if view is None and not allow_missing_view:
        return False, "NO_EVIDENCE"
    if view is not None:
        if not view.get("parsed_ok", True):
            return False, "UNPARSABLE"
        if view.get("blocking"):
            return False, "PENDING_FINDINGS"
    digest = findings_digest(view) if view is not None else ""
    # Append-only invariant: decision seq must be strictly increasing (the journal is the item's decisions[]).
    last_seq = -1
    for d in (item.get("decisions") or []):
        try:
            seq = int(d.get("seq") or 0)
        except Exception:
            seq = 0
        if seq and seq <= last_seq:
            return False, "DECISION_ORDER_INVALID"
        last_seq = max(last_seq, seq)
    for d in reversed((item.get("decisions") or [])):
        try:
            g = int(d.get("gate") or 0)
        except Exception:
            g = 0
        if g != gate or str(d.get("decision") or "").upper() not in APPROVED:
            continue
        if str(d.get("findings_sha") or "") != str(evidence_sha or ""):
            return False, "STALE_APPROVAL"
        if view is not None and str(d.get("findings_digest") or "") != digest:
            return False, "STALE_APPROVAL"
        return True, "OK"
    return False, "NO_GATE_APPROVAL"


def gate2_ready(item: dict, diff_sha: str, diff_view: dict | None,
                allow_missing_view: bool = False) -> tuple[bool, str]:
    return approval(item, 2, diff_sha, diff_view, allow_missing_view=allow_missing_view)
