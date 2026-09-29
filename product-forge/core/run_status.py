"""Single-writer run status.

Maintains products/<project>/run-status.json with an accurate current state
(phase/stage/agents) and is updated ONLY from lifecycle transitions, so it always
matches events.jsonl. Consumed by the dashboard/api.

Owner: this module. Fed by: run_entry (run_started), job_manager (run_completed/
run_failed), stage_runner._emit_lifecycle (stage_*/agent_*).
"""
import json
import os
from datetime import datetime
from typing import Dict

FILENAME = "run-status.json"

_AGENT_STATE = {"agent_started": "running", "agent_completed": "completed",
                "agent_failed": "failed", "agent_blocked": "blocked",
                "agent_stage_changed": "changed"}


def path(project_dir: str) -> str:
    return os.path.join(project_dir, FILENAME)


def load(project_dir: str) -> Dict:
    try:
        with open(path(project_dir), "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _save(project_dir: str, d: Dict) -> None:
    tmp = path(project_dir) + ".tmp"
    try:
        os.makedirs(project_dir, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path(project_dir))
    except Exception:
        pass
    # Human mirror so PROJECT-STATUS.md is never stale (same single writer).
    try:
        stages = d.get("stages") or {}
        agents = d.get("agents") or {}
        lines = [
            f"# PROJECT STATUS — {d.get('project', '')}",
            f"- **State:** {d.get('state', 'idle')}",
            f"- **Run:** {d.get('run_id', '')}",
            f"- **Current stage:** {d.get('current_stage', '') or '-'}",
            f"- **Updated:** {d.get('updated_at', '')}",
            "", "## Stages",
        ]
        for sid, st in stages.items():
            lines.append(f"- {sid}: {st}")
        lines += ["", "## Agents"]
        for a, st in agents.items():
            lines.append(f"- {a}: {st}")
        with open(os.path.join(project_dir, "PROJECT-STATUS.md"), "w",
                  encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except Exception:
        pass


def update(project_dir: str, event_type: str, *, run_id: str = "", stage: str = "",
           agent: str = "", status: str = "", **_fields) -> Dict:
    d = load(project_dir)
    d.setdefault("project", os.path.basename(project_dir.rstrip("/\\")))
    d.setdefault("stages", {})
    d.setdefault("agents", {})
    if run_id:
        d["run_id"] = run_id
    d["updated_at"] = datetime.now().isoformat()
    et = str(event_type)
    if et == "run_started":
        d["state"] = "running"
    elif et in ("run_completed", "run_failed"):
        final = "completed" if et == "run_completed" else "failed"
        d["state"] = final
        d["current_stage"] = ""
        # BI-PF-0234: reconcile leftovers so the derived status cannot disagree with
        # the terminal state (e.g. state=failed while stages still show 'running').
        for _s, _st in list((d.get("stages") or {}).items()):
            if _st == "running":
                d["stages"][_s] = "interrupted"
        for _a, _st in list((d.get("agents") or {}).items()):
            if _st == "running":
                d["agents"][_a] = "failed" if final == "failed" else "completed"
    elif et == "stage_started":
        d["stages"][stage] = "running"
        d["current_stage"] = stage
    elif et == "stage_completed":
        d["stages"][stage] = "completed"
        if d.get("current_stage") == stage:
            d["current_stage"] = ""
    elif et == "stage_failed":
        d["stages"][stage] = "failed"
        if d.get("current_stage") == stage:
            d["current_stage"] = ""
    elif et in _AGENT_STATE:
        d["agents"][f"{stage}:{agent}"] = status or _AGENT_STATE[et]
    _save(project_dir, d)
    return d


def summary(project_dir: str) -> Dict:
    d = load(project_dir)
    stages = d.get("stages") or {}
    return {
        "state": d.get("state", "idle"),
        "run_id": d.get("run_id", ""),
        "current_stage": d.get("current_stage", ""),
        "stages_completed": sum(1 for v in stages.values() if v == "completed"),
        "stages_failed": sum(1 for v in stages.values() if v == "failed"),
        "agents_running": sum(1 for v in (d.get("agents") or {}).values() if v == "running"),
        "agents_blocked": sum(1 for v in (d.get("agents") or {}).values() if v == "blocked"),
        "updated_at": d.get("updated_at", ""),
    }
