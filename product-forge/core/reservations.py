"""ENG-8: shared-path reservations + common-code detection (design: SHARED-PATH-RESERVATION-DESIGN.md).

Serializes concurrent workers on shared/common code so they cannot edit it at once (prevent conflicts rather
than resolve them). Advisory + TTL (cannot deadlock). Complements ENG-2's plan-time overlap check with a
runtime hold, plus a shared allowlist (config) and a git-hotspot heuristic (advisory).

Store: ``reservations.json`` (single writer: this module). Scope: global (holds are cross-worker).
"""
import contextlib
import fnmatch
import json
import os
import subprocess
import time
import uuid
from datetime import datetime
from typing import Any

from core.paths import ROOT

FILENAME = "reservations.json"
_SHARED = os.path.join(ROOT, "config", "shared-paths.json")
_DEFAULT_TTL = 3600


def _path() -> str:
    # overridable for tests/gates so they never write the shared store
    return os.environ.get("PF_RESERVATIONS_FILE") or os.path.join(ROOT, "engineering", FILENAME)


def _lock() -> str:
    d = os.path.dirname(_path())
    os.makedirs(d, exist_ok=True)
    lp = os.path.join(d, ".reservations.lock")
    for _ in range(50):
        try:
            fd = os.open(lp, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return lp
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(lp) > 300:
                    os.remove(lp)
                    continue
            except Exception:
                pass
            time.sleep(0.1)
    raise TimeoutError("could not acquire reservations lock")


def _unlock(lp: str) -> None:
    with contextlib.suppress(Exception):
        os.remove(lp)


def _read() -> dict[str, Any]:
    try:
        with open(_path(), encoding="utf-8-sig") as f:
            d = json.load(f)
        if isinstance(d, dict) and isinstance(d.get("reservations"), list):
            return d
    except Exception:
        pass
    return {"reservations": []}


def _write(data: dict[str, Any]) -> None:
    p = _path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, p)


# ── shared/common detection ─────────────────────────────────────────────────
def shared_config() -> dict[str, Any]:
    try:
        with open(_SHARED, encoding="utf-8-sig") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def is_shared(path: str) -> bool:
    """True if a path is shared/common per the allowlist (component or glob)."""
    p = str(path or "").replace("\\", "/").lstrip("./")
    if not p:
        return False
    cfg = shared_config()
    comp = p.split("/", 1)[0]
    if comp in (cfg.get("components") or []):
        return True
    return any(fnmatch.fnmatch(p, g) or fnmatch.fnmatch(os.path.basename(p), g)
               for g in (cfg.get("globs") or []))


def shared_paths(paths: list[str]) -> list[str]:
    return [p for p in (paths or []) if is_shared(p)]


def hotspots(limit: int = 20) -> list[dict[str, Any]]:
    """Advisory: most frequently-changed files in recent history (common-code signal)."""
    cfg = shared_config().get("hotspot") or {}
    if not cfg.get("enabled", True):
        return []
    n = int(cfg.get("history_commits") or 100)
    minc = int(cfg.get("min_commits") or 3)
    try:
        r = subprocess.run(["git", "-C", ROOT, "log", f"-{n}", "--name-only", "--pretty=format:"],
                           capture_output=True, text=True, timeout=60)
    except Exception:
        return []
    counts: dict[str, int] = {}
    for line in (r.stdout or "").splitlines():
        line = line.strip()
        if line and not line.startswith(("Merge ", "commit ")):
            counts[line] = counts.get(line, 0) + 1
    rows = [{"path": k, "commits": v} for k, v in counts.items() if v >= minc]
    rows.sort(key=lambda x: (-x["commits"], x["path"]))
    return rows[:limit]


# ── reservations (advisory runtime holds) ───────────────────────────────────
def _live(rows: list[dict[str, Any]], now: float) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        held = str(r.get("state")) == "held"
        fresh = (now - float(r.get("acquired_ts", 0) or 0)) < float(r.get("ttl_s", _DEFAULT_TTL) or _DEFAULT_TTL)
        if held and fresh:
            out.append(r)
    return out


def list_active() -> list[dict[str, Any]]:
    now = time.time()
    return _live(_read().get("reservations", []), now)


def holder_of(resource: str) -> dict[str, Any] | None:
    r = str(resource or "").replace("\\", "/")
    for row in list_active():
        if row.get("resource") == r:
            return row
    return None


def acquire(resource: str, *, holder_task: str = "", holder_worker: str = "", run_id: str = "",
            kind: str = "path", ttl_s: int = _DEFAULT_TTL) -> dict[str, Any]:
    """Acquire an advisory hold on ``resource``. Returns {ok, reservation|holder}."""
    res = str(resource or "").replace("\\", "/").strip()
    if not res:
        return {"ok": False, "reason": "empty resource"}
    lp = _lock()
    try:
        data = _read()
        now = time.time()
        live = _live(data.get("reservations", []), now)
        holder = next((r for r in live if r.get("resource") == res), None)
        if holder:
            same = holder_task and holder.get("holder_task") == holder_task
            if not same:
                return {"ok": False, "reason": "reserved", "holder": holder}
        rec = {"id": "RSV-" + uuid.uuid4().hex[:8], "resource": res, "kind": kind,
               "holder_task": holder_task, "holder_worker": holder_worker, "run_id": run_id,
               "state": "held", "acquired_at": datetime.now().isoformat(), "acquired_ts": now,
               "ttl_s": int(ttl_s)}
        data["reservations"] = [r for r in live if r.get("resource") != res] + [rec]
        _write(data)
        return {"ok": True, "reservation": rec}
    finally:
        _unlock(lp)


def acquire_many(resources: list[str], **kw) -> dict[str, Any]:
    """All-or-nothing acquire of several resources."""
    got = []
    for r in resources:
        a = acquire(r, **kw)
        if not a.get("ok"):
            for g in got:
                release(g)
            return {"ok": False, "reason": a.get("reason"), "blocked": r, "holder": a.get("holder")}
        got.append(a["reservation"]["resource"])
    return {"ok": True, "resources": got}


def release(resource: str) -> bool:
    res = str(resource or "").replace("\\", "/")
    lp = _lock()
    try:
        data = _read()
        rows = data.get("reservations", [])
        before = len(_live(rows, time.time()))
        for r in rows:
            if r.get("resource") == res:
                r["state"] = "released"
        _write(data)
        return len(_live(_read().get("reservations", []), time.time())) < before or True
    finally:
        _unlock(lp)
