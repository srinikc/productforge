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
import shutil
import socket
import subprocess
import tempfile
import threading

from core.paths import ROOT

OUT = os.path.join(str(ROOT), "config", "id-blocks.json")
_LOCK = threading.Lock()


def block_size() -> int:
    try:
        return int(os.environ.get("PF_ID_BLOCK_SIZE", "1") or 1)
    except Exception:
        return 1


def base() -> int:
    try:
        return int(os.environ.get("PF_ID_BLOCK_BASE", "0") or 0)
    except Exception:
        return 0


def session_id() -> str:
    """Stable id for THIS session/worktree. Explicit override wins; the worker plane passes its id."""
    s = str(os.environ.get("PF_SESSION_ID") or os.environ.get("WORKERGRID_WORKER_ID") or "").strip()
    return s or f"{socket.gethostname()}-{os.getpid()}"


def _mode() -> str:
    v = ""
    try:
        from core import env_flags
        v = env_flags.get("PF_ID_ALLOC", os.environ.get("PF_ID_ALLOC", "strict"))
    except Exception:
        v = os.environ.get("PF_ID_ALLOC", "strict")
    return str(v or "strict").strip().lower()


def enabled() -> bool:
    return _mode() not in ("off", "0", "false", "no")


def strict() -> bool:
    """BI-PF-0966: opt-in hard mode - require the shared git authority, never self-reserve (DEFAULT OFF)."""
    return _mode() in ("strict", "hard", "required")


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


def _repo_root() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=str(ROOT),
                           capture_output=True, text=True)
        return (r.stdout or "").strip()
    except Exception:
        return ""


def _git(root: str, *args, env=None, stdin=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    try:
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, env=e, input=stdin)
    except Exception:
        return 1, "", "exec-failed"
    return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()


def _remote_enabled() -> bool:
    return str(os.environ.get("PF_ID_ALLOC_REMOTE", "on")).strip().lower() not in ("off", "0", "false", "no")


def _reserve_git(scope: str, project: str | None, size: int, existing_max: int = 0) -> dict | None:
    """Reserve a block via an ATOMIC CAS on the shared git remote (BI-PF-0764).

    The counter lives in ``id-counter.json`` on ``refs/heads/pf-id-counter``. We commit the new counter and
    ``git push`` it: a NON-fast-forward push is rejected (someone else advanced it) -> retry. This is a
    compare-and-swap, so any session/worker sharing the remote gets disjoint blocks with nothing to point at.
    The block always starts ABOVE ``existing_max`` (so remote blocks are never behind local items).
    """
    if not _remote_enabled():
        return None
    root = _repo_root()
    if not root:
        return None
    ref = str(os.environ.get("PF_ID_REMOTE_REF", "refs/heads/pf-id-counter"))
    path = "id-counter" + ".json"
    key = _key(scope, project)
    for _ in range(5):
        rc, _, _ = _git(root, "fetch", "origin", f"{ref}:{ref}")
        rc2, out, _ = _git(root, "show", f"{ref}:{path}")
        try:
            data = json.loads(out) if (rc2 == 0 and out) else {"blocks": {}}
        except Exception:
            data = {"blocks": {}}
        st = data.setdefault("blocks", {}).setdefault(key, {"reserved_up_to": 0})
        start = max(int(st.get("reserved_up_to") or 0), int(existing_max or 0), base()) + 1
        end = start + size - 1
        st["reserved_up_to"] = end
        rc3, blob, _ = _git(root, "hash-object", "-w", "--stdin",
                            stdin=json.dumps(data, indent=2, ensure_ascii=False))
        if rc3 != 0:
            return None
        td = tempfile.mkdtemp()
        envf = {"GIT_INDEX_FILE": os.path.join(td, "index")}
        if rc == 0:
            _git(root, "read-tree", ref, env=envf)
        else:
            _git(root, "read-tree", "--empty", env=envf)
        _git(root, "update-index", "--add", "--cacheinfo", f"100644,{blob},{path}", env=envf)
        rc4, tree, _ = _git(root, "write-tree", env=envf)
        shutil.rmtree(td, ignore_errors=True)
        if rc4 != 0:
            return None
        if rc == 0:
            rc5, commit, _ = _git(root, "commit-tree", tree, "-p", ref, "-m", "reserve backlog ids [skip ci]")
        else:
            rc5, commit, _ = _git(root, "commit-tree", tree, "-m", "reserve backlog ids [skip ci]")
        if rc5 != 0:
            return None
        rc6, _, _ = _git(root, "push", "origin", f"{commit}:{ref}")
        if rc6 == 0:
            return {"start": start, "end": end}
        # CAS lost the race -> refetch and retry
    return None


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


def lift_remote(scope: str, project: str | None, at_least: int) -> dict | None:
    """CAS-advance the remote counter to at least ``at_least`` (never lowers it). No session block consumed.

    Called at merge/PR with the GLOBAL max id, so the shared counter is always >= every issued id -> a stale
    session can never re-reserve an already-issued range (BI-PF-0866).
    """
    if not _remote_enabled():
        return None
    root = _repo_root()
    if not root:
        return None
    ref = str(os.environ.get("PF_ID_REMOTE_REF", "refs/heads/pf-id-counter"))
    path = "id-counter" + ".json"
    key = _key(scope, project)
    for _ in range(5):
        rc, _, _ = _git(root, "fetch", "origin", f"{ref}:{ref}")
        rc2, out, _ = _git(root, "show", f"{ref}:{path}")
        try:
            data = json.loads(out) if (rc2 == 0 and out) else {"blocks": {}}
        except Exception:
            data = {"blocks": {}}
        st = data.setdefault("blocks", {}).setdefault(key, {"reserved_up_to": 0})
        cur = int(st.get("reserved_up_to") or 0)
        if cur >= int(at_least):
            return {"reserved_up_to": cur}
        st["reserved_up_to"] = int(at_least)
        rc3, blob, _ = _git(root, "hash-object", "-w", "--stdin",
                            stdin=json.dumps(data, indent=2, ensure_ascii=False))
        if rc3 != 0:
            return None
        td = tempfile.mkdtemp()
        envf = {"GIT_INDEX_FILE": os.path.join(td, "index")}
        if rc == 0:
            _git(root, "read-tree", ref, env=envf)
        else:
            _git(root, "read-tree", "--empty", env=envf)
        _git(root, "update-index", "--add", "--cacheinfo", f"100644,{blob},{path}", env=envf)
        rc4, tree, _ = _git(root, "write-tree", env=envf)
        shutil.rmtree(td, ignore_errors=True)
        if rc4 != 0:
            return None
        if rc == 0:
            rc5, commit, _ = _git(root, "commit-tree", tree, "-p", ref, "-m", "lift id-counter [skip ci]")
        else:
            rc5, commit, _ = _git(root, "commit-tree", tree, "-m", "lift id-counter [skip ci]")
        if rc5 != 0:
            return None
        rc6, _, _ = _git(root, "push", "origin", f"{commit}:{ref}")
        if rc6 == 0:
            return {"reserved_up_to": int(at_least)}
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
    """Get a fresh block for this session: the shared git remote (CAS) first, then the API, then a local block.

    In ``strict`` mode (opt-in) only the git-CAS is allowed; if it fails we RAISE (never self-reserve).
    """
    size = block_size()
    cand = _reserve_git(scope, project, size, existing_max)
    if strict():
        if not (cand and int(cand["start"]) > int(existing_max)):
            raise RuntimeError("PF_ID_ALLOC=strict: the shared git authority is unavailable - refusing to "
                               "self-reserve a local id block")
        return {"start": cand["start"], "end": cand["end"], "next": cand["start"]}
    if not (cand and int(cand["start"]) > int(existing_max)):
        cand = _reserve_remote(scope, project, size)
    if cand and int(cand["start"]) > int(existing_max):
        return {"start": cand["start"], "end": cand["end"], "next": cand["start"]}
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
