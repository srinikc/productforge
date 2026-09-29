"""Single-writer facade for the budget/cost concern (addresses BI-0002).

One store per scope with sections, replacing 5 parallel files:

    products/budget.json            (global scope)
    products/<project>/budget.json  (project scope)

    {
      "version": "1",
      "limits":      {},        # windows / total_max / stage limits
      "usage":       {},        # total_used, per_project, per_stage
      "allocations": {},        # per-stage allocations
      "state":       { "alerts": [], "breakers": {} },
      "history":     []         # append-only spend/usage/reallocation entries
    }

Legacy files are migrated once (and renamed `*.migrated`):
    budget-tracking.json, budget_allocations.json, cost_metrics.jsonl, pipeline_cost_history.json

All writers (budget_tracker, budget_protection, budget_allocator, cost_kpi,
pipeline_telemetry) go through this module; readers keep reading `budget.json`.
"""
import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

_DEFAULT_PRODUCTS = "products"
_LEGACY_FILES = ("budget-tracking.json", "budget_allocations.json",
                 "cost_metrics.jsonl", "pipeline_cost_history.json")


def path(project: Optional[str] = None, products_dir: str = _DEFAULT_PRODUCTS) -> str:
    if project in (None, "", "default"):
        return os.path.join(products_dir, "budget.json")
    return os.path.join(products_dir, project, "budget.json")


def _empty() -> Dict:
    return {"version": "1", "limits": {}, "usage": {}, "allocations": {},
            "state": {"alerts": [], "breakers": {}}, "history": []}


def _lock(p: str):
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    lp = p + ".lock"
    for _ in range(50):
        try:
            fd = os.open(lp, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return lp
        except FileExistsError:
            # Reclaim a stale lock left by a dead/hung writer.
            try:
                if time.time() - os.path.getmtime(lp) > 300:
                    os.remove(lp)
                    continue
            except Exception:
                pass
            time.sleep(0.1)
    # Fail closed (PF-011): never mutate the budget store without the lock.
    raise TimeoutError(f"[Budget] could not acquire lock {lp} within timeout")


def _unlock(lp):
    try:
        if lp:
            os.remove(lp)
    except Exception:
        pass


def load(project: Optional[str] = None, products_dir: str = _DEFAULT_PRODUCTS) -> Dict:
    p = path(project, products_dir)
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
    except Exception:
        data = {}
    base = _empty()
    base.update({k: v for k, v in data.items() if k in base})
    return base


def save(project: Optional[str], data: Dict, products_dir: str = _DEFAULT_PRODUCTS) -> Dict:
    p = path(project, products_dir)
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    os.replace(tmp, p)
    return data


def _mutate(project: Optional[str], fn, products_dir: str = _DEFAULT_PRODUCTS) -> Dict:
    p = path(project, products_dir)
    lp = _lock(p)
    try:
        data = load(project, products_dir)
        fn(data)
        save(project, data, products_dir)
        return data
    finally:
        _unlock(lp)


def read_section(project: Optional[str], section: str,
                 products_dir: str = _DEFAULT_PRODUCTS) -> Dict:
    val = load(project, products_dir).get(section)
    return val if isinstance(val, (dict, list)) else ({} if section != "history" else [])


def update_section(project: Optional[str], section: str, values: Dict,
                   products_dir: str = _DEFAULT_PRODUCTS) -> Dict:
    def _fn(d):
        cur = d.get(section)
        if not isinstance(cur, dict):
            cur = {}
        cur.update(values or {})
        d[section] = cur
    return _mutate(project, _fn, products_dir)


def append_history(project: Optional[str], entries: Any,
                   products_dir: str = _DEFAULT_PRODUCTS) -> Dict:
    items = entries if isinstance(entries, list) else [entries]
    items = [i for i in items if i]
    if not items:
        return load(project, products_dir)

    def _fn(d):
        hist = d.get("history")
        if not isinstance(hist, list):
            hist = []
        hist.extend(items)
        d["history"] = hist[-5000:]
    return _mutate(project, _fn, products_dir)


def record_usage(project: Optional[str], tokens: int = 0, cost: float = 0.0,
                 stage: Any = None, products_dir: str = _DEFAULT_PRODUCTS) -> Dict:
    entry = {"at": datetime.now().isoformat(), "tokens": int(tokens or 0),
             "cost": float(cost or 0.0)}
    if stage is not None:
        entry["stage"] = stage

    def _fn(d):
        usage = d.setdefault("usage", {})
        usage["total_used"] = int(usage.get("total_used", 0)) + int(tokens or 0)   # tokens
        usage["tokens_used"] = int(usage.get("tokens_used", 0)) + int(tokens or 0)
        usage["cost_used"] = float(usage.get("cost_used", 0.0)) + float(cost or 0.0)
        hist = d.setdefault("history", [])
        hist.append(entry)
        d["history"] = hist[-5000:]
    return _mutate(project, _fn, products_dir)


def reserve(project: Optional[str], amount: float, key: str = "",
            products_dir: str = _DEFAULT_PRODUCTS) -> Dict:
    """Atomically reserve `amount` against the budget (PF-013).

    Returns {ok, reason, reserved_total}. Fail-closed: if a configured cap
    (limits.per_run_cap_usd|total_cap_usd) would be exceeded, ok=False and nothing
    is reserved. The reservation is recorded in state.reservations[key].
    """
    out = {"ok": True, "reason": "", "reserved_total": 0.0}

    def _fn(d):
        lim = d.get("limits") or {}
        usage = d.get("usage") or {}
        st = d.setdefault("state", {})
        rsv = st.setdefault("reservations", {})
        reserved = sum(float(v or 0.0) for v in rsv.values())
        cap = float(lim.get("per_run_cap_usd") or lim.get("total_cap_usd") or 0.0)
        used = float(usage.get("cost_used", 0.0) or 0.0)
        if cap and (used + reserved + float(amount or 0.0)) > cap:
            out["ok"] = False
            out["reason"] = (f"budget cap {cap} exceeded "
                             f"(used={used}, reserved={reserved}, add={amount})")
        else:
            rsv[str(key or "anon")] = float(amount or 0.0)
            out["reserved_total"] = reserved + float(amount or 0.0)
    _mutate(project, _fn, products_dir)
    return out


def release(project: Optional[str], key: str = "",
            products_dir: str = _DEFAULT_PRODUCTS) -> None:
    """Release a reservation without charging usage."""
    def _fn(d):
        st = d.setdefault("state", {})
        st.setdefault("reservations", {}).pop(str(key or "anon"), None)
    _mutate(project, _fn, products_dir)


def commit_reservation(project: Optional[str], key: str = "", actual_cost: float = 0.0,
                       tokens: int = 0, products_dir: str = _DEFAULT_PRODUCTS) -> Dict:
    """Convert a reservation into real usage (cost/tokens) and drop the reservation."""
    def _fn(d):
        st = d.setdefault("state", {})
        st.setdefault("reservations", {}).pop(str(key or "anon"), None)
        usage = d.setdefault("usage", {})
        usage["cost_used"] = float(usage.get("cost_used", 0.0) or 0.0) + float(actual_cost or 0.0)
        usage["tokens_used"] = int(usage.get("tokens_used", 0) or 0) + int(tokens or 0)
        hist = d.setdefault("history", [])
        hist.append({"at": datetime.now().isoformat(), "tokens": int(tokens or 0),
                     "cost": float(actual_cost or 0.0), "reservation": str(key or "anon")})
        d["history"] = hist[-5000:]
    return _mutate(project, _fn, products_dir)


def add_alert(project: Optional[str], alert: Dict,
              products_dir: str = _DEFAULT_PRODUCTS) -> Dict:
    def _fn(d):
        st = d.setdefault("state", {})
        alerts = st.setdefault("alerts", [])
        alerts.append(alert)
        st["alerts"] = alerts[-100:]
    return _mutate(project, _fn, products_dir)


def migrate_legacy(project: Optional[str] = None,
                   products_dir: str = _DEFAULT_PRODUCTS) -> List[str]:
    """Import legacy budget files into the unified store once; rename them *.migrated."""
    scope_dir = products_dir if project in (None, "", "default") else os.path.join(products_dir, project)
    migrated = []
    for name in _LEGACY_FILES:
        src = os.path.join(scope_dir, name)
        if not os.path.exists(src):
            continue
        try:
            if name == "budget-tracking.json":
                data = json.load(open(src, encoding="utf-8")) or {}
                update_section(project, "state", {
                    "total_used": data.get("total_used", 0),
                    "total_max": data.get("total_max", 0),
                    "alerts": data.get("alerts", [])}, products_dir)
            elif name == "budget_allocations.json":
                data = json.load(open(src, encoding="utf-8")) or {}
                update_section(project, "allocations", {
                    "stages": data.get("allocations", []), "updated_at": data.get("updated_at", "")},
                    products_dir)
                append_history(project, [{"at": datetime.now().isoformat(), "kind": "reallocation",
                                          **h} for h in (data.get("history") or [])], products_dir)
            elif name == "cost_metrics.jsonl":
                rows = []
                with open(src, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                rows.append({"at": datetime.now().isoformat(), "kind": "task_cost",
                                             **json.loads(line)})
                            except json.JSONDecodeError:
                                continue
                append_history(project, rows, products_dir)
            elif name == "pipeline_cost_history.json":
                data = json.load(open(src, encoding="utf-8")) or {}
                rows = data if isinstance(data, list) else data.get("history", [])
                append_history(project, rows, products_dir)
            os.replace(src, src + ".migrated")
            migrated.append(name)
        except Exception:
            continue
    return migrated
