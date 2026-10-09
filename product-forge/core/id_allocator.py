"""Collision-safe backlog id allocation (BI-PF-0462) - single writer of ``config/id-blocks.json``.

Root cause of the id collisions: ``core.backlog._next_id`` used ``max(local ids)+1`` over the worktree's OWN
items, so two concurrent sessions computed the same next id. Fix: a single authority mints contiguous id
**blocks** per (scope, project, session); a session allocates locally within its block. A shared PF API
(``POST /api/v1/backlog/ids:reserve``) is the authority that hands out blocks; offline, a session allocates
within its own reserved block (optionally offset via ``PF_ID_BLOCK_BASE``).

Applies to EVERY item type (epic / child / regular): they share one id space per (scope, project) and one create
path (``backlog.add_epic``). The worker CLAIM path (``/wg work``) does not allocate -- it claims an existing id --
but any item a worker's run CREATES goes through here too.

Framework-agnostic: core + config only. Ids stay ``BI-<TAG>-<nnn>`` (blocks leave gaps - acceptable).
"""
import json
import os
import socket
import threading

from core.paths import ROOT

OUT = os.path.join(str(ROOT), "config", "id-blocks.json")
_LOCK = threading.Lock()


def block_size() -> int:
    try:
        return int(os.environ.get("PF_ID_BLOCK_SIZE", "100") or 100)
    except Exception:
        return 100


def base() -> int:
    try:
        return int(os.environ.get("PF_ID_BLOCK_BASE", "0") or 0)
    except Exception:
        return 0


def session_id() -> str:
    """Stable id for THIS session/worktree. Explicit override wins; the worker plane passes its id."""
    s = str(os.environ.get("PF_SESSION_ID") or os.environ.get("WORKERGRID_WORKER_ID") or "").strip()
    return s or f"{socket.gethostname()}-{os.getpid()}"


def enabled() -> bool:
    return str(os.environ.get("PF_ID_ALLOC", "on")).strip().lower() not in ("off", "0", "false", "no")


def _read() -> dict:
    try:
        with open(OUT, encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {"blocks": {}}


def _write(d: dict) -> None:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
    os.replace(tmp, OUT)


def _key(scope: str, project: str | None) -> str:
    return f"{scope}::{project or ''}"


def _state(d: dict, scope: str, project: str | None) -> dict:
    return d.setdefault("blocks", {}).setdefault(
        _key(scope, project), {"reserved_up_to": 0, "sessions": {}})


_API_CACHE = {"base": None, "at": 0.0}


def _up(base: str) -> bool:
    try:
        import requests
        return requests.get(base + "/health", timeout=2).status_code == 200
    except Exception:
        return False


def _api_base() -> str:
    """The shared authority base. Explicit ``PF_API_URL`` wins; else default to the LOCAL PF API when it is
    actually reachable (short-TTL cached). ``PF_ID_ALLOC_API=off`` disables the API path (local blocks only)."""
    if str(os.environ.get("PF_ID_ALLOC_API", "on")).strip().lower() in ("off", "0", "false", "no"):
        return ""
    b = str(os.environ.get("PF_API_URL") or "").rstrip("/")
    if b:
        return b
    import time
    now = time.time()
    if _API_CACHE["base"] is not None and now - _API_CACHE["at"] < 10:
        return _API_CACHE["base"]
    host = str(os.environ.get("API_HOST") or "127.0.0.1")
    port = str(os.environ.get("API_PORT") or "8000")
    cand = f"http://{host}:{port}"
    base = cand if _up(cand) else ""
    _API_CACHE["base"] = base
    _API_CACHE["at"] = now
    return base


def _reserve_remote(scope: str, project: str | None, size: int) -> dict | None:
    """Ask the shared PF API (the authority) for a block. Returns None when unavailable/offline."""
    base = _api_base()
    if not base:
        return None
    try:
        import requests
        token = str(os.environ.get("API_TOKEN") or os.environ.get("WORKERGRID_TOKEN") or "")
        r = requests.post(base + "/api/v1/backlog/ids:reserve",
                          json={"scope": scope, "project": project or "", "size": size},
                          headers={"Authorization": f"Bearer {token}"} if token else {}, timeout=5)
        if r.status_code == 200:
            d = (r.json() or {}).get("data") or {}
            if d.get("start") and d.get("end"):
                return {"start": int(d["start"]), "end": int(d["end"])}
    except Exception:
        return None
    return None


def reserve(scope: str, project: str | None = None, size: int = 0, session: str = "") -> dict:
    """Authority-side: mint a fresh contiguous LOCAL block for ``session``. Returns {start,end,session,size}."""
    size = size or block_size()
    session = session or session_id()
    with _LOCK:
        d = _read()
        st = _state(d, scope, project)
        start = max(int(st.get("reserved_up_to") or 0), base()) + 1
        end = start + size - 1
        st["reserved_up_to"] = end
        st.setdefault("sessions", {})[session] = {"start": start, "end": end, "next": start}
        _write(d)
        return {"start": start, "end": end, "session": session, "size": size}


def _mint(scope: str, project: str | None, existing_max: int, reserved_up_to: int) -> dict:
    """Get a fresh block for this session: the shared API if reachable, else a local block."""
    size = block_size()
    rem = _reserve_remote(scope, project, size)
    if rem and int(rem["start"]) > int(existing_max):
        return {"start": rem["start"], "end": rem["end"], "next": rem["start"]}
    start = max(int(existing_max), int(reserved_up_to), base()) + 1
    return {"start": start, "end": start + size - 1, "next": start}


def alloc(scope: str, project: str | None, existing_max: int = 0, session: str = "") -> int:
    """Next id NUMBER for this (scope, project, session) - any item type; reserves a block when needed."""
    session = session or session_id()
    with _LOCK:
        d = _read()
        st = _state(d, scope, project)
        if int(st.get("reserved_up_to") or 0) < int(existing_max or 0):
            st["reserved_up_to"] = int(existing_max or 0)
        blk = st.setdefault("sessions", {}).get(session)
        if not blk or int(blk.get("next", 0)) > int(blk.get("end", 0)):
            blk = _mint(scope, project, existing_max, int(st.get("reserved_up_to") or 0))
            st["sessions"][session] = blk
            st["reserved_up_to"] = max(int(st.get("reserved_up_to") or 0), int(blk["end"]))
        n = int(blk["next"])
        blk["next"] = n + 1
        _write(d)
        return n
