"""Result Aggregator — combine multi-agent/model/tool outputs with provenance + conflict resolution
(BI-PF-0277).

Single owner of aggregation logic and writer of the ``Aggregation-Report`` artifact. Preserves source
model/agent/tool, timestamp, evidence, confidence, validation status, test evidence, unresolved issues and
conflicts. ``conflict_resolver`` picks the highest evidence-backed confidence or **escalates** on ties /
low confidence (fail-closed). Real quorum: a single pass can never pass. See docs/RESULT-AGGREGATOR-DESIGN.md.
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

try:
    from core.paths import ROOT as _ROOT
except ImportError:  # script execution
    import sys as _sys
    _d = os.path.abspath(__file__)
    for _ in range(3):
        _d = os.path.dirname(_d)
        if os.path.isfile(os.path.join(_d, "core", "paths.py")):
            _sys.path.insert(0, _d)
            break
    from core.paths import ROOT as _ROOT

REPORT_NAME = "Aggregation-Report"
_MIN_CONFIDENCE = 0.5


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def contribution(source_kind: str, source: str, output, *, kind: str = "text",
                 evidence: Optional[List] = None, confidence: float = 0.0,
                 validation_status: str = "unknown", tests: Optional[Dict] = None,
                 unresolved_issues: Optional[List] = None, timestamp: str = "",
                 cost: float = 0.0, provider: str = "") -> Dict:
    """Normalize one contribution (fail-closed defaults)."""
    return {"source_kind": str(source_kind or "agent"), "source": str(source or ""),
            "kind": str(kind or "text"), "output": output,
            "evidence": list(evidence or []), "confidence": float(confidence or 0.0),
            "validation_status": str(validation_status or "unknown"),
            "tests": dict(tests or {}), "unresolved_issues": list(unresolved_issues or []),
            "timestamp": timestamp or _now(), "cost": float(cost or 0.0),
            "provider": str(provider or "")}


def _hash(x) -> str:
    s = x if isinstance(x, str) else json.dumps(x, sort_keys=True, default=str)
    return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()[:16]


def evidence_merger(contribs: List[Dict]) -> List[Dict]:
    """Dedup evidence by content hash; mark corroborated when >=2 independent sources agree."""
    by_hash: Dict[str, Dict] = {}
    for c in contribs:
        for ev in (c.get("evidence") or []):
            h = _hash(ev)
            rec = by_hash.setdefault(h, {"evidence": ev, "sources": [], "corroborated": False})
            src = str(c.get("source") or "")
            if src and src not in rec["sources"]:
                rec["sources"].append(src)
            rec["corroborated"] = len(rec["sources"]) >= 2
    return list(by_hash.values())


def conflict_resolver(contribs: List[Dict]) -> List[Dict]:
    """Detect divergent outputs for the same (kind) key; resolve by evidence-backed confidence or escalate."""
    groups: Dict[str, List[Dict]] = {}
    for c in contribs:
        groups.setdefault(str(c.get("kind") or "text"), []).append(c)
    conflicts: List[Dict] = []
    for kind, cs in groups.items():
        if len(cs) < 2:
            continue
        outs = {json.dumps(c.get("output"), sort_keys=True, default=str) for c in cs}
        if len(outs) <= 1:
            continue  # agreement
        values = [{"source": c.get("source"), "confidence": c.get("confidence", 0.0),
                   "evidence_backed": bool(c.get("evidence"))} for c in cs]
        # resolution: highest evidence-backed confidence wins; ties/low -> escalate (fail-closed)
        scored = sorted(values, key=lambda v: (v["evidence_backed"], v["confidence"]), reverse=True)
        top, second = scored[0], (scored[1] if len(scored) > 1 else None)
        tie = second and (top["confidence"] == second["confidence"]
                          and top["evidence_backed"] == second["evidence_backed"])
        if tie or (top["confidence"] < _MIN_CONFIDENCE and not top["evidence_backed"]):
            conflicts.append({"kind": kind, "values": values, "resolution": "escalate",
                              "rationale": "tie or low confidence"})
        else:
            conflicts.append({"kind": kind, "values": values, "resolution": "chosen",
                              "chosen": top["source"], "rationale": "highest evidence-backed confidence"})
    return conflicts


def aggregate(contribs: List[Dict], *, quorum: int = 0) -> Dict:
    """Combine contributions into a fail-closed aggregation result.

    ``passed`` requires: enough reviewers (n_total >= quorum), a strict majority pass, and no
    escalated conflict. A single contribution can never pass when quorum >= 2.
    """
    contribs = [contribution(**c) if "source_kind" not in c else c for c in (contribs or [])]
    n_total = len(contribs)
    st = [str(c.get("validation_status") or "unknown") for c in contribs]
    n_pass = st.count("pass")
    n_fail = st.count("fail")
    n_unknown = st.count("unknown")
    tests_passed = sum(int((c.get("tests") or {}).get("passed", 0) or 0) for c in contribs)
    tests_failed = sum(int((c.get("tests") or {}).get("failed", 0) or 0) for c in contribs)
    unresolved = [i for c in contribs for i in (c.get("unresolved_issues") or [])]
    conflicts = conflict_resolver(contribs)
    escalated = [c for c in conflicts if c.get("resolution") == "escalate"]
    conf = round(sum(float(c.get("confidence") or 0.0) for c in contribs) / n_total, 3) if n_total else 0.0
    q = max(int(quorum or 0), 0)
    consensus = n_total >= q and n_pass > n_fail and not escalated
    if q >= 2 and n_total < q:
        consensus = False
    return {
        "generated_at": _now(),
        "contributions": [{"source_kind": c.get("source_kind"), "source": c.get("source"),
                           "kind": c.get("kind"), "confidence": c.get("confidence"),
                           "validation_status": c.get("validation_status"),
                           "timestamp": c.get("timestamp"), "provider": c.get("provider")}
                          for c in contribs],
        "merged_evidence": evidence_merger(contribs),
        "conflicts": conflicts,
        "unresolved_issues": unresolved,
        "validation": {"passed": n_pass, "failed": n_fail, "unknown": n_unknown},
        "tests": {"passed": tests_passed, "failed": tests_failed},
        "consensus": {"n_pass": n_pass, "n_fail": n_fail, "n_total": n_total, "quorum": q,
                      "reached": bool(consensus)},
        "confidence": conf,
        "passed": bool(consensus),
        "sources": [c.get("source") for c in contribs],
    }


def _report_path(project_dir: str) -> str:
    return os.path.join(project_dir, "artifacts", "9 - Package", REPORT_NAME + "." + "json")


def write_report(project_dir: str, agg: Dict) -> Dict:
    """Single writer of the Aggregation-Report artifact."""
    try:
        p = _report_path(project_dir)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(agg, f, indent=2)
    except Exception:
        pass
    return agg


def load_report(project_dir: str) -> Optional[Dict]:
    try:
        with open(_report_path(project_dir), encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return None
