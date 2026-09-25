"""
Canonical status + dependency model (standardization).

One vocabulary used at every level:
  phase -> stage -> agent

Statuses:
  pending     not started
  blocked     dependencies not satisfied (won't run yet)
  running     in progress
  completed    done
  failed       errored
  skipped      intentionally not run
  stale        was completed, but an upstream dependency changed -> needs rerun
  needs_retry  ran but must be re-run (compliance/validation)
  escalated    needs human

A dependency is "satisfied" when it is COMPLETED or SKIPPED (skipped = intentionally
not needed). Anything else leaves dependents BLOCKED.
"""
from enum import Enum
from typing import Dict, List, Optional


class Status(str, Enum):
    PENDING = "pending"
    BLOCKED = "blocked"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    STALE = "stale"
    NEEDS_RETRY = "needs_retry"
    ESCALATED = "escalated"


SATISFIED = {Status.COMPLETED.value, Status.SKIPPED.value}
RUNNABLE = {Status.PENDING.value, Status.STALE.value}
TERMINAL = {Status.COMPLETED.value, Status.FAILED.value, Status.SKIPPED.value, Status.STALE.value}
ACTIVE = {Status.RUNNING.value}

_ALIASES = {
    "ready": Status.PENDING.value,
    "done": Status.COMPLETED.value,
    "pass": Status.COMPLETED.value,
    "passed": Status.COMPLETED.value,
    "error": Status.FAILED.value,
    "retry": Status.NEEDS_RETRY.value,
}


def norm(value) -> str:
    """Normalize any legacy status string/enum into the canonical vocabulary."""
    if isinstance(value, Status):
        return value.value
    v = str(value or "").strip().lower()
    if v in {s.value for s in Status}:
        return v
    return _ALIASES.get(v, Status.PENDING.value)


def dependency_satisfied(status) -> bool:
    return norm(status) in SATISFIED


def unmet_dependencies(stage_id: str, deps: List[str], stage_status: Dict[str, str]) -> List[str]:
    """Return deps that are not yet satisfied (blocking this stage)."""
    return [d for d in (deps or []) if not dependency_satisfied(stage_status.get(d, "pending"))]


def effective_status(raw_status, unmet: List[str]) -> str:
    """A pending stage with unmet deps is BLOCKED; otherwise its raw status."""
    s = norm(raw_status)
    if s in RUNNABLE and unmet:
        return Status.BLOCKED.value
    return s


def build_report(dag, execution=None, agent_deps: Optional[Dict] = None,
                 stage_agents: Optional[Dict] = None) -> Dict:
    """Standardized phase/stage/agent status snapshot.

    `agent_deps` maps {stage_id: {agent: [prerequisite agents]}}; when given, an agent
    whose prerequisite agent has not completed is reported BLOCKED.
    `stage_agents` maps {stage_id: [agent ids]} so agents that have NOT run yet are
    listed as PENDING (or BLOCKED) instead of being omitted.
    Never-run agents are PENDING; only previously-completed agents invalidated by an
    upstream change are STALE.
    """
    raw_status = {}
    if dag is not None:
        for sid, st in dag.states.items():
            raw_status[sid] = getattr(st.status, "value", str(st.status))

    stage_execs = {}
    try:
        stage_execs = dict(getattr(execution, "stage_executions", {}) or {}) if execution else {}
    except Exception:
        stage_execs = {}

    stages: Dict[str, Dict] = {}
    counts: Dict[str, int] = {}
    agent_counts: Dict[str, int] = {}

    def _tally(bucket, key):
        bucket[key] = bucket.get(key, 0) + 1

    for sid, stagedef in (getattr(dag, "stages", {}) or {}).items():
        deps = list(getattr(stagedef, "depends_on", []) or [])
        unmet = unmet_dependencies(sid, deps, raw_status)
        raw_stage = norm(raw_status.get(sid, "pending"))
        status = effective_status(raw_stage, unmet)
        _tally(counts, status)

        execs = stage_execs.get(sid) or []
        by_id = {getattr(e, "agent_id", ""): e for e in execs}
        stage_agent_status = {aid: norm(getattr(e, "status", "")) for aid, e in by_id.items()}
        adeps = (agent_deps or {}).get(sid, {}) or {}

        # All agents that belong to this stage (from the definition) + any executed ones.
        agent_ids = list((stage_agents or {}).get(sid, []) or [])
        for aid in by_id:
            if aid and aid not in agent_ids:
                agent_ids.append(aid)

        agents = []
        for aid in agent_ids:
            e = by_id.get(aid)
            agent_unmet = [p for p in (adeps.get(aid, []) or [])
                           if stage_agent_status.get(p, "pending") not in SATISFIED]
            if e is not None:
                a_status = norm(getattr(e, "status", "completed"))
                # previously completed, now invalidated by an upstream change
                if a_status == Status.COMPLETED.value and raw_stage == Status.STALE.value:
                    a_status = Status.STALE.value
            else:
                a_status = Status.PENDING.value  # never run
            if a_status in RUNNABLE and (unmet or agent_unmet):
                a_status = Status.BLOCKED.value
            agents.append({
                "agent_id": aid,
                "status": a_status,
                "model": getattr(e, "selected_model", "") if e else "",
                "provider": getattr(e, "selected_provider", "") if e else "",
                "tokens": getattr(e, "total_tokens", 0) if e else 0,
                "compliance_passed": bool(getattr(e, "compliance_passed", False)) if e else False,
                "unmet_dependencies": agent_unmet,
                "error": getattr(e, "error", "") if e else "",
                "started_at": getattr(e, "started_at", "") if e else "",
                "completed_at": getattr(e, "completed_at", "") if e else "",
            })
            _tally(agent_counts, a_status)

        stages[sid] = {
            "id": sid,
            "name": getattr(stagedef, "name", sid),
            "status": status,
            "depends_on": deps,
            "unmet_dependencies": unmet,
            "agents": agents,
        }

    return {
        "phase": getattr(getattr(execution, "phase", None), "value", None) if execution else None,
        "current_stage": getattr(execution, "current_stage", "") if execution else "",
        "stages": stages,
        "summary": {"stages": counts, "agents": agent_counts,
                    "blocked": counts.get(Status.BLOCKED.value, 0),
                    "stale": counts.get(Status.STALE.value, 0)},
    }
