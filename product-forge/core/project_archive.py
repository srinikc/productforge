"""Project archive / soft-delete (BI-0071).

Single concern: deleting a project is not immediate. The project directory is
ARCHIVED under ``products/.archive/<name>-<ts>/`` for a retention window
(default 7 days) so it can be RESTORED; then it is permanently deleted, with a
pre-delete reminder. Deletion only ever touches this module's own archive path.

Owner store: ``product-forge/archive/registry.json`` (kind=control, scope=product_forge)
"""
from __future__ import annotations

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
import shutil
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

REPO = str(_PF_ROOT)
PRODUCTS = os.path.join(REPO, "products")
ARCHIVE_DIR = os.path.join(PRODUCTS, ".archive")
REGISTRY = os.path.join(REPO, "data", "archive", "archive-registry.json")
DEFAULT_RETENTION_DAYS = 7


def _rj(p: str, default):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _wj(p: str, data) -> None:
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, p)


def retention_days() -> int:
    try:
        return int(os.getenv("PROJECT_ARCHIVE_RETENTION_DAYS", str(DEFAULT_RETENTION_DAYS)))
    except Exception:
        return DEFAULT_RETENTION_DAYS


def list_archived() -> List[Dict[str, Any]]:
    reg = _rj(REGISTRY, {}) or {}
    now = datetime.now()
    out = []
    for name, rec in reg.items():
        try:
            exp = datetime.fromisoformat(rec.get("expires_at", ""))
            rec = dict(rec)
            rec["days_remaining"] = max(0, (exp - now).days)
        except Exception:
            rec = dict(rec)
            rec["days_remaining"] = None
        out.append({"name": name, **rec})
    return out


def archive(project: str, reason: str = "user-delete") -> Dict[str, Any]:
    """Soft-delete: move products/<project> into the archive."""
    src = os.path.join(PRODUCTS, project)
    if not os.path.isdir(src):
        return {"ok": False, "error": f"project not found: {project}"}
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    dst = os.path.join(ARCHIVE_DIR, f"{project}-{ts}")
    shutil.move(src, dst)
    exp = (datetime.now() + timedelta(days=retention_days())).isoformat()
    reg = _rj(REGISTRY, {}) or {}
    reg[project] = {"path": dst, "archived_at": datetime.now().isoformat(),
                    "reason": reason, "expires_at": exp}
    _wj(REGISTRY, reg)
    return {"ok": True, "project": project, "archived_to": dst, "expires_at": exp,
            "days_remaining": retention_days()}


def restore(project: str) -> Dict[str, Any]:
    """Restore an archived project if still within retention."""
    reg = _rj(REGISTRY, {}) or {}
    rec = reg.get(project)
    if not rec:
        return {"ok": False, "error": f"no archive for {project}"}
    dst = rec.get("path", "")
    if not os.path.isdir(dst):
        return {"ok": False, "error": "archive path missing"}
    target = os.path.join(PRODUCTS, project)
    if os.path.exists(target):
        return {"ok": False, "error": f"a project named {project} already exists"}
    shutil.move(dst, target)
    reg.pop(project, None)
    _wj(REGISTRY, reg)
    return {"ok": True, "project": project, "restored_to": target}


def due_for_purge() -> List[str]:
    now = datetime.now()
    out = []
    for name, rec in (_rj(REGISTRY, {}) or {}).items():
        try:
            if datetime.fromisoformat(rec.get("expires_at", "")) <= now:
                out.append(name)
        except Exception:
            pass
    return out


def purge_due() -> List[str]:
    """Permanently delete archives past retention (own archive path only)."""
    reg = _rj(REGISTRY, {}) or {}
    purged = []
    for name in due_for_purge():
        path = reg.get(name, {}).get("path", "")
        # Safety: only delete paths inside our own ARCHIVE_DIR.
        if path and os.path.commonpath([os.path.abspath(path), ARCHIVE_DIR]) == os.path.abspath(ARCHIVE_DIR):
            shutil.rmtree(path, ignore_errors=True)
            reg.pop(name, None)
            purged.append(name)
    if purged:
        _wj(REGISTRY, reg)
    return purged


def reminder(project: str) -> Optional[Dict[str, Any]]:
    """Pre-delete reminder info (owner: send 1-2 days before purge)."""
    rec = (_rj(REGISTRY, {}) or {}).get(project)
    if not rec:
        return None
    try:
        days = max(0, (datetime.fromisoformat(rec.get("expires_at", "")) - datetime.now()).days)
    except Exception:
        days = None
    return {"project": project, "expires_at": rec.get("expires_at"), "days_remaining": days,
            "action": "restore-or-lose"}
