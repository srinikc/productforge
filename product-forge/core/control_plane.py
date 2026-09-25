"""Dashboard control-plane store (SQLite) - BI-0043.

Single concern: the dashboard's OWN control-plane data (tenants, users, sessions,
settings) lives in a database, while the pipeline's truths stay file stores. Single
writer = this module; the API layer reads/writes only through it.

Engine: SQLite (self-hosted default). For multi-tenant SaaS, point the DB at
Postgres by setting CONTROL_PLANE_DSN (out of scope here - schema is portable).

Owner store: ``product-forge/control-plane/control-plane.db`` (kind=control, scope=product_forge)
"""
from __future__ import annotations

import os
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(REPO, "data", "control-plane", "control-plane.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tenants (
  id TEXT PRIMARY KEY, name TEXT, tier TEXT, status TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY, tenant_id TEXT, email TEXT, name TEXT, roles TEXT,
  status TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY, user_id TEXT, created_at TEXT, expires_at TEXT
);
CREATE TABLE IF NOT EXISTS settings (
  tenant_id TEXT, key TEXT, value TEXT, PRIMARY KEY (tenant_id, key)
);
"""


def _conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.executescript(_SCHEMA)
    return c


def _rows(cur: sqlite3.Cursor) -> List[Dict[str, Any]]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _row(cur: sqlite3.Cursor) -> Optional[Dict[str, Any]]:
    cols = [d[0] for d in cur.description]
    r = cur.fetchone()
    return dict(zip(cols, r)) if r is not None else None


def _now() -> str:
    return datetime.now().isoformat()


def create_tenant(name: str, tier: str = "trial", status: str = "active") -> Dict[str, Any]:
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO tenants (id,name,tier,status,created_at) VALUES (?,?,?,?,?)",
                  (name, name, tier, status, _now()))
    return {"id": name, "name": name, "tier": tier, "status": status}


def list_tenants() -> List[Dict[str, Any]]:
    with _conn() as c:
        return _rows(c.execute("SELECT * FROM tenants ORDER BY created_at"))


def upsert_user(tenant: str, email: str, name: str = "", roles=None, status: str = "active") -> Dict[str, Any]:
    uid = f"{tenant}:{email.lower()}"
    rr = roles if isinstance(roles, str) else json.dumps(sorted(set(roles or ["read"])))
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO users (id,tenant_id,email,name,roles,status,created_at) "
                  "VALUES (?,?,?,?,?,?,COALESCE((SELECT created_at FROM users WHERE id=?), ?))",
                  (uid, tenant, email.lower(), name, rr, status, uid, _now()))
    return {"id": uid, "tenant": tenant, "email": email.lower(), "roles": rr, "status": status}


def list_users(tenant: str = "") -> List[Dict[str, Any]]:
    with _conn() as c:
        if tenant:
            return _rows(c.execute("SELECT * FROM users WHERE tenant_id=? ORDER BY email", (tenant,)))
        return _rows(c.execute("SELECT * FROM users ORDER BY tenant_id,email"))


def create_session(user_id: str, ttl_hours: int = 24) -> Dict[str, Any]:
    import secrets
    sid = secrets.token_urlsafe(24)
    exp = (datetime.now() + timedelta(hours=ttl_hours)).isoformat()
    with _conn() as c:
        c.execute("INSERT INTO sessions (id,user_id,created_at,expires_at) VALUES (?,?,?,?)",
                  (sid, user_id, _now(), exp))
    return {"session": sid, "user_id": user_id, "expires_at": exp}


def get_session(sid: str) -> Optional[Dict[str, Any]]:
    with _conn() as c:
        d = _row(c.execute("SELECT * FROM sessions WHERE id=?", (sid,)))
        if not d:
            return None
        try:
            if datetime.fromisoformat(d["expires_at"]) < datetime.now():
                return None
        except Exception:
            pass
        return d


def set_setting(tenant: str, key: str, value) -> None:
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO settings (tenant_id,key,value) VALUES (?,?,?)",
                  (tenant, key, json.dumps(value)))


def get_setting(tenant: str, key: str, default=None):
    with _conn() as c:
        row = _row(c.execute("SELECT value FROM settings WHERE tenant_id=? AND key=?", (tenant, key)))
        return json.loads(row["value"]) if row else default
