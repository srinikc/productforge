"""Runtime agent instruction overlays — append/adjust an agent's instructions on the fly.

Lets you ADD detail to any agent (existing or new) WITHOUT editing code or its card:
  products/<project>/agent-overlays.json
    { "design": {"instructions": "...", "updated_at": ..., "by": ...},
      "architect": {...}, "*": {...} }        # "*" = applies to every agent

Composed into the prompt by agent_runner (after the base instructions). Because the
overlay changes the prompt, it naturally changes the prompt-cache key (no stale hits).

Owner: this module (single writer). Global defaults may also live in
config/agent-overlays.json (applied before the project overlay).
"""
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
from datetime import datetime
from typing import Dict, Optional

REPO = str(_PF_ROOT)
_GLOBAL = os.path.join(REPO, "config", "agent-overlays.json")
_FILENAME = "agent-overlays.json"


def _rj(p: str, d):
    try:
        with open(p, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return d


def _wj(p: str, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def project_path(project_dir: str) -> str:
    return os.path.join(project_dir, _FILENAME)


def load(project_dir: str) -> Dict:
    merged: Dict = {}
    g = _rj(_GLOBAL, {}) or {}
    if isinstance(g, dict):
        merged.update(g)
    p = _rj(project_path(project_dir), {}) or {}
    if isinstance(p, dict):
        for k, v in p.items():
            merged[k] = v            # project overlay wins per-agent
    return merged


def set_overlay(project_dir: str, agent_id: str, instructions: str,
                by: str = "operator", mode: str = "append") -> Dict:
    """Add/replace an agent overlay. ``mode`` = append | replace."""
    path = project_path(project_dir)
    data = _rj(path, {}) or {}
    if not isinstance(data, dict):
        data = {}
    cur = data.get(agent_id) or {}
    if mode == "append" and cur.get("instructions"):
        text = cur["instructions"].rstrip() + "\n" + (instructions or "").strip()
    else:
        text = (instructions or "").strip()
    data[agent_id] = {"instructions": text, "updated_at": datetime.now().isoformat(), "by": by}
    _wj(path, data)
    return data[agent_id]


def clear_overlay(project_dir: str, agent_id: str) -> bool:
    path = project_path(project_dir)
    data = _rj(path, {}) or {}
    if isinstance(data, dict) and agent_id in data:
        data.pop(agent_id, None)
        _wj(path, data)
        return True
    return False


def for_agent(project_dir: str, agent_id: str) -> str:
    """The overlay text to append to ``agent_id``'s instructions ('' if none)."""
    try:
        data = load(project_dir)
        parts = []
        star = data.get("*") or {}
        if star.get("instructions"):
            parts.append(str(star["instructions"]).strip())
        own = data.get(agent_id) or {}
        if own.get("instructions"):
            parts.append(str(own["instructions"]).strip())
        return "\n".join(p for p in parts if p)
    except Exception:
        return ""
