"""
Capacity governor (portfolio/global tier).

Answers "do we have capacity to start this project?" and enforces limits:
  - max_parallel_projects    : concurrent running projects (slots)
  - max_created_projects     : total registered (queued + defined)
  - max_supervisors          : portfolio instances that may run at once (scale-out)
  - provider_limits/budget   : (data; consumed by model/budget layers)

Config: config/capacity.json. State read from products/ (portfolio registry/state,
per-project locks, pipeline-state.json).
"""
try:
    from core.paths import ROOT as _PF_ROOT
except ImportError:  # executed as a script: seed the repo root on sys.path, then retry
    import os as _pf_os
    import sys as _pf_sys
    _pf_d = _pf_os.path.abspath(__file__)
    for _pf_i in range(3):
        _pf_d = _pf_os.path.dirname(_pf_d)
        if _pf_os.path.isfile(_pf_os.path.join(_pf_d, 'core', 'paths.py')):
            _pf_sys.path.insert(0, _pf_d)
            break
    from core.paths import ROOT as _PF_ROOT

import json
import os
import subprocess
import threading
import time
from collections import deque
from typing import Any, Dict, List, Optional

_REPO = str(_PF_ROOT)
_PRODUCTS = os.path.join(_REPO, "products")
_CFG = os.path.join(_REPO, "config", "capacity.json")
_LOCKS = os.path.join(_PRODUCTS, ".locks")
_REG = os.path.join(_PRODUCTS, "portfolio-registry.json")
_STATE = os.path.join(_PRODUCTS, "portfolio-state.json")


def load() -> Dict[str, Any]:
    try:
        with open(_CFG, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _rj(p, d):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def _pid_alive(pid: int) -> bool:
    if not pid:
        return False
    try:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"],
                             capture_output=True, text=True, timeout=10).stdout
        return str(pid) in out
    except Exception:
        return False


def live_supervisors() -> List[int]:
    """Live portfolio supervisor PIDs (portfolio*.lock files with alive pids)."""
    out = []
    if not os.path.isdir(_LOCKS):
        return out
    for fn in os.listdir(_LOCKS):
        if fn.startswith("portfolio") and fn.endswith(".lock"):
            pid = _rj(os.path.join(_LOCKS, fn), {}).get("pid")
            if _pid_alive(pid):
                out.append(pid)
    return out


def provider_limits(provider: str) -> Dict[str, int]:
    """Declared per-provider caps from config/capacity.json::provider_limits (0 = unlimited)."""
    lim = ((load().get("provider_limits") or {}).get(str(provider) or "") or {})
    return {"rpm": int(lim.get("requests_per_min") or 0), "tpm": int(lim.get("tokens_per_min") or 0)}


_RATE_LOCK = threading.Lock()
_RATE: Dict[str, Dict[str, deque]] = {}  # provider -> {"reqs": deque[ts], "tokens": deque[(ts, n)]}
_RATE_WINDOW = 60.0


def _prune(dq: deque, now: float) -> None:
    while dq and now - dq[0][0] > _RATE_WINDOW:
        dq.popleft()


def rate_wait(provider: str, *, max_wait: float = 30.0) -> float:
    """Seconds to wait before the next request so `provider` stays within its provider_limits.

    **Fail-open**: unknown provider / no limits -> 0; never returns more than `max_wait` (the caller caps
    the actual sleep). This PACES only — it never blocks/aborts an agent.
    """
    lim = provider_limits(provider)
    if not lim["rpm"] and not lim["tpm"]:
        return 0.0
    now = time.time()
    st = _RATE.setdefault(str(provider or ""), {"reqs": deque(), "tokens": deque()})
    with _RATE_LOCK:
        _prune(st["reqs"], now)
        _prune(st["tokens"], now)
        waits = []
        if lim["rpm"] and len(st["reqs"]) >= lim["rpm"]:
            waits.append(_RATE_WINDOW - (now - st["reqs"][0][0]))
        if lim["tpm"]:
            used = sum(n for _, n in st["tokens"])
            if used >= lim["tpm"] and st["tokens"]:
                waits.append(_RATE_WINDOW - (now - st["tokens"][0][0]))
        return max(0.0, min(max(waits) if waits else 0.0, float(max_wait)))


def record_request(provider: str, tokens: int = 0) -> None:
    """Record one request (and optional token usage) for the provider's rolling window."""
    now = time.time()
    st = _RATE.setdefault(str(provider or ""), {"reqs": deque(), "tokens": deque()})
    with _RATE_LOCK:
        _prune(st["reqs"], now)
        _prune(st["tokens"], now)
        st["reqs"].append((now,))
        if tokens:
            st["tokens"].append((now, int(tokens)))


def _running_projects() -> List[str]:
    st = _rj(_STATE, {})
    out = [p for p, d in st.items() if (d or {}).get("status") == "running"]
    if out:
        return out
    # fallback: live per-project locks
    if os.path.isdir(_LOCKS):
        for fn in os.listdir(_LOCKS):
            if fn.endswith(".lock") and not fn.startswith("portfolio"):
                out.append(fn[:-5])
    return out


def status() -> Dict[str, Any]:
    cfg = load()
    reg = _rj(_REG, {})
    running = _running_projects()
    sups = live_supervisors()
    return {
        "limits": {k: cfg.get(k) for k in
                   ("max_parallel_projects", "max_created_projects", "max_supervisors")},
        "running_projects": sorted(running),
        "running_count": len(running),
        "created_count": len(reg),
        "supervisors": sups,
        "provider_limits": cfg.get("provider_limits", {}),
        "global_budget": cfg.get("global_budget", {}),
    }


def can_add() -> Dict[str, Any]:
    cfg, reg = load(), _rj(_REG, {})
    mx = int(cfg.get("max_created_projects") or 0)
    ok = (not mx) or len(reg) < mx
    return {"ok": ok, "created": len(reg), "max_created": mx,
            "reason": "" if ok else f"max_created_projects reached ({mx})"}


def can_start(project: str = "") -> Dict[str, Any]:
    cfg = load()
    running = _running_projects()
    mx = int(cfg.get("max_parallel_projects") or 0)
    ok = (not mx) or len(running) < mx
    return {"ok": ok, "running": len(running), "max_parallel": mx,
            "project": project,
            "reason": "" if ok else f"no free slot ({len(running)}/{mx} running)"}


def max_parallel_assignments() -> int:
    """Concurrent backlog-item assignments allowed across a scope (0 = unlimited). BI-PF-0419."""
    return int(load().get("max_parallel_assignments") or 0)


def can_assign(active: int) -> Dict[str, Any]:
    """Capacity check for per-item assignment (BI-PF-0419): ``active`` leased items < the cap."""
    mx = max_parallel_assignments()
    ok = (not mx) or int(active) < mx
    return {"ok": ok, "active": int(active), "max_parallel_assignments": mx,
            "reason": "" if ok else f"no free assignment slot ({active}/{mx})"}


def max_parallel_validations() -> int:
    """Concurrent validation runs allowed per repo (0 = unlimited). BI-PF-0420."""
    return int(load().get("max_parallel_validations") or 0)


def can_validate(active: int) -> Dict[str, Any]:
    """Capacity check for parallel validation (BI-PF-0420): ``active`` runs < the cap."""
    mx = max_parallel_validations()
    ok = (not mx) or int(active) < mx
    return {"ok": ok, "active": int(active), "max_parallel_validations": mx,
            "reason": "" if ok else f"no free validation slot ({active}/{mx})"}


def effective_limits(tier: str = "", extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Global limits, further capped by a license TIER (and optional extras).

    The global values stay the hard ceiling; the tier quota is the effective
    limit (min). 0 = unlimited on either side (BI-0041).
    """
    cfg = load()
    base = {k: cfg.get(k) for k in ("max_parallel_projects", "max_created_projects")}
    if tier:
        try:
            from core import licensing
            base = licensing.effective_limits(tier, base)
        except Exception:
            pass
    if extra:
        for k, v in extra.items():
            cur, new = int(base.get(k) or 0), int(v or 0)
            base[k] = new if cur == 0 else (cur if new == 0 else min(cur, new))
    return base


def can_add_context(tier: str = "", **extra) -> Dict[str, Any]:
    lim = effective_limits(tier, extra or None)
    reg = _rj(_REG, {})
    mx = int(lim.get("max_created_projects") or 0)
    ok = (not mx) or len(reg) < mx
    return {"ok": ok, "created": len(reg), "max_created": mx, "tier": tier,
            "reason": "" if ok else f"max_created_projects reached ({mx}) for tier {tier or 'default'}"}


def can_start_context(project: str = "", tier: str = "", **extra) -> Dict[str, Any]:
    lim = effective_limits(tier, extra or None)
    running = _running_projects()
    mx = int(lim.get("max_parallel_projects") or 0)
    ok = (not mx) or len(running) < mx
    return {"ok": ok, "running": len(running), "max_parallel": mx, "project": project, "tier": tier,
            "reason": "" if ok else f"no free slot ({len(running)}/{mx} running) for tier {tier or 'default'}"}


def can_start_supervisor() -> Dict[str, Any]:
    cfg = load()
    sups = live_supervisors()
    mx = int(cfg.get("max_supervisors") or 0)
    ok = (not mx) or len(sups) < mx
    return {"ok": ok, "supervisors": len(sups), "max_supervisors": mx,
            "reason": "" if ok else f"max_supervisors reached ({mx})"}
