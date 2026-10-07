"""WorkerGrid shared coordination store (SQLite; Postgres later).

Owns the coordination state that must be **shared across machines**: workers, leases, assignments.
Producer-agnostic. Single writer (this module). Stage 2b.
"""
import os
import sqlite3
import time

try:
    from . import _cfg  # type: ignore
except Exception:
    import _cfg  # type: ignore

_SCHEMA = """
CREATE TABLE IF NOT EXISTS workers (
  worker_id TEXT PRIMARY KEY,
  runtime TEXT,
  capabilities TEXT,
  role TEXT,
  status TEXT,
  registered_at REAL,
  last_heartbeat REAL,
  current_assignment TEXT
);
CREATE TABLE IF NOT EXISTS leases (
  item_id TEXT PRIMARY KEY,
  worker_id TEXT,
  runtime TEXT,
  assignment_id TEXT,
  expires_at REAL,
  created_at REAL
);
"""


def _db() -> sqlite3.Connection:
    d = _cfg.state_dir()
    c = sqlite3.connect(os.path.join(d, "workergrid.db"))
    c.row_factory = sqlite3.Row
    c.executescript(_SCHEMA)
    return c


def _now() -> float:
    return time.time()


def _row(r) -> dict:
    return dict(r) if r is not None else None


# ── workers ─────────────────────────────────────────────────────────────────
def register(worker_id: str, runtime: str = "", capabilities: list | None = None,
             role: str = "") -> dict:
    wid = str(worker_id or "").strip() or f"WRK-{runtime or 'worker'}-{int(_now()) % 100000000}"
    caps = ",".join(str(c) for c in (capabilities or []))
    c = _db()
    try:
        c.execute("INSERT INTO workers(worker_id,runtime,capabilities,role,status,registered_at,last_heartbeat,current_assignment)"
                  " VALUES(?,?,?,?,?,?,?,'')"
                  " ON CONFLICT(worker_id) DO UPDATE SET runtime=excluded.runtime,"
                  " capabilities=excluded.capabilities, role=excluded.role, status='ONLINE',"
                  " last_heartbeat=excluded.last_heartbeat",
                  (wid, runtime, caps, role, "ONLINE", _now(), _now()))
        c.commit()
    finally:
        c.close()
    return get(wid)


def get(worker_id: str) -> dict | None:
    c = _db()
    try:
        return _row(c.execute("SELECT * FROM workers WHERE worker_id=?", (str(worker_id),)).fetchone())
    finally:
        c.close()


def list_workers() -> list[dict]:
    c = _db()
    try:
        return [_row(r) for r in c.execute("SELECT * FROM workers ORDER BY registered_at").fetchall()]
    finally:
        c.close()


def heartbeat(worker_id: str, status: str = "", current_assignment: str = "") -> dict:
    w = get(worker_id)
    if not w:
        return {"ok": False, "reason": "unknown worker"}
    c = _db()
    try:
        c.execute("UPDATE workers SET last_heartbeat=?, status=?, current_assignment=? WHERE worker_id=?",
                  (_now(), status or w["status"], current_assignment or w["current_assignment"], str(worker_id)))
        c.commit()
    finally:
        c.close()
    return {"ok": True, "worker_id": str(worker_id)}


def unregister(worker_id: str) -> dict:
    c = _db()
    try:
        n = c.execute("DELETE FROM workers WHERE worker_id=?", (str(worker_id),)).rowcount
        c.execute("DELETE FROM leases WHERE worker_id=?", (str(worker_id),))
        c.commit()
    finally:
        c.close()
    return {"removed": bool(n), "worker_id": str(worker_id)}


# ── leases (claim) ──────────────────────────────────────────────────────────
def claim(item_id: str, worker_id: str, runtime: str = "", lease_seconds: int = 0) -> dict:
    secs = int(lease_seconds or _cfg.load().get("lease_seconds") or 3600)
    now = _now()
    c = _db()
    try:
        c.execute("BEGIN IMMEDIATE")
        cur = c.execute("SELECT * FROM leases WHERE item_id=?", (str(item_id),)).fetchone()
        if cur and float(cur["expires_at"]) > now:
            c.commit()
            return {"claimed": False, "reason": f"already leased by {cur['worker_id']}"}
        asg = f"ASG-{item_id}"
        c.execute("INSERT INTO leases(item_id,worker_id,runtime,assignment_id,expires_at,created_at)"
                  " VALUES(?,?,?,?,?,?) ON CONFLICT(item_id) DO UPDATE SET worker_id=excluded.worker_id,"
                  " runtime=excluded.runtime, assignment_id=excluded.assignment_id,"
                  " expires_at=excluded.expires_at, created_at=excluded.created_at",
                  (str(item_id), str(worker_id), str(runtime), asg, now + secs, now))
        c.execute("UPDATE workers SET status='BUSY', current_assignment=? WHERE worker_id=?", (str(item_id), str(worker_id)))
        c.commit()
    finally:
        c.close()
    return {"claimed": True, "item_id": str(item_id), "worker_id": str(worker_id),
            "assignment_id": asg, "expires_at": now + secs}


def renew(item_id: str, lease_seconds: int = 0) -> dict:
    secs = int(lease_seconds or _cfg.load().get("lease_seconds") or 3600)
    c = _db()
    try:
        n = c.execute("UPDATE leases SET expires_at=? WHERE item_id=?", (_now() + secs, str(item_id))).rowcount
        c.commit()
    finally:
        c.close()
    return {"renewed": bool(n), "item_id": str(item_id)}


def release(item_id: str) -> dict:
    c = _db()
    try:
        row = c.execute("SELECT worker_id FROM leases WHERE item_id=?", (str(item_id),)).fetchone()
        c.execute("DELETE FROM leases WHERE item_id=?", (str(item_id),))
        if row:
            c.execute("UPDATE workers SET status='IDLE', current_assignment='' WHERE worker_id=?", (row["worker_id"],))
        c.commit()
    finally:
        c.close()
    return {"released": True, "item_id": str(item_id)}


def list_leases() -> list[dict]:
    c = _db()
    try:
        return [_row(r) for r in c.execute("SELECT * FROM leases ORDER BY created_at").fetchall()]
    finally:
        c.close()


def recover_expired() -> dict:
    now = _now()
    c = _db()
    try:
        rows = c.execute("SELECT item_id,worker_id FROM leases WHERE expires_at < ?", (now,)).fetchall()
        for r in rows:
            c.execute("UPDATE workers SET status='IDLE', current_assignment='' WHERE worker_id=?", (r["worker_id"],))
        c.execute("DELETE FROM leases WHERE expires_at < ?", (now,))
        c.commit()
    finally:
        c.close()
    return {"recovered": [r["item_id"] for r in rows], "count": len(rows)}
