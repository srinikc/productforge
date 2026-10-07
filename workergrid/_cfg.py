"""WorkerGrid config + paths (shared by the CLI and client).

Config home resolution (BI-PF-0417) mirrors the Go components
(``internal/config.Home()``): ``$WORKERGRID_HOME`` when set, else the checkout's
``workergrid/`` directory (where ``config.json`` lives). This keeps ``/wg …``
and ``/wg serve`` pointing at the SAME config.
"""
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))


def home() -> str:
    """$WORKERGRID_HOME (absolute) > the checkout's workergrid dir."""
    h = os.environ.get("WORKERGRID_HOME", "").strip()
    return os.path.abspath(h) if h else ROOT


def load() -> dict:
    try:
        with open(os.path.join(home(), "config.json"), encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def state_dir() -> str:
    d = os.environ.get("WORKERGRID_STATE_DIR", "").strip() \
        or os.path.join(home(), str(load().get("state_dir") or "state"))
    os.makedirs(d, exist_ok=True)
    return d


def instructions_path() -> str:
    return os.path.join(home(), str(load().get("instructions_file") or "instructions.md"))


def lease_seconds(default: int = 3600) -> int:
    """Lease TTL in seconds: WORKERGRID_LEASE_SECONDS env > config > default."""
    try:
        return int(os.environ.get("WORKERGRID_LEASE_SECONDS", "").strip()
                   or load().get("lease_seconds") or default)
    except (TypeError, ValueError):
        return default


def read_json(name: str, default):
    p = os.path.join(state_dir(), name)
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_json(name: str, data) -> None:
    p = os.path.join(state_dir(), name)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, p)
