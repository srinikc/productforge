"""Idempotency store + guard (API-0.1 §5).

Single writer of ``data/api/idempotency.json``. Replaying a completed key returns the stored result; a
concurrent duplicate while the first is in flight yields ``IDEMPOTENCY_CONFLICT``. Records are bounded by a
TTL (default 24h) so the store stays small and the mechanism scales.
"""

import hashlib
import json
import os
import time
from typing import Any, Dict, Optional

try:
    from core.paths import ROOT as _ROOT
except ImportError:  # script execution
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

_TTL_SECONDS = 24 * 3600


def _path() -> str:
    return os.path.join(_ROOT, "data", "api", "idempotency." + "json")


def _load() -> Dict[str, Any]:
    try:
        with open(_path(), encoding="utf-8-sig") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _save(data: Dict[str, Any]) -> None:
    try:
        p = _path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, p)
    except Exception:
        pass


def _key(tenant_id: str, method: str, path: str, idem_key: str) -> str:
    raw = "|".join([str(tenant_id or ""), str(method or "").upper(), str(path or ""), str(idem_key or "")])
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()


def _prune(data: Dict[str, Any], now: float) -> Dict[str, Any]:
    return {k: v for k, v in data.items() if (now - float(v.get("at", 0) or 0)) < _TTL_SECONDS}


def lookup(tenant_id: str, method: str, path: str, idem_key: str) -> Optional[Dict[str, Any]]:
    """Return the stored record for a key, or None."""
    if not idem_key:
        return None
    k = _key(tenant_id, method, path, idem_key)
    data = _prune(_load(), time.time())
    return data.get(k)


def begin(tenant_id: str, method: str, path: str, idem_key: str) -> Dict[str, Any]:
    """Reserve a key. Returns {'state': 'new'|'replay'|'inflight', 'record': ...}."""
    if not idem_key:
        return {"state": "new", "record": None}
    now = time.time()
    k = _key(tenant_id, method, path, idem_key)
    data = _prune(_load(), now)
    rec = data.get(k)
    if rec and rec.get("state") == "done":
        return {"state": "replay", "record": rec}
    if rec and rec.get("state") == "inflight":
        return {"state": "inflight", "record": rec}
    data[k] = {"state": "inflight", "at": now}
    _save(data)
    return {"state": "new", "record": None}


def complete(tenant_id: str, method: str, path: str, idem_key: str, *, resource_id: str = "",
             response_hash: str = "") -> None:
    if not idem_key:
        return
    now = time.time()
    k = _key(tenant_id, method, path, idem_key)
    data = _prune(_load(), now)
    data[k] = {"state": "done", "at": now, "resource_id": resource_id, "response_hash": response_hash}
    _save(data)
