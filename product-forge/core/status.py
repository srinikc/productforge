"""Canonical status vocabulary — ONE place for every status string in the pipeline.

Why: statuses were compared as raw strings in 400+ places (`"completed"`, `"pending"`,
`"approved"`, `"regenerate"`, ...). A typo or a new value silently breaks a gate.
Here each *domain* has one enum, and helpers normalize/validate.

This module is the single registry. Writers/readers should import from here rather
than hard-coding strings.
"""
from enum import Enum
from typing import Iterable, List, Optional


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    STALE = "stale"
    SKIPPED = "skipped"
    FAILED = "failed"


class AgentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class RunStatus(str, Enum):
    STARTED = "started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    APPROVED_WITH_CONDITIONS = "approved_with_conditions"
    CHANGES = "changes"
    REGENERATE = "regenerate"
    SKIP = "skip"
    REJECTED = "rejected"
    ABORT = "abort"
    EXPIRED = "expired"
    SNOOZED = "snoozed"
    WAITING = "waiting"


class ControlAction(str, Enum):
    RUN = "run"
    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"
    CANCEL = "cancel"


class GateOutcome(str, Enum):
    GO = "go"
    NO_GO = "no_go"
    CONDITIONAL = "conditional"


_DOMAINS = {
    "stage": StageStatus,
    "agent": AgentStatus,
    "run": RunStatus,
    "approval": ApprovalStatus,
    "control": ControlAction,
    "gate": GateOutcome,
}

# Any value that terminates an approval wait (kept explicit for gates).
APPROVAL_DECIDED = {
    ApprovalStatus.APPROVED.value, ApprovalStatus.APPROVED_WITH_CONDITIONS.value,
    ApprovalStatus.CHANGES.value, ApprovalStatus.REGENERATE.value,
    ApprovalStatus.SKIP.value, ApprovalStatus.REJECTED.value,
    ApprovalStatus.ABORT.value, ApprovalStatus.EXPIRED.value,
}


def values(domain: str) -> List[str]:
    e = _DOMAINS.get(domain)
    return [m.value for m in e] if e else []


def is_valid(domain: str, value: str) -> bool:
    return str(value) in values(domain)


def normalize(domain: str, value: str) -> str:
    """Lower/sanitize; map common aliases to a canonical value (keeps old data valid)."""
    v = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "done": "completed", "complete": "completed", "ok": "completed",
        "in_progress": "running", "active": "running", "queued": "pending", "new": "pending",
        "approve": "approved", "accepted": "approved", "approve_with_conditions":
            "approved_with_conditions", "no-go": "no_go", "nogo": "no_go",
        "cancelled": "cancel", "halt": "stop", "reset": "stale",
    }
    v = aliases.get(v, v)
    return v
