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
import json
import os
import subprocess
from typing import Any, Dict, List, Optional

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
