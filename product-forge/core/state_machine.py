"""
State Machine
Project state management for concurrent multi-project execution
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum


class ProjectState(Enum):
    """Project execution states"""
    IDLE = "idle"  # Project exists but not queued
    QUEUED = "queued"  # In queue, waiting to run
    LOCKED = "locked"  # Lock acquired, preparing to run
    RUNNING = "running"  # Actively executing
    PAUSED = "paused"  # Temporarily paused
    COMPLETED = "completed"  # Pipeline completed successfully
    ERROR = "error"  # Pipeline failed
    CANCELLED = "cancelled"  # User cancelled


# Valid state transitions
VALID_TRANSITIONS: Dict[ProjectState, List[ProjectState]] = {
    ProjectState.IDLE: [ProjectState.QUEUED],
    ProjectState.QUEUED: [ProjectState.LOCKED, ProjectState.CANCELLED],
    ProjectState.LOCKED: [ProjectState.RUNNING, ProjectState.QUEUED, ProjectState.ERROR],
    ProjectState.RUNNING: [ProjectState.PAUSED, ProjectState.COMPLETED, ProjectState.ERROR],
    ProjectState.PAUSED: [ProjectState.RUNNING, ProjectState.CANCELLED],
    ProjectState.COMPLETED: [ProjectState.IDLE],  # Can restart
    ProjectState.ERROR: [ProjectState.IDLE, ProjectState.QUEUED],  # Can retry
    ProjectState.CANCELLED: [ProjectState.IDLE],  # Can restart
}


@dataclass
class StateTransition:
    """State transition record"""
    from_state: str
    to_state: str
    timestamp: str
    reason: Optional[str] = None
    run_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class ProjectStateInfo:
    """Complete project state information"""
    project: str
    current_state: str
    previous_state: Optional[str]
    state_changed_at: str
    run_id: Optional[str]
    current_stage: Optional[int]
    total_stages: int
    error_message: Optional[str]
    transitions: List[Dict[str, Any]]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProjectStateInfo':
        """Create from dictionary"""
        return cls(**data)


class StateMachine:
    """
    Project state machine for managing execution states.
    
    Features:
    - Enforced valid state transitions
    - State transition history
    - Persistent state storage
    - Error tracking
    """
    
    def __init__(self, products_dir: str = "products"):
        """
        Initialize state machine.
        
        Args:
            products_dir: Path to products directory
        """
        self.products_dir = Path(products_dir)
    
    def _get_state_path(self, project: str) -> Path:
        """Get state file path for project"""
        return self.products_dir / project / "state.json"
    
    def _get_default_state(self, project: str) -> ProjectStateInfo:
        """Get default state for new project"""
        now = datetime.now().isoformat()
        return ProjectStateInfo(
            project=project,
            current_state=ProjectState.IDLE.value,
            previous_state=None,
            state_changed_at=now,
            run_id=None,
            current_stage=None,
            total_stages=10,
            error_message=None,
            transitions=[]
        )
    
    def get_state(self, project: str) -> ProjectStateInfo:
        """
        Get current state for a project.
        
        Args:
            project: Project name
            
        Returns:
            ProjectStateInfo for the project
        """
        state_path = self._get_state_path(project)
        
        if not state_path.exists():
            return self._get_default_state(project)
        
        try:
            with open(state_path, 'r') as f:
                state_data = json.load(f)
            return ProjectStateInfo.from_dict(state_data)
        except (json.JSONDecodeError, KeyError):
            return self._get_default_state(project)
    
    def _save_state(self, project: str, state: ProjectStateInfo):
        """Save state to file"""
        state_path = self._get_state_path(project)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Atomic write
        temp_path = state_path.with_suffix('.tmp')
        try:
            with open(temp_path, 'w') as f:
                json.dump(state.to_dict(), f, indent=2)
            # On Windows, rename doesn't overwrite, so remove target first
            if state_path.exists():
                state_path.unlink()
            temp_path.rename(state_path)
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise Exception(f"Failed to save state for {project}: {e}")
    
    def can_transition(self, project: str, target_state: ProjectState) -> Tuple[bool, str]:
        """
        Check if a state transition is valid.
        
        Args:
            project: Project name
            target_state: Target state
            
        Returns:
            Tuple of (is_valid, reason)
        """
        current = self.get_state(project)
        current_state = ProjectState(current.current_state)
        
        if target_state not in VALID_TRANSITIONS.get(current_state, []):
            return False, f"Cannot transition from {current_state.value} to {target_state.value}"
        
        return True, "Valid transition"
    
    def transition(
        self, 
        project: str, 
        target_state: ProjectState,
        reason: Optional[str] = None,
        run_id: Optional[str] = None
    ) -> ProjectStateInfo:
        """
        Transition project to new state.
        
        Args:
            project: Project name
            target_state: Target state
            reason: Optional reason for transition
            run_id: Optional run identifier
            
        Returns:
            Updated ProjectStateInfo
            
        Raises:
            Exception: If transition is invalid
        """
        current = self.get_state(project)
        current_state = ProjectState(current.current_state)
        
        # Validate transition
        if target_state not in VALID_TRANSITIONS.get(current_state, []):
            raise Exception(
                f"Invalid state transition for {project}: "
                f"{current_state.value} -> {target_state.value}"
            )
        
        # Create transition record
        transition = StateTransition(
            from_state=current_state.value,
            to_state=target_state.value,
            timestamp=datetime.now().isoformat(),
            reason=reason,
            run_id=run_id
        )
        
        # Update state
        now = datetime.now().isoformat()
        updated_state = ProjectStateInfo(
            project=project,
            current_state=target_state.value,
            previous_state=current_state.value,
            state_changed_at=now,
            run_id=run_id or current.run_id,
            current_stage=current.current_stage,
            total_stages=current.total_stages,
            error_message=None if target_state != ProjectState.ERROR else reason,
            transitions=current.transitions + [transition.to_dict()]
        )
        
        self._save_state(project, updated_state)
        return updated_state
    
    def set_stage(self, project: str, stage: int) -> ProjectStateInfo:
        """
        Update current stage for a running project.
        
        Args:
            project: Project name
            stage: Current stage number
            
        Returns:
            Updated ProjectStateInfo
        """
        current = self.get_state(project)
        
        if current.current_state != ProjectState.RUNNING.value:
            raise Exception(f"Cannot update stage for {project} in state {current.current_state}")
        
        current.current_stage = stage
        self._save_state(project, current)
        return current
    
    def set_error(self, project: str, error_message: str) -> ProjectStateInfo:
        """
        Set project to error state.
        
        Args:
            project: Project name
            error_message: Error description
            
        Returns:
            Updated ProjectStateInfo
        """
        return self.transition(
            project,
            ProjectState.ERROR,
            reason=error_message
        )
    
    def reset(self, project: str) -> ProjectStateInfo:
        """
        Reset project to idle state.
        
        Args:
            project: Project name
            
        Returns:
            Updated ProjectStateInfo
        """
        return self.transition(
            project,
            ProjectState.IDLE,
            reason="Reset by user"
        )
    
    def get_all_states(self) -> Dict[str, ProjectStateInfo]:
        """
        Get states for all projects.
        
        Returns:
            Dictionary of project -> ProjectStateInfo
        """
        states = {}
        
        for project_dir in self.products_dir.iterdir():
            if project_dir.is_dir() and not project_dir.name.startswith('.'):
                states[project_dir.name] = self.get_state(project_dir.name)
        
        return states
    
    def get_projects_by_state(self, state: ProjectState) -> List[str]:
        """
        Get all projects in a specific state.
        
        Args:
            state: Target state
            
        Returns:
            List of project names
        """
        projects = []
        
        for project_dir in self.products_dir.iterdir():
            if project_dir.is_dir() and not project_dir.name.startswith('.'):
                project_state = self.get_state(project_dir.name)
                if project_state.current_state == state.value:
                    projects.append(project_dir.name)
        
        return projects
    
    def get_running_projects(self) -> List[str]:
        """Get all currently running projects"""
        return self.get_projects_by_state(ProjectState.RUNNING)
    
    def get_queued_projects(self) -> List[str]:
        """Get all queued projects"""
        return self.get_projects_by_state(ProjectState.QUEUED)
    
    def get_error_projects(self) -> List[str]:
        """Get all projects in error state"""
        return self.get_projects_by_state(ProjectState.ERROR)
