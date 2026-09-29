"""Run-bound artifact/approval manifest — provenance SSOT for a run (F0-3 / M0.3).

Single writer. Store: ``products/<project>/run-manifests/<run_id>.json``::

    {
      "run_id": "...", "project": "...", "created_at": "...", "updated_at": "...",
      "artifacts": {"<stage>/<agent>": {"path": "...", "sha256": "...", "at": "..."}},
      "approvals": {"<stage>/<agent>": {"decision": "...", "run_id": "...",
                                        "artifact_sha256": "...", "at": "...", "notes": "..."}}
    }

Purpose (audit PF-006/PF-031/BU-C06/CB-C01/CB-C02): verification, close-loop, resume and
approval consumption must bind to the CURRENT run and artifact digest instead of accepting
"any markdown / latest report / stale approval" by existence.
"""
import hashlib
import json
import os
from datetime import datetime
from typing import Dict, Optional

_SUBDIR = "run-manifests"


def _dir(project_dir: str) -> str:
    return os.path.join(project_dir, _SUBDIR)


def _path(project_dir: str, run_id: str) -> str:
    safe = "".join(c for c in str(run_id or "") if c.isalnum() or c in "-_.") or "unknown"
    return os.path.join(_dir(project_dir), f"{safe}.json")


def _load(project_dir: str, run_id: str) -> Dict:
    try:
        with open(_path(project_dir, run_id), "r", encoding="utf-8-sig") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _save(project_dir: str, run_id: str, data: Dict) -> None:
    try:
        os.makedirs(_dir(project_dir), exist_ok=True)
        p = _path(project_dir, run_id)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, p)
    except Exception:
        pass


def sha256_file(path: str) -> str:
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return ""


def _empty(project_dir: str, run_id: str) -> Dict:
    now = datetime.now().isoformat()
    return {"run_id": str(run_id or ""), "project": os.path.basename(project_dir),
            "created_at": now, "updated_at": now, "artifacts": {}, "approvals": {}}


def record_artifact(project_dir: str, run_id: str, stage: str, agent: str, path: str) -> Dict:
    """Record (or refresh) one artifact for this run with its content hash."""
    if not run_id:
        return {}
    d = _load(project_dir, run_id) or _empty(project_dir, run_id)
    d.setdefault("artifacts", {})
    key = f"{stage}/{agent}"
    d["artifacts"][key] = {"path": str(path), "sha256": sha256_file(path),
                           "at": datetime.now().isoformat()}
    d["updated_at"] = datetime.now().isoformat()
    _save(project_dir, run_id, d)
    return d["artifacts"][key]


def record_approval(project_dir: str, run_id: str, stage: str, agent: str,
                    decision: str, artifact_sha256: str = "", notes: str = "") -> Dict:
    """Record one approval bound to the run (and artifact digest when available)."""
    if not run_id:
        return {}
    d = _load(project_dir, run_id) or _empty(project_dir, run_id)
    d.setdefault("approvals", {})
    key = f"{stage}/{agent}"
    rec = {"decision": str(decision or ""), "run_id": str(run_id),
           "artifact_sha256": str(artifact_sha256 or ""), "at": datetime.now().isoformat(),
           "notes": str(notes or "")[:500]}
    d["approvals"][key] = rec
    d["updated_at"] = datetime.now().isoformat()
    _save(project_dir, run_id, d)
    return rec


def get(project_dir: str, run_id: str) -> Dict:
    return _load(project_dir, run_id)


def has(project_dir: str, run_id: str) -> bool:
    return bool(run_id) and os.path.isfile(_path(project_dir, run_id))


def verify_artifact(project_dir: str, run_id: str, path: str) -> bool:
    """True iff `path` is recorded for THIS run and its content hash still matches."""
    d = _load(project_dir, run_id)
    for rec in (d.get("artifacts") or {}).values():
        if os.path.abspath(str(rec.get("path", ""))) == os.path.abspath(str(path)):
            cur = sha256_file(path)
            return bool(cur) and cur == rec.get("sha256")
    return False


def verify_any_artifact(project_dir: str, run_id: str) -> bool:
    """True iff the run has >=1 recorded artifact whose hash still matches on disk."""
    d = _load(project_dir, run_id)
    for rec in (d.get("artifacts") or {}).values():
        p = str(rec.get("path", ""))
        if p and os.path.isfile(p) and sha256_file(p) == rec.get("sha256"):
            return True
    return False


def approval_for(project_dir: str, run_id: str, stage: str, agent: str) -> Optional[Dict]:
    rec = (_load(project_dir, run_id).get("approvals") or {}).get(f"{stage}/{agent}")
    return rec or None
