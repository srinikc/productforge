"""Orchestration event bus + context (BI-0020).

Signals emitted by the runtime (stuck / anomaly / conflict / coverage_gap / escalation / ...)
are appended to a single JSONL stream and routed by `orchestration_context`.

Store: products/.orchestration/events.jsonl  (append-only; global)
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
from typing import Any, Callable, Dict, List, Optional

_REPO = str(_PF_ROOT)
_EVENTS = os.path.join(_REPO, "products", ".orchestration", "events.jsonl")

KINDS = ("stuck", "anomaly", "compliance_exhausted", "agent_conflict",
         "coverage_gap", "scope_change", "escalation", "follow_up_due")

_HANDLERS: Dict[str, List[Callable]] = {}


def on(kind: str, fn: Callable) -> None:
    _HANDLERS.setdefault(kind, []).append(fn)


def emit(kind: str, **payload) -> Dict:
    """Append one event and dispatch in-process handlers (never raises)."""
    ev = {"kind": kind, "at": datetime.now().isoformat(), **payload}
    try:
        os.makedirs(os.path.dirname(_EVENTS), exist_ok=True)
        with open(_EVENTS, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass
    for fn in _HANDLERS.get(kind, []) + _HANDLERS.get("*", []):
        try:
            fn(ev)
        except Exception:
            pass
    # Coordinator routing (policy-first) for actionable signals — lazy import avoids a cycle.
    if kind in ("stuck", "anomaly", "compliance_exhausted", "agent_conflict",
                "coverage_gap", "scope_change", "escalation"):
        try:
            from core import orchestration_context as _oc
            _oc.route(ev)
        except Exception:
            pass
    return ev


def recent(limit: int = 50, kind: str = "") -> List[Dict]:
    out: List[Dict] = []
    try:
        with open(_EVENTS, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if kind and ev.get("kind") != kind:
                    continue
                out.append(ev)
    except Exception:
        return []
    return out[-limit:]
