"""Provider health tracking — availability / rate-limits / errors / latency (BI-PF-0279).

Single writer of ``data/provider-health.json``. Records a rolling, bounded window per provider from real
LLM call outcomes and derives a state (healthy|degraded|unavailable) + score (0..1). Fail-open: a provider
with no data is neutral, so routing is unchanged when nothing is known. See docs/PROVIDER-HEALTH-DESIGN.md.
"""

import json
import os
import threading
from datetime import datetime, timezone
from typing import Dict, Optional

try:
    from core.paths import ROOT as _ROOT
except ImportError:  # script execution
    import sys as _sys
    _d = os.path.abspath(__file__)
    for _ in range(3):
        _d = os.path.dirname(_d)
        if os.path.isfile(os.path.join(_d, "core", "paths.py")):
            _sys.path.insert(0, _d)
            break
    from core.paths import ROOT as _ROOT

STORE = os.path.join(str(_ROOT), "data", "provider-health." + "json")
_LOCK = threading.Lock()

# tuning (bounded, deterministic)
_WINDOW = 20          # rolling window size
_COOLDOWN_SECONDS = 300
_DEGRADED_SCORE = 0.6
_UNAVAILABLE_SCORE = 0.3


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ts_epoch(s: str) -> float:
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def _blank() -> Dict:
    return {"success": 0, "fail": 0, "rate_limited": 0, "errors_by_status": {},
            "latency_ms": 0.0, "last_error": "", "last_seen": "", "cooldown_until": 0.0,
            "state": "unknown", "score": 0.5, "kind": ""}


def _load() -> Dict:
    try:
        with open(STORE, encoding="utf-8-sig") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _save(data: Dict) -> None:
    try:
        os.makedirs(os.path.dirname(STORE), exist_ok=True)
        tmp = STORE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, STORE)
    except Exception:
        pass


def _derive(p: Dict) -> None:
    """Recompute state + score from the bounded window (recency-weighted)."""
    total = p.get("success", 0) + p.get("fail", 0)
    if total == 0:
        p["state"] = "unknown"
        p["score"] = 0.5
        return
    base = p.get("success", 0) / float(total)
    rl = p.get("rate_limited", 0)
    penalty = min(0.4, 0.1 * rl)
    score = max(0.0, min(1.0, base - penalty))
    p["score"] = round(score, 3)
    now = datetime.now(timezone.utc).timestamp()
    if p.get("cooldown_until", 0) > now:
        p["state"] = "unavailable" if score < _UNAVAILABLE_SCORE else "degraded"
    elif score >= _DEGRADED_SCORE:
        p["state"] = "healthy"
    elif score >= _UNAVAILABLE_SCORE:
        p["state"] = "degraded"
    else:
        p["state"] = "unavailable"


def record(provider: str, *, ok: bool, status: int = 0, latency_ms: float = 0,
           error: str = "", kind: str = "") -> Dict:
    """Record one call outcome for a provider (best-effort, never raises). Single writer."""
    try:
        provider = str(provider or "").strip()
        if not provider:
            return _blank()
        with _LOCK:
            data = _load()
            p = dict(data.get(provider) or _blank())
            if kind:
                p["kind"] = kind
            if ok:
                p["success"] = min(_WINDOW, p.get("success", 0) + 1)
            else:
                p["fail"] = min(_WINDOW, p.get("fail", 0) + 1)
                if status == 429:
                    p["rate_limited"] = min(_WINDOW, p.get("rate_limited", 0) + 1)
                    p["cooldown_until"] = max(
                        p.get("cooldown_until", 0.0),
                        datetime.now(timezone.utc).timestamp() + _COOLDOWN_SECONDS)
                if status:
                    eb = dict(p.get("errors_by_status") or {})
                    eb[str(status)] = int(eb.get(str(status), 0)) + 1
                    p["errors_by_status"] = eb
                if error:
                    p["last_error"] = str(error)[:300]
            if latency_ms:
                prev = float(p.get("latency_ms") or 0.0)
                p["latency_ms"] = round((prev * 0.7) + (float(latency_ms) * 0.3), 1) if prev else round(float(latency_ms), 1)
            p["last_seen"] = _now()
            _derive(p)
            data[provider] = p
            _save(data)
            return p
    except Exception:
        return _blank()


def state(provider: str) -> str:
    return str((_load().get(str(provider)) or {}).get("state") or "unknown")


def score(provider: str) -> float:
    p = _load().get(str(provider)) or {}
    if not p:
        return 0.5  # fail-open neutral
    return float(p.get("score", 0.5))


def cooldown(provider: str) -> bool:
    p = _load().get(str(provider)) or {}
    return bool(p.get("cooldown_until", 0) > datetime.now(timezone.utc).timestamp())


def snapshot() -> Dict:
    return _load()


def reset(provider: Optional[str] = None) -> Dict:
    """Clear health for one provider or all (operator use)."""
    with _LOCK:
        if provider:
            data = _load()
            data.pop(str(provider), None)
        else:
            data = {}
        _save(data)
        return data
