"""LIVE/OPS phase (BI-0021) — opt-in, post-deploy.

Stages 13 Monitor / 13a Incident / 13b Maintenance are **opt-in** via project config
(`project.json` → `"ops": {"enabled": true}`), so existing runs are unchanged.

Produces, per project:
  products/<project>/ops/ops-report.json     (monitor: SLO-ish signals + cost)
  products/<project>/ops/incidents.json      (incident records from critical defects)
  products/<project>/backlog items           (maintenance: recurring defects -> work items)
Emits `anomaly`/`escalation` events through core/event_bus.
"""
import json
import os
from datetime import datetime
from typing import Any, Dict, List

_AGENTS = ["post-production", "guardian", "observer", "maintenance", "finops", "performance"]


def enabled(project_dir: str) -> bool:
    try:
        with open(os.path.join(project_dir, "project.json"), "r", encoding="utf-8") as f:
            cfg = json.load(f) or {}
        return bool((cfg.get("ops") or {}).get("enabled"))
    except Exception:
        return False


def _rj(p: str, d: Any) -> Any:
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def _wj(p: str, data: Any) -> None:
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    os.replace(tmp, p)


def monitor(project: str, project_dir: str) -> Dict:
    """Stage 13: collect post-deploy signals (defects, coverage, cost, build)."""
    report: Dict[str, Any] = {"project": project, "stage": "13-monitor",
                              "generated_at": datetime.now().isoformat()}
    try:
        from core.defect_loop import open_defects
        defects = open_defects(project) or []
    except Exception:
        defects = []
    report["open_defects"] = len(defects)
    report["critical_defects"] = [d.get("defect_id") for d in defects
                                  if str(d.get("severity", "")).lower() in ("critical", "high")]
    report["quality"] = _rj(os.path.join(project_dir, "quality-metrics.json"), {})
    report["budget"] = _rj(os.path.join(project_dir, "budget.json"), {})
    report["build"] = _rj(os.path.join(project_dir, "build-info.json"), {})
    report["status"] = "degraded" if report["critical_defects"] else "healthy"
    _wj(os.path.join(project_dir, "ops", "ops-report.json"), report)
    return report


def incident(project: str, project_dir: str, report: Dict) -> Dict:
    """Stage 13a: open incident records for critical defects and escalate."""
    path = os.path.join(project_dir, "ops", "incidents.json")
    incidents: List[Dict] = _rj(path, []) or []
    known = {i.get("defect_id") for i in incidents if i.get("status") == "open"}
    opened = []
    for did in report.get("critical_defects", []):
        if did in known:
            continue
        incidents.append({"incident_id": f"INC-{len(incidents)+1:04d}", "defect_id": did,
                          "status": "open", "opened_at": datetime.now().isoformat(),
                          "stage": "13a-incident"})
        opened.append(did)
    if opened:
        _wj(path, incidents)
        try:
            from core import event_bus
            event_bus.emit("escalation", project=project, reason="critical_defects",
                           defects=opened, source="ops_phase")
        except Exception:
            pass
    return {"opened": opened, "incidents": len(incidents)}


def maintenance(project: str, project_dir: str, report: Dict) -> Dict:
    """Stage 13b: promote recurring/known issues into the project backlog."""
    created = []
    try:
        from core import backlog
        if report.get("critical_defects"):
            for did in report["critical_defects"][:10]:
                it = backlog.ensure_item("project", project, external_id=f"ops:defect:{did}",
                                         title=f"Post-deploy: fix defect {did}",
                                         type_="bug", origin="pipeline", source="ops",
                                         body="Raised by the LIVE/OPS maintenance stage.")
                if it and it.get("status") == "new":
                    created.append(it.get("id"))
    except Exception:
        pass
    return {"created": created}


def run(executor) -> Dict:
    """Run the ops phase for a finished project run (called only when enabled)."""
    project = getattr(executor, "project", "")
    project_dir = getattr(executor, "project_dir", "")
    if not project or not project_dir or not enabled(project_dir):
        return {"enabled": False}
    rep = monitor(project, project_dir)
    inc = incident(project, project_dir, rep)
    mnt = maintenance(project, project_dir, rep)
    out = {"enabled": True, "monitor": rep.get("status"), "incidents": inc,
           "maintenance": mnt, "agents": _AGENTS}
    _wj(os.path.join(project_dir, "ops", "ops-run.json"),
        {**out, "at": datetime.now().isoformat()})
    return out
