"""
Global Orchestrator Tests
Tests for multi-project management
"""

import pytest
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.global_orchestrator import GlobalOrchestrator, ProjectInfo, OrchestratorStatus
from core.state_machine import ProjectState


class TestGlobalOrchestrator:
    """Test suite for GlobalOrchestrator"""
    
    def test_register_project(self, temp_products_dir):
        """Test project registration"""
        orchestrator = GlobalOrchestrator(str(temp_products_dir))
        
        project = orchestrator.register_project(
            name="new-project",
            product_type="prototype",
            product_domain="general",
            model_tier="recommended",
            quality_tier="standard"
        )
        
        assert project is not None
        assert project.name == "new-project"
        assert project.product_type == "prototype"
    
    def test_register_duplicate_project(self, temp_products_dir, sample_project):
        """Test that duplicate project registration fails"""
        orchestrator = GlobalOrchestrator(str(temp_products_dir))
        
        with pytest.raises(ValueError) as excinfo:
            orchestrator.register_project(name=sample_project)
        
        assert "already exists" in str(excinfo.value)
    
    def test_get_project_info(self, temp_products_dir, sample_project):
        """Test getting project information"""
        orchestrator = GlobalOrchestrator(str(temp_products_dir))
        
        info = orchestrator.get_project_info(sample_project)
        
        assert info.name == sample_project
        assert info.status == ProjectState.IDLE.value
    
    def test_start_project(self, temp_products_dir, sample_project):
        """Test starting a project"""
        orchestrator = GlobalOrchestrator(str(temp_products_dir))
        
        # Queue project first (required for valid state transition)
        from core.queue_manager import QueueManager
        qm = QueueManager(str(temp_products_dir))
        qm.enqueue(sample_project)
        
        # Transition state to QUEUED (required for valid state transition)
        from core.state_machine import ProjectState
        orchestrator.state_machine.transition(
            sample_project,
            ProjectState.QUEUED,
            reason="Queued for execution"
        )
        
        # Start project
        started = orchestrator.start_project(sample_project)
        assert started is True
        
        # Verify project is running
        info = orchestrator.get_project_info(sample_project)
        assert info.status == ProjectState.RUNNING.value
    
    def test_pause_project(self, temp_products_dir, sample_project):
        """Test pausing a project"""
        orchestrator = GlobalOrchestrator(str(temp_products_dir))
        
        # Start project
        from core.queue_manager import QueueManager
        from core.state_machine import ProjectState
        qm = QueueManager(str(temp_products_dir))
        qm.enqueue(sample_project)
        orchestrator.state_machine.transition(
            sample_project,
            ProjectState.QUEUED,
            reason="Queued for execution"
        )
        orchestrator.start_project(sample_project)
        
        # Pause project
        paused = orchestrator.pause_project(sample_project)
        assert paused is True
        
        # Verify project is paused
        info = orchestrator.get_project_info(sample_project)
        assert info.status == ProjectState.PAUSED.value
    
    def test_resume_project(self, temp_products_dir, sample_project):
        """Test resuming a project"""
        orchestrator = GlobalOrchestrator(str(temp_products_dir))
        
        # Start and pause project
        from core.queue_manager import QueueManager
        from core.state_machine import ProjectState
        qm = QueueManager(str(temp_products_dir))
        qm.enqueue(sample_project)
        orchestrator.state_machine.transition(
            sample_project,
            ProjectState.QUEUED,
            reason="Queued for execution"
        )
        orchestrator.start_project(sample_project)
        orchestrator.pause_project(sample_project)
        
        # Resume project
        resumed = orchestrator.resume_project(sample_project)
        assert resumed is True
        
        # Verify project is running
        info = orchestrator.get_project_info(sample_project)
        assert info.status == ProjectState.RUNNING.value
    
    def test_complete_project(self, temp_products_dir, sample_project):
        """Test completing a project"""
        orchestrator = GlobalOrchestrator(str(temp_products_dir))
        
        # Start project
        from core.queue_manager import QueueManager
        from core.state_machine import ProjectState
        qm = QueueManager(str(temp_products_dir))
        qm.enqueue(sample_project)
        orchestrator.state_machine.transition(
            sample_project,
            ProjectState.QUEUED,
            reason="Queued for execution"
        )
        orchestrator.start_project(sample_project)
        
        # Complete project
        completed = orchestrator.complete_project(sample_project)
        assert completed is True
        
        # Verify project is completed
        info = orchestrator.get_project_info(sample_project)
        assert info.status == ProjectState.COMPLETED.value
    
    def test_get_all_projects(self, temp_products_dir, multiple_projects):
        """Test getting all projects"""
        orchestrator = GlobalOrchestrator(str(temp_products_dir))
        
        projects = orchestrator.get_all_projects()
        
        assert len(projects) == len(multiple_projects)
        project_names = [p.name for p in projects]
        for name in multiple_projects:
            assert name in project_names
    
    def test_get_status(self, temp_products_dir, multiple_projects):
        """Test getting orchestrator status"""
        orchestrator = GlobalOrchestrator(str(temp_products_dir))
        
        status = orchestrator.get_status()
        
        assert status.total_projects == len(multiple_projects)
        assert status.running_projects == 0
        assert status.queued_projects == 0
        assert status.completed_projects == 0
    
    def test_health_check(self, temp_products_dir, sample_project):
        """Test health check"""
        orchestrator = GlobalOrchestrator(str(temp_products_dir))
        
        health = orchestrator.health_check()
        
        assert "total_projects" in health
        assert "healthy_projects" in health
        assert "issues" in health
        assert "timestamp" in health
    
    def test_cleanup(self, temp_products_dir, sample_project):
        """Test cleanup operations"""
        orchestrator = GlobalOrchestrator(str(temp_products_dir))
        
        result = orchestrator.cleanup()
        
        assert "stale_locks_removed" in result
        assert "error_projects_reset" in result


class TestProjectInfo:
    """Test suite for ProjectInfo dataclass"""
    
    def test_project_info_creation(self):
        """Test ProjectInfo creation"""
        info = ProjectInfo(
            name="test-project",
            status="idle",
            current_stage=None,
            total_stages=10,
            model_tier="recommended",
            quality_tier="standard",
            product_type="prototype",
            product_domain="general",
            created_at="2024-01-01T00:00:00",
            last_activity="2024-01-01T00:00:00",
            run_id=None,
            lock_holder=None
        )
        
        assert info.name == "test-project"
        assert info.status == "idle"
    
    def test_project_info_serialization(self):
        """Test ProjectInfo serialization"""
        info = ProjectInfo(
            name="test-project",
            status="idle",
            current_stage=None,
            total_stages=10,
            model_tier="recommended",
            quality_tier="standard",
            product_type="prototype",
            product_domain="general",
            created_at="2024-01-01T00:00:00",
            last_activity="2024-01-01T00:00:00",
            run_id=None,
            lock_holder=None
        )
        
        data = info.to_dict()
        assert data["name"] == "test-project"
        assert data["status"] == "idle"
