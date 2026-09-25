"""
Integration Tests
End-to-end tests for the multi-agent, multi-project pipeline
"""

import pytest
import json
import time
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.global_orchestrator import GlobalOrchestrator
from core.lock_manager import LockManager
from core.state_machine import StateMachine, ProjectState
from core.write_safety import WriteSafety
from core.queue_manager import QueueManager, Priority
from core.budget_tracker import BudgetTracker
from security.core.issue_tracker import SecurityIssueTracker


class TestPipelineIntegration:
    """End-to-end integration tests for the pipeline"""
    
    def test_full_project_lifecycle(self, temp_products_dir):
        """Test complete project lifecycle from registration to completion"""
        orchestrator = GlobalOrchestrator(str(temp_products_dir))
        
        # 1. Register project
        project = orchestrator.register_project(
            name="lifecycle-project",
            product_type="product",
            product_domain="finance"
        )
        assert project.name == "lifecycle-project"
        
        # 2. Queue project
        qm = QueueManager(str(temp_products_dir))
        qm.enqueue("lifecycle-project", priority=Priority.HIGH)
        
        # 3. Transition state to QUEUED (required for valid state transition)
        orchestrator.state_machine.transition(
            "lifecycle-project",
            ProjectState.QUEUED,
            reason="Queued for execution"
        )
        
        # 4. Start project
        started = orchestrator.start_project("lifecycle-project")
        assert started is True
        
        # 5. Verify running state
        info = orchestrator.get_project_info("lifecycle-project")
        assert info.status == ProjectState.RUNNING.value
        
        # 6. Pause project
        paused = orchestrator.pause_project("lifecycle-project")
        assert paused is True
        
        # 7. Resume project
        resumed = orchestrator.resume_project("lifecycle-project")
        assert resumed is True
        
        # 8. Complete project
        completed = orchestrator.complete_project("lifecycle-project")
        assert completed is True
        
        # 9. Verify completed state
        info = orchestrator.get_project_info("lifecycle-project")
        assert info.status == ProjectState.COMPLETED.value
    
    def test_concurrent_project_execution(self, temp_products_dir):
        """Test multiple projects running concurrently"""
        orchestrator = GlobalOrchestrator(str(temp_products_dir))
        qm = QueueManager(str(temp_products_dir))
        
        # Register multiple projects
        projects = []
        for i in range(3):
            project = orchestrator.register_project(
                name=f"concurrent-project-{i}",
                product_type="prototype",
                product_domain="general"
            )
            projects.append(project.name)
            qm.enqueue(project.name)
            # Transition state to QUEUED
            orchestrator.state_machine.transition(
                project.name,
                ProjectState.QUEUED,
                reason="Queued for execution"
            )
        
        # Start all projects
        for project in projects:
            started = orchestrator.start_project(project)
            assert started is True
        
        # Verify all are running
        for project in projects:
            info = orchestrator.get_project_info(project)
            assert info.status == ProjectState.RUNNING.value
        
        # Get status
        status = orchestrator.get_status()
        assert status.running_projects == 3
    
    def test_project_isolation(self, temp_products_dir):
        """Test that projects are isolated from each other"""
        orchestrator = GlobalOrchestrator(str(temp_products_dir))
        qm = QueueManager(str(temp_products_dir))
        
        # Register two projects
        orchestrator.register_project(name="project-a", product_type="prototype")
        orchestrator.register_project(name="project-b", product_type="prototype")
        
        qm.enqueue("project-a")
        qm.enqueue("project-b")
        
        # Transition state to QUEUED
        orchestrator.state_machine.transition(
            "project-a",
            ProjectState.QUEUED,
            reason="Queued for execution"
        )
        orchestrator.state_machine.transition(
            "project-b",
            ProjectState.QUEUED,
            reason="Queued for execution"
        )
        
        # Start project A
        orchestrator.start_project("project-a")
        
        # Project A should be running, project B should be queued
        info_a = orchestrator.get_project_info("project-a")
        info_b = orchestrator.get_project_info("project-b")
        
        assert info_a.status == ProjectState.RUNNING.value
        assert info_b.status == ProjectState.QUEUED.value
        
        # Project B should still be able to start
        started = orchestrator.start_project("project-b")
        assert started is True
    
    def test_lock_prevents_double_execution(self, temp_products_dir):
        """Test that lock prevents same project from running twice"""
        orchestrator = GlobalOrchestrator(str(temp_products_dir))
        qm = QueueManager(str(temp_products_dir))
        
        # Register project
        orchestrator.register_project(name="locked-project")
        qm.enqueue("locked-project")
        # Transition state to QUEUED
        orchestrator.state_machine.transition(
            "locked-project",
            ProjectState.QUEUED,
            reason="Queued for execution"
        )
        
        # Start project
        orchestrator.start_project("locked-project")
        
        # Try to start again (should fail due to lock)
        qm.enqueue("locked-project")
        started = orchestrator.start_project("locked-project")
        assert started is False
    
    def test_security_issue_workflow(self, temp_products_dir, sample_project):
        """Test security issue creation, decision, and tracking"""
        tracker = SecurityIssueTracker(str(temp_products_dir))
        
        # 1. Add critical issue
        issue = tracker.add_issue(
            project=sample_project,
            title="SQL Injection vulnerability",
            severity="critical",
            description="User input directly interpolated into SQL query",
            recommendation="Use parameterized queries",
            file="src/auth/login.py",
            line=42
        )
        assert issue.priority == "p0"
        assert issue.fix_now is True
        
        # 2. User decides to fix now
        updated = tracker.update_issue(
            sample_project,
            issue.issue_id,
            decision="fix_now"
        )
        assert updated.decision == "fix_now"
        
        # 3. Mark as fixed
        fixed = tracker.update_issue(
            sample_project,
            issue.issue_id,
            status="fixed"
        )
        assert fixed.status == "fixed"
        assert fixed.resolved_at is not None
        
        # 4. Verify summary
        summary = tracker.get_summary(sample_project)
        assert summary["by_status"]["fixed"] == 1
    
    def test_budget_tracking(self, temp_products_dir):
        """Test budget tracking across projects"""
        tracker = BudgetTracker(str(temp_products_dir))
        
        # Record spend
        tracker.record_spend(
            project="project-a",
            agent="implement",
            model="mimo-v2.5-free",
            tokens_input=1000,
            tokens_output=500,
            cost=0.50
        )
        
        tracker.record_spend(
            project="project-b",
            agent="architect",
            model="hy3-free",
            tokens_input=2000,
            tokens_output=1000,
            cost=1.00
        )
        
        # Check remaining budget
        remaining = tracker.get_remaining_budget()
        assert remaining > 0
        
        # Check project spend
        spend_a = tracker.get_project_spend("project-a")
        spend_b = tracker.get_project_spend("project-b")
        
        assert spend_a == 0.50
        assert spend_b == 1.00
    
    def test_queue_priority_scheduling(self, temp_products_dir):
        """Test that queue respects priority scheduling"""
        qm = QueueManager(str(temp_products_dir))
        
        # Enqueue with different priorities
        qm.enqueue("normal-project", priority=Priority.NORMAL)
        qm.enqueue("critical-project", priority=Priority.CRITICAL)
        qm.enqueue("high-project", priority=Priority.HIGH)
        
        # Get next should return CRITICAL
        next_item = qm.get_next()
        assert next_item.project == "critical-project"
        
        # Remove and get next should return HIGH
        qm.dequeue("critical-project")
        next_item = qm.get_next()
        assert next_item.project == "high-project"
    
    def test_state_machine_transitions(self, temp_products_dir, sample_project):
        """Test valid state machine transitions"""
        sm = StateMachine(str(temp_products_dir))
        
        # Test that can_transition works correctly
        # Start from IDLE
        can, reason = sm.can_transition(sample_project, ProjectState.QUEUED)
        assert can is True, f"Should be able to transition from IDLE to QUEUED: {reason}"
        
        # Try to transition to LOCKED (not allowed from IDLE)
        can, reason = sm.can_transition(sample_project, ProjectState.LOCKED)
        assert can is False, f"Should not be able to transition from IDLE to LOCKED: {reason}"
        
        # Try to transition to RUNNING (not allowed from IDLE)
        can, reason = sm.can_transition(sample_project, ProjectState.RUNNING)
        assert can is False, f"Should not be able to transition from IDLE to RUNNING: {reason}"
    
    def test_health_check(self, temp_products_dir, multiple_projects):
        """Test system health check"""
        orchestrator = GlobalOrchestrator(str(temp_products_dir))
        
        # Start some projects
        qm = QueueManager(str(temp_products_dir))
        for project in multiple_projects[:2]:
            qm.enqueue(project)
            # Transition state to QUEUED
            orchestrator.state_machine.transition(
                project,
                ProjectState.QUEUED,
                reason="Queued for execution"
            )
            orchestrator.start_project(project)
        
        # Run health check
        health = orchestrator.health_check()
        
        assert health["total_projects"] == len(multiple_projects)
        assert health["healthy_projects"] > 0
    
    def test_cleanup_stale_locks(self, temp_products_dir, sample_project):
        """Test cleanup of stale locks"""
        lm = LockManager(str(temp_products_dir))
        
        # Acquire lock with short TTL
        lm.acquire_lock(sample_project, holder="test", ttl_seconds=1)
        
        # Wait for expiration
        time.sleep(2)
        
        # Cleanup
        removed = lm.cleanup_stale_locks()
        assert removed >= 1
        
        # Verify lock is gone
        assert not lm.is_locked(sample_project)


class TestSecurityIntegration:
    """Integration tests for security system"""
    
    def test_security_analysis_workflow(self, temp_products_dir, sample_project):
        """Test complete security analysis workflow"""
        from security.core.issue_tracker import SecurityIssueTracker
        
        tracker = SecurityIssueTracker(str(temp_products_dir))
        
        # Add multiple issues
        issues = [
            ("Critical SQL Injection", "critical", "p0"),
            ("High XSS Vulnerability", "high", "p1"),
            ("Medium CSRF Issue", "medium", "p2"),
            ("Low Information Disclosure", "low", "p3"),
        ]
        
        for title, severity, expected_priority in issues:
            issue = tracker.add_issue(
                project=sample_project,
                title=title,
                severity=severity,
                description=f"Test {severity} issue",
                recommendation="Fix it"
            )
            assert issue.priority == expected_priority
        
        # Get summary
        summary = tracker.get_summary(sample_project)
        assert summary["total"] == 4
        assert summary["fix_now"] == 2  # critical + high
        assert summary["track_later"] == 2  # medium + low
    
    def test_compliance_check(self, security_config_dir):
        """Test compliance checking"""
        from security.core.compliance_checker import ComplianceChecker
        
        checker = ComplianceChecker(str(security_config_dir))
        
        # Check that compliance config is loaded
        assert checker.config is not None
        assert "domains" in checker.config
        
        # Check finance domain has PCI-DSS
        finance = checker.config["domains"].get("finance", {})
        regulations = finance.get("regulations", [])
        reg_names = [r["name"] for r in regulations]
        assert "PCI-DSS" in reg_names
