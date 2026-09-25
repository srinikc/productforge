"""
State Machine - Pipeline stage state machine.

Phase 1.1 (CRITICAL): Manages stage transitions and state validation.
"""
from enum import Enum
from typing import Optional


class StageStatus(str, Enum):
    """Status of a pipeline stage."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class PipelineStateMachine:
    """Manages valid state transitions for pipeline stages."""
    
    VALID_TRANSITIONS = {
        StageStatus.PENDING: [StageStatus.IN_PROGRESS, StageStatus.SKIPPED, StageStatus.BLOCKED],
        StageStatus.IN_PROGRESS: [StageStatus.COMPLETED, StageStatus.FAILED],
        StageStatus.COMPLETED: [],  # Terminal
        StageStatus.FAILED: [StageStatus.IN_PROGRESS, StageStatus.SKIPPED],  # Can retry or skip
        StageStatus.SKIPPED: [],  # Terminal
        StageStatus.BLOCKED: [StageStatus.PENDING, StageStatus.IN_PROGRESS],
    }
    
    def can_transition(self, from_status: str, to_status: str) -> bool:
        """Check if a state transition is valid."""
        try:
            from_enum = StageStatus(from_status)
            to_enum = StageStatus(to_status)
        except ValueError:
            return False
        
        return to_enum in self.VALID_TRANSITIONS.get(from_enum, [])
    
    def transition(self, current_status: str, new_status: str) -> bool:
        """
        Attempt to transition from current to new status.
        
        Returns:
            True if transition is valid, False otherwise
        """
        return self.can_transition(current_status, new_status)
    
    def is_terminal(self, status: str) -> bool:
        """Check if a status is terminal (no further transitions)."""
        try:
            status_enum = StageStatus(status)
        except ValueError:
            return False
        
        return len(self.VALID_TRANSITIONS.get(status_enum, [])) == 0
    
    def get_valid_next_states(self, current_status: str) -> list[str]:
        """Get list of valid next states from current status."""
        try:
            current_enum = StageStatus(current_status)
        except ValueError:
            return []
        
        return [s.value for s in self.VALID_TRANSITIONS.get(current_enum, [])]
    
    def get_progress(self, stages: dict) -> dict:
        """
        Calculate overall pipeline progress.
        
        Args:
            stages: Dict of stage_id -> {status: str, ...}
        
        Returns:
            Dict with progress info
        """
        if not stages:
            return {"total": 0, "completed": 0, "failed": 0, "in_progress": 0, "percent": 0}
        
        total = len(stages)
        completed = sum(1 for s in stages.values() if s.get("status") == StageStatus.COMPLETED.value)
        failed = sum(1 for s in stages.values() if s.get("status") == StageStatus.FAILED.value)
        in_progress = sum(1 for s in stages.values() if s.get("status") == StageStatus.IN_PROGRESS.value)
        skipped = sum(1 for s in stages.values() if s.get("status") == StageStatus.SKIPPED.value)
        blocked = sum(1 for s in stages.values() if s.get("status") == StageStatus.BLOCKED.value)
        
        finished = completed + skipped
        percent = (finished / total) * 100 if total > 0 else 0
        
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "skipped": skipped,
            "blocked": blocked,
            "percent": round(percent, 1),
        }
