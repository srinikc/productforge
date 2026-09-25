"""Forced Convergence - ensures pipeline doesn't loop indefinitely.

Implements the Auto-Company pattern: when the Product Forge supervisor
can't decide what to do next, forced convergence kicks in to
either escalate, skip, or auto-resolve based on constitution rules.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ConvergenceAction:
    action: str  # skip, escalate, force_complete, auto_resolve, terminate
    reason: str
    stage: Optional[str] = None
    timestamp: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConvergenceState:
    project: str
    consecutive_noops: int = 0
    max_noops: int = 5
    actions_taken: List[ConvergenceAction] = field(default_factory=list)
    terminated: bool = False
    termination_reason: str = ""


def check_convergence(state: ConvergenceState, current_action: Optional[str] = None) -> Optional[ConvergenceAction]:
    """Check if forced convergence should be triggered."""
    if state.terminated:
        return None

    if current_action is None or current_action == "none":
        state.consecutive_noops += 1
    else:
        state.consecutive_noops = 0

    if state.consecutive_noops >= state.max_noops:
        action = ConvergenceAction(
            action="terminate",
            reason=f"No progress after {state.consecutive_noops} consecutive idle cycles",
            timestamp=datetime.now().isoformat(),
        )
        state.actions_taken.append(action)
        state.terminated = True
        state.termination_reason = action.reason
        return action

    if state.consecutive_noops >= 3:
        action = ConvergenceAction(
            action="escalate",
            reason=f"Possible stall: {state.consecutive_noops} idle cycles, needs human input",
            timestamp=datetime.now().isoformat(),
        )
        state.actions_taken.append(action)
        return action

    return None


def force_complete_stage(state: ConvergenceState, stage: str, reason: str) -> ConvergenceAction:
    """Force a stage to complete when stuck."""
    action = ConvergenceAction(
        action="force_complete",
        reason=reason,
        stage=stage,
        timestamp=datetime.now().isoformat(),
    )
    state.actions_taken.append(action)
    state.consecutive_noops = 0
    return action


def skip_stage(state: ConvergenceState, stage: str, reason: str) -> ConvergenceAction:
    """Skip a stuck stage."""
    action = ConvergenceAction(
        action="skip",
        reason=reason,
        stage=stage,
        timestamp=datetime.now().isoformat(),
    )
    state.actions_taken.append(action)
    state.consecutive_noops = 0
    return action


def auto_resolve(state: ConvergenceState, stage: str, resolution: str) -> ConvergenceAction:
    """Auto-resolve a minor issue without human intervention."""
    action = ConvergenceAction(
        action="auto_resolve",
        reason=resolution,
        stage=stage,
        timestamp=datetime.now().isoformat(),
    )
    state.actions_taken.append(action)
    state.consecutive_noops = 0
    return action


def convergence_to_dict(state: ConvergenceState) -> Dict[str, Any]:
    return {
        "project": state.project,
        "consecutive_noops": state.consecutive_noops,
        "max_noops": state.max_noops,
        "terminated": state.terminated,
        "termination_reason": state.termination_reason,
        "actions_count": len(state.actions_taken),
        "recent_actions": [
            {"action": a.action, "reason": a.reason, "stage": a.stage, "timestamp": a.timestamp}
            for a in state.actions_taken[-10:]
        ],
    }
