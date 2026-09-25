"""
State Machine Tests
Tests for project state management
"""

import pytest
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.state_machine import StateMachine, ProjectState, ProjectStateInfo


class TestStateMachine:
    """Test suite for StateMachine"""
    
    def test_get_default_state(self, temp_products_dir, sample_project):
        """Test getting default state for new project"""
        sm = StateMachine(str(temp_products_dir))
        
        state = sm.get_state(sample_project)
        assert state.current_state == ProjectState.IDLE.value
        assert state.previous_state is None
        assert state.project == sample_project
    
    def test_valid_transition(self, temp_products_dir, sample_project):
        """Test valid state transition"""
        sm = StateMachine(str(temp_products_dir))
        
        # Transition from IDLE to QUEUED
        new_state = sm.transition(
            sample_project,
            ProjectState.QUEUED,
            reason="User queued project"
        )
        
        assert new_state.current_state == ProjectState.QUEUED.value
        assert new_state.previous_state == ProjectState.IDLE.value
    
    def test_invalid_transition(self, temp_products_dir, sample_project):
        """Test invalid state transition"""
        sm = StateMachine(str(temp_products_dir))
        
        # Try to transition from IDLE to RUNNING (invalid)
        with pytest.raises(Exception) as excinfo:
            sm.transition(
                sample_project,
                ProjectState.RUNNING,
                reason="Invalid transition"
            )
        
        assert "Invalid state transition" in str(excinfo.value)
    
    def test_can_transition(self, temp_products_dir, sample_project):
        """Test checking if transition is valid"""
        sm = StateMachine(str(temp_products_dir))
        
        # Valid transition
        can, reason = sm.can_transition(sample_project, ProjectState.QUEUED)
        assert can is True
        
        # Invalid transition
        can, reason = sm.can_transition(sample_project, ProjectState.RUNNING)
        assert can is False
    
    def test_full_lifecycle(self, temp_products_dir, sample_project):
        """Test full project lifecycle"""
        sm = StateMachine(str(temp_products_dir))
        
        # IDLE -> QUEUED
        state = sm.transition(sample_project, ProjectState.QUEUED)
        assert state.current_state == ProjectState.QUEUED.value
        
        # QUEUED -> LOCKED
        state = sm.transition(sample_project, ProjectState.LOCKED)
        assert state.current_state == ProjectState.LOCKED.value
        
        # LOCKED -> RUNNING
        state = sm.transition(sample_project, ProjectState.RUNNING)
        assert state.current_state == ProjectState.RUNNING.value
        
        # RUNNING -> COMPLETED
        state = sm.transition(sample_project, ProjectState.COMPLETED)
        assert state.current_state == ProjectState.COMPLETED.value
    
    def test_error_state(self, temp_products_dir, sample_project):
        """Test error state handling"""
        sm = StateMachine(str(temp_products_dir))
        
        # Go to RUNNING state
        sm.transition(sample_project, ProjectState.QUEUED)
        sm.transition(sample_project, ProjectState.LOCKED)
        sm.transition(sample_project, ProjectState.RUNNING)
        
        # Set error
        state = sm.set_error(sample_project, "Something went wrong")
        assert state.current_state == ProjectState.ERROR.value
        assert state.error_message == "Something went wrong"
    
    def test_pause_resume(self, temp_products_dir, sample_project):
        """Test pause and resume functionality"""
        sm = StateMachine(str(temp_products_dir))
        
        # Go to RUNNING state
        sm.transition(sample_project, ProjectState.QUEUED)
        sm.transition(sample_project, ProjectState.LOCKED)
        sm.transition(sample_project, ProjectState.RUNNING)
        
        # Pause
        state = sm.transition(sample_project, ProjectState.PAUSED)
        assert state.current_state == ProjectState.PAUSED.value
        
        # Resume
        state = sm.transition(sample_project, ProjectState.RUNNING)
        assert state.current_state == ProjectState.RUNNING.value
    
    def test_cancel(self, temp_products_dir, sample_project):
        """Test cancellation"""
        sm = StateMachine(str(temp_products_dir))
        
        # Go to QUEUED state
        sm.transition(sample_project, ProjectState.QUEUED)
        
        # Cancel
        state = sm.transition(sample_project, ProjectState.CANCELLED)
        assert state.current_state == ProjectState.CANCELLED.value
    
    def test_set_stage(self, temp_products_dir, sample_project):
        """Test setting current stage"""
        sm = StateMachine(str(temp_products_dir))
        
        # Go to RUNNING state
        sm.transition(sample_project, ProjectState.QUEUED)
        sm.transition(sample_project, ProjectState.LOCKED)
        sm.transition(sample_project, ProjectState.RUNNING)
        
        # Set stage
        state = sm.set_stage(sample_project, 3)
        assert state.current_stage == 3
    
    def test_get_all_states(self, temp_products_dir, multiple_projects):
        """Test getting all project states"""
        sm = StateMachine(str(temp_products_dir))
        
        states = sm.get_all_states()
        assert len(states) == len(multiple_projects)
    
    def test_get_projects_by_state(self, temp_products_dir, multiple_projects):
        """Test filtering projects by state"""
        sm = StateMachine(str(temp_products_dir))
        
        # All projects should be in IDLE state
        idle_projects = sm.get_projects_by_state(ProjectState.IDLE)
        assert len(idle_projects) == len(multiple_projects)
    
    def test_state_history(self, temp_products_dir, sample_project):
        """Test state transition history"""
        sm = StateMachine(str(temp_products_dir))
        
        # Make several transitions
        sm.transition(sample_project, ProjectState.QUEUED)
        sm.transition(sample_project, ProjectState.LOCKED)
        sm.transition(sample_project, ProjectState.RUNNING)
        
        # Get state
        state = sm.get_state(sample_project)
        
        # Check history
        assert len(state.transitions) == 3
        assert state.transitions[0]["to_state"] == ProjectState.QUEUED.value
        assert state.transitions[1]["to_state"] == ProjectState.LOCKED.value
        assert state.transitions[2]["to_state"] == ProjectState.RUNNING.value


class TestProjectState:
    """Test suite for ProjectState enum"""
    
    def test_valid_states(self):
        """Test all valid states exist"""
        states = [
            ProjectState.IDLE,
            ProjectState.QUEUED,
            ProjectState.LOCKED,
            ProjectState.RUNNING,
            ProjectState.PAUSED,
            ProjectState.COMPLETED,
            ProjectState.ERROR,
            ProjectState.CANCELLED
        ]
        
        assert len(states) == 8
    
    def test_state_values(self):
        """Test state string values"""
        assert ProjectState.IDLE.value == "idle"
        assert ProjectState.QUEUED.value == "queued"
        assert ProjectState.RUNNING.value == "running"
        assert ProjectState.COMPLETED.value == "completed"
        assert ProjectState.ERROR.value == "error"
