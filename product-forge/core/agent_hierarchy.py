"""
Agent hierarchy (parent -> sub-agents) — single source of truth.

Merges `config/agent-hierarchy.json` with any `sub_agents/sub_flow` declared in
`pipeline-definition.json`, so a sub-agent's model can be inherited from its
parent automatically (no hand-maintained per-agent mapping).

Used by `core/orchestrator/model_router.py` at resolution time.
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
from typing import Dict, List, Optional

_REPO = str(_PF_ROOT)
_CFG = os.path.join(_REPO, "config", "agent-hierarchy.json")
_PIPE = os.path.join(_REPO, "pipeline-definition.json")
_cache: Optional[Dict[str, List[str]]] = None


def _load() -> Dict[str, List[str]]:
    global _cache
    if _cache is not None:
        return _cache
    parents: Dict[str, List[str]] = {}
    try:
        with open(_CFG, "r", encoding="utf-8") as f:
            for p, subs in ((json.load(f) or {}).get("parents") or {}).items():
                parents.setdefault(p, [])
                parents[p].extend(subs)
    except Exception:
        pass
    try:
        with open(_PIPE, "r", encoding="utf-8") as f:
            stages = (json.load(f) or {}).get("stages", {})
        for st in stages.values():
            for ag, cfg in (st.get("sub_agents") or {}).items():
                if isinstance(cfg, dict):
                    for sub in (cfg.get("sub_flow") or []):
                        parents.setdefault(ag, [])
                        if sub not in parents[ag]:
                            parents[ag].append(sub)
    except Exception:
        pass
    _cache = parents
    return parents


def parent_of(agent: str) -> Optional[str]:
    for p, subs in _load().items():
        if agent in subs:
            return p
    return None


def root_of(agent: str) -> str:
    seen = set()
    cur = agent
    while True:
        p = parent_of(cur)
        if not p or p in seen:
            return cur
        seen.add(cur)
        cur = p


def descendants(agent: str) -> List[str]:
    out, stack = set(), list(_load().get(agent, []))
    while stack:
        n = stack.pop()
        if n in out:
            continue
        out.add(n)
        stack.extend(_load().get(n, []))
    return sorted(out)


def parents() -> Dict[str, List[str]]:
    return {k: sorted(set(v)) for k, v in _load().items()}
