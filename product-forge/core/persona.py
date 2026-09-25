"""
Owner persona — the human the auto-mode Human Proxy emulates.

Config: config/persona.json (default) merged with products/<project>/persona.json
(per-project overlay). Used by the `human` agent context and by backlog triage
(priority/accept decisions) so automation carries the owner's judgment.
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
from typing import Any, Dict

_REPO = str(_PF_ROOT)
_DEFAULT = os.path.join(_REPO, "config", "persona.json")


def _rj(p: str) -> Dict:
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _merge(a: Dict, b: Dict) -> Dict:
    out = dict(a)
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = {**out[k], **v}
        else:
            out[k] = v
    return out


def load(project_dir: str = "") -> Dict[str, Any]:
    base = _rj(_DEFAULT)
    if project_dir:
        base = _merge(base, _rj(os.path.join(project_dir, "persona.json")))
    return base


def brief(project_dir: str = "") -> str:
    """Compact persona brief for the Human Proxy / PO prompts."""
    p = load(project_dir)
    kn = p.get("knobs", {})
    return (f"Owner persona: {p.get('summary','')}\n"
            f"Knobs: {json.dumps(kn)}\n"
            f"Must: {p.get('must', [])}\nMust NOT: {p.get('must_not', [])}")
