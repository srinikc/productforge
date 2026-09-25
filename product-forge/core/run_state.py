"""Run linkage + resume reconciliation (preserve-first).

Problems this solves:
  * multiple runs over days leave approvals/artifacts with NO run linkage, so the
    story is untraceable (which run produced what);
  * a restart resets stage statuses while artifacts/approvals from a prior run
    remain -> state and disk disagree, and finished work is needlessly redone.

This module NEVER deletes user data. It (a) records each run attempt in
``<project>/pipeline-runs.json`` with a run_id, (b) stamps approvals with the
run_id that created them, and (c) reconciles ``pipeline-state.json`` so stages
that already have a fully-approved approval set + real artifacts are marked
completed (resume then skips them).
"""
import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Set

RUNS_FILENAME = "pipeline-runs.json"


def _rj(path: str, default):
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return default


def _wj(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _approval_files(project_dir: str) -> List[str]:
    base = os.path.join(project_dir, "approvals")
    out: List[str] = []
    if not os.path.isdir(base):
        return out
    for dp, _dn, fs in os.walk(base):
        for fn in fs:
            if fn.endswith(".json"):
                out.append(os.path.join(dp, fn))
    return sorted(out)


def approvals_by_stage(project_dir: str) -> Dict[str, List[Dict]]:
    out: Dict[str, List[Dict]] = {}
    for p in _approval_files(project_dir):
        d = _rj(p, None)
        if not isinstance(d, dict):
            continue
        sid = str(d.get("stage_id") or "")
        if not sid:
            continue
        out.setdefault(sid, []).append({
            "agent": d.get("agent_id"), "status": d.get("status"),
            "run_id": d.get("run_id", ""), "created_at": d.get("created_at", ""),
            "approved_at": d.get("approved_at", ""), "path": p,
        })
    return out


def _stage_has_artifacts(project_dir: str, stage_id: str) -> bool:
    try:
        from core import stage_paths as _sp
        d = _sp.find_stage_dir(project_dir, stage_id)
        if not os.path.isdir(d):
            return False
        return any(f.endswith("-output.md") or f == "_stage.json"
                   for f in os.listdir(d))
    except Exception:
        return False


def reconciled_completed(project_dir: str) -> Set[str]:
    """Stages whose EVERY approval is approved AND that have artifacts on disk."""
    done: Set[str] = set()
    for sid, recs in approvals_by_stage(project_dir).items():
        if not recs:
            continue
        if all(str(r.get("status") or "").lower() == "approved" for r in recs) \
                and _stage_has_artifacts(project_dir, sid):
            done.add(sid)
    return done


def record_run(project_dir: str, run_id: str, resumed_from: str = "",
               stages_completed: Optional[List[str]] = None,
               stopped_run: str = "") -> Dict:
    """Append/update this run attempt in pipeline-runs.json."""
    path = os.path.join(project_dir, RUNS_FILENAME)
    reg = _rj(path, {"project": os.path.basename(project_dir), "runs": []})
    if not isinstance(reg, dict):
        reg = {"project": os.path.basename(project_dir), "runs": []}
    runs = reg.setdefault("runs", [])
    entry = next((r for r in runs if r.get("run_id") == run_id), None)
    if entry is None:
        entry = {"run_id": run_id, "started_at": datetime.now().isoformat(),
                 "resumed_from": resumed_from, "stopped_run": stopped_run,
                 "stages_completed": list(stages_completed or [])}
        runs.append(entry)
    else:
        if resumed_from:
            entry["resumed_from"] = resumed_from
        if stopped_run:
            entry["stopped_run"] = stopped_run
        if stages_completed is not None:
            entry["stages_completed"] = list(stages_completed)
        entry["updated_at"] = datetime.now().isoformat()
    _wj(path, reg)
    return entry


def reconcile(project_dir: str, run_id: str = "", stopped_run: str = "") -> Dict:
    """Preserve-first reconciliation of pipeline-state.json from approvals+artifacts.

    Marks stages with a fully-approved approval set + artifacts as completed, and
    records the run attempt. Returns a report. Never deletes anything.
    """
    report = {"run_id": run_id, "marked_completed": [], "state_updated": False}
    state_path = os.path.join(project_dir, "pipeline-state.json")
    state = _rj(state_path, None)
    done = reconciled_completed(project_dir)

    if isinstance(state, dict):
        stages = state.setdefault("stages", {})
        for sid in sorted(done):
            info = stages.get(sid)
            if not isinstance(info, dict):
                info = {"status": "pending", "started_at": "", "completed_at": "", "error": ""}
                stages[sid] = info
            if info.get("status") != "completed":
                info["status"] = "completed"
                info.setdefault("completed_at", datetime.now().isoformat())
                info["reconciled"] = True
                report["marked_completed"].append(sid)
        if run_id:
            state["run_id"] = run_id
        state["updated_at"] = datetime.now().isoformat()
        _wj(state_path, state)
        report["state_updated"] = True

    if run_id:
        record_run(project_dir, run_id, resumed_from=(state or {}).get("run_id", "")
                   if isinstance(state, dict) else "",
                   stages_completed=sorted(done), stopped_run=stopped_run)
    return report


def stamp_approval(approval_path: str, run_id: str) -> None:
    """Add the creating run_id to an approval record (idempotent)."""
    d = _rj(approval_path, None)
    if isinstance(d, dict) and run_id and d.get("run_id") != run_id:
        d["run_id"] = run_id
        _wj(approval_path, d)


def _norm(run_id: str) -> str:
    r = str(run_id or "")
    m = re.match(r"^(?:pipeline|run)-(\d+)$", r)
    return f"run-{m.group(1)}" if m else r


def _known_runs(project_dir: str) -> List[Dict]:
    """Run registry + the execution report, as [{run_id, started, ended}] windows."""
    out: List[Dict] = []
    reg = _rj(os.path.join(project_dir, RUNS_FILENAME), None)
    for r in ((reg or {}).get("runs") or []):
        out.append({"run_id": _norm(r.get("run_id")), "started": r.get("started_at", ""),
                    "ended": r.get("updated_at") or r.get("completed_at") or ""})
    rep = _rj(os.path.join(project_dir, "pipeline-execution-report.json"), None)
    if isinstance(rep, dict) and (rep.get("pipeline_id") or rep.get("run_id")):
        out.append({"run_id": _norm(rep.get("pipeline_id") or rep.get("run_id")),
                    "started": rep.get("started_at", ""), "ended": rep.get("completed_at", "")})
    # de-dup by run_id (keep widest window)
    merged: Dict[str, Dict] = {}
    for r in out:
        cur = merged.get(r["run_id"])
        if cur is None:
            merged[r["run_id"]] = r
        else:
            cur["started"] = min(x for x in (cur["started"], r["started"]) if x or True) \
                if cur["started"] else r["started"]
            cur["ended"] = max(cur["ended"], r["ended"])
    return list(merged.values())


def backfill_run_ids(project_dir: str) -> Dict:
    """Stamp approvals with a provable run_id, else 'legacy'. Never invents ids."""
    runs = _known_runs(project_dir)
    report = {"stamped": {}, "legacy": []}
    for p in _approval_files(project_dir):
        d = _rj(p, None)
        if not isinstance(d, dict) or d.get("run_id"):
            continue
        created = str(d.get("created_at") or "")
        match = ""
        for r in runs:
            if r["started"] and created and r["started"] <= created and \
                    (not r["ended"] or created <= r["ended"]):
                match = r["run_id"]
                break
        if not match:
            match = "legacy"   # no recorded run provably covers this record — never guess
        if match == "legacy":
            report["legacy"].append(d.get("stage_id", ""))
        else:
            report["stamped"][d.get("stage_id", "")] = match
        d["run_id"] = match
        _wj(p, d)
    return report


def annotate_run(project_dir: str) -> Dict[str, str]:
    """Read-side: {approval_path: 'current'|'run X'|'legacy'} — non-blocking."""
    from core.lock_manager import LockManager
    try:
        info = LockManager(os.path.dirname(os.path.abspath(project_dir))).get_lock_info(
            os.path.basename(project_dir))
        current = _norm(getattr(info, "run_id", "")) if info else ""
    except Exception:
        current = ""
    out: Dict[str, str] = {}
    for p in _approval_files(project_dir):
        d = _rj(p, None)
        rid = _norm((d or {}).get("run_id"))
        if not rid or rid == "legacy":
            out[p] = "legacy"
        elif current and rid == current:
            out[p] = "current"
        else:
            out[p] = f"run {rid}"
    return out


def check_live_action(project_dir: str, run_id: str) -> Dict:
    """STRICT: an action on a LIVE run must match the active lock's run_id."""
    from core.lock_manager import LockManager
    try:
        info = LockManager(os.path.dirname(os.path.abspath(project_dir))).get_lock_info(
            os.path.basename(project_dir))
        current = _norm(getattr(info, "run_id", "")) if info else ""
    except Exception:
        current = ""
    if not current:
        return {"ok": True, "reason": "no live run"}
    if _norm(run_id) != current:
        return {"ok": False, "reason": f"action run {run_id or '(none)'} != live run {current}",
                "live_run": current}
    return {"ok": True, "live_run": current}
