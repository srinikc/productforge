# DEPRECATED (2026-09-12): superseded by PipelineExecutor + core/orchestrator/*.
# Kept for reference; not part of the generic pipeline. See docs/UNWIRED-MODULES-TRIAGE.md.
"""
Global Orchestrator
Multi-project pipeline management and coordination
"""

import json
import os
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from datetime import datetime

from .lock_manager import LockManager
from .state_machine import StateMachine, ProjectState
from .write_safety import WriteSafety
from .queue_manager import QueueManager
from .budget_tracker import BudgetTracker


@dataclass
class ProjectInfo:
    """Project information"""
    name: str
    status: str
    current_stage: Optional[int]
    total_stages: int
    model_tier: str
    quality_tier: str
    product_type: str
    product_domain: str
    created_at: str
    last_activity: str
    run_id: Optional[str]
    lock_holder: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OrchestratorStatus:
    """Global orchestrator status"""
    total_projects: int
    running_projects: int
    queued_projects: int
    completed_projects: int
    error_projects: int
    budget_remaining: float
    last_updated: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GlobalOrchestrator:
    """
    Global orchestrator for multi-project pipeline management.
    
    Features:
    - Project lifecycle management
    - Concurrent execution coordination
    - Resource allocation (budget, models)
    - Status aggregation
    - Health monitoring
    """
    
    def __init__(self, products_dir: str = "products"):
        """
        Initialize global orchestrator.
        
        Args:
            products_dir: Path to products directory
        """
        self.products_dir = Path(products_dir)
        self.lock_manager = LockManager(products_dir)
        self.state_machine = StateMachine(products_dir)
        self.write_safety = WriteSafety(products_dir)
        self.queue_manager = QueueManager(products_dir)
        self.budget_tracker = BudgetTracker(products_dir)
        
        # Ensure index.json exists
        self._ensure_index()
    
    def _ensure_index(self):
        """Ensure products index exists"""
        index_path = self.products_dir / "index.json"
        if not index_path.exists():
            self.write_safety.atomic_write_json(index_path, {"products": []})
    
    def _load_index(self) -> Dict[str, Any]:
        """Load products index"""
        index_path = self.products_dir / "index.json"
        if index_path.exists():
            with open(index_path, 'r') as f:
                return json.load(f)
        return {"products": []}
    
    def _save_index(self, index: Dict[str, Any]):
        """Save products index"""
        index_path = self.products_dir / "index.json"
        self.write_safety.atomic_write_json(index_path, index)
    
    def register_project(
        self,
        name: str,
        product_type: str = "general",
        product_domain: str = "general",
        model_tier: str = "recommended",
        quality_tier: str = "standard"
    ) -> ProjectInfo:
        """
        Register a new project.
        
        Args:
            name: Project name
            product_type: Product type classification
            product_domain: Product domain
            model_tier: Model tier to use
            quality_tier: Quality tier
            
        Returns:
            ProjectInfo for the new project
        """
        # Check if project already exists
        index = self._load_index()
        if name in index.get("products", []):
            raise ValueError(f"Project {name} already exists")
        
        # Create project directory
        project_dir = self.products_dir / name
        project_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        for subdir in ["docs", "reports", "checkpoints", "dlq", "selective_runs", "security"]:
            (project_dir / subdir).mkdir(exist_ok=True)
        
        # Create initial pipeline.json
        now = datetime.now().isoformat()
        pipeline_config = {
            "current_stage": 0,
            "model_tier": model_tier,
            "quality_tier": quality_tier,
            "product_type": product_type,
            "product_domain": product_domain,
            "agents": {},
            "stages": {},
            "circuit_breakers": {},
            "fallback_chains": {},
            "git": {
                "auto_commit": True,
                "branch_prefix": "pipeline/",
                "commit_format": "conventional"
            },
            "created_at": now,
            "last_activity": now
        }
        self.write_safety.atomic_write_json(project_dir / "pipeline.json", pipeline_config)
        
        # Update index
        index["products"].append(name)
        self._save_index(index)
        
        # Initialize state
        self.state_machine.get_state(name)  # Creates default state
        
        # Return project info
        return self.get_project_info(name)
    
    def get_project_info(self, name: str) -> ProjectInfo:
        """
        Get project information.
        
        Args:
            name: Project name
            
        Returns:
            ProjectInfo
        """
        project_dir = self.products_dir / name
        if not project_dir.exists():
            raise ValueError(f"Project {name} not found")
        
        # Load pipeline.json
        pipeline_path = project_dir / "pipeline.json"
        if pipeline_path.exists():
            with open(pipeline_path, 'r') as f:
                pipeline = json.load(f)
        else:
            pipeline = {}
        
        # Get state
        state = self.state_machine.get_state(name)
        
        # Get lock info
        lock_info = self.lock_manager.get_lock_info(name)
        
        return ProjectInfo(
            name=name,
            status=state.current_state,
            current_stage=state.current_stage,
            total_stages=state.total_stages,
            model_tier=pipeline.get("model_tier", "recommended"),
            quality_tier=pipeline.get("quality_tier", "standard"),
            product_type=pipeline.get("product_type", "general"),
            product_domain=pipeline.get("product_domain", "general"),
            created_at=pipeline.get("created_at", ""),
            last_activity=pipeline.get("last_activity", ""),
            run_id=state.run_id,
            lock_holder=lock_info.holder if lock_info else None
        )
    
    def start_project(self, name: str) -> bool:
        """
        Start executing a project.
        
        Args:
            name: Project name
            
        Returns:
            True if started successfully
        """
        # Check if project is queued
        state = self.state_machine.get_state(name)
        if state.current_state != ProjectState.QUEUED.value:
            # Queue it first
            self.queue_manager.enqueue(name)
        
        # Try to acquire lock
        run_id = str(uuid.uuid4())[:8]
        lock = self.lock_manager.acquire_lock(
            name,
            holder=f"orchestrator-{run_id}",
            ttl_seconds=7200,  # 2 hours
            run_id=run_id
        )
        
        if not lock:
            return False  # Lock held by another process
        
        # Transition to locked state
        self.state_machine.transition(
            name,
            ProjectState.LOCKED,
            reason="Lock acquired",
            run_id=run_id
        )
        
        # Remove from queue
        self.queue_manager.dequeue(name)
        
        # Transition to running
        self.state_machine.transition(
            name,
            ProjectState.RUNNING,
            reason="Pipeline started"
        )
        
        return True
    
    def pause_project(self, name: str) -> bool:
        """
        Pause a running project.
        
        Args:
            name: Project name
            
        Returns:
            True if paused successfully
        """
        state = self.state_machine.get_state(name)
        if state.current_state != ProjectState.RUNNING.value:
            return False
        
        self.state_machine.transition(
            name,
            ProjectState.PAUSED,
            reason="Paused by user"
        )
        
        return True
    
    def resume_project(self, name: str) -> bool:
        """
        Resume a paused project.
        
        Args:
            name: Project name
            
        Returns:
            True if resumed successfully
        """
        state = self.state_machine.get_state(name)
        if state.current_state != ProjectState.PAUSED.value:
            return False
        
        self.state_machine.transition(
            name,
            ProjectState.RUNNING,
            reason="Resumed by user"
        )
        
        return True
    
    def complete_project(self, name: str) -> bool:
        """
        Mark a project as completed.
        
        Args:
            name: Project name
            
        Returns:
            True if completed successfully
        """
        state = self.state_machine.get_state(name)
        if state.current_state != ProjectState.RUNNING.value:
            return False
        
        # Release lock
        lock_info = self.lock_manager.get_lock_info(name)
        if lock_info:
            self.lock_manager.release_lock(name, lock_info.holder)
        
        # Transition to completed
        self.state_machine.transition(
            name,
            ProjectState.COMPLETED,
            reason="Pipeline completed"
        )
        
        return True
    
    def cancel_project(self, name: str) -> bool:
        """
        Cancel a project.
        
        Args:
            name: Project name
            
        Returns:
            True if cancelled successfully
        """
        state = self.state_machine.get_state(name)
        if state.current_state not in [ProjectState.QUEUED.value, ProjectState.PAUSED.value]:
            return False
        
        # Release lock if held
        lock_info = self.lock_manager.get_lock_info(name)
        if lock_info:
            self.lock_manager.release_lock(name, lock_info.holder)
        
        # Transition to cancelled
        self.state_machine.transition(
            name,
            ProjectState.CANCELLED,
            reason="Cancelled by user"
        )
        
        return True
    
    def get_all_projects(self) -> List[ProjectInfo]:
        """
        Get information for all projects.
        
        Returns:
            List of ProjectInfo
        """
        index = self._load_index()
        projects = []
        
        for name in index.get("products", []):
            try:
                projects.append(self.get_project_info(name))
            except ValueError:
                continue
        
        return projects
    
    def get_status(self) -> OrchestratorStatus:
        """
        Get global orchestrator status.
        
        Returns:
            OrchestratorStatus
        """
        projects = self.get_all_projects()
        
        return OrchestratorStatus(
            total_projects=len(projects),
            running_projects=sum(1 for p in projects if p.status == ProjectState.RUNNING.value),
            queued_projects=sum(1 for p in projects if p.status == ProjectState.QUEUED.value),
            completed_projects=sum(1 for p in projects if p.status == ProjectState.COMPLETED.value),
            error_projects=sum(1 for p in projects if p.status == ProjectState.ERROR.value),
            budget_remaining=self.budget_tracker.get_remaining_budget(),
            last_updated=datetime.now().isoformat()
        )
    
    def get_project_status(self, name: str) -> Dict[str, Any]:
        """
        Get detailed project status.
        
        Args:
            name: Project name
            
        Returns:
            Detailed status dictionary
        """
        project_info = self.get_project_info(name)
        lock_info = self.lock_manager.get_lock_info(name)
        state = self.state_machine.get_state(name)
        
        return {
            "project": project_info.to_dict(),
            "lock": lock_info.to_dict() if lock_info else None,
            "state_history": [t for t in state.transitions[-10:]],  # Last 10 transitions
            "current_stage": state.current_stage,
            "error_message": state.error_message
        }
    
    def cleanup(self) -> Dict[str, int]:
        """
        Cleanup stale locks and reset error states.
        
        Returns:
            Cleanup statistics
        """
        stale_locks = self.lock_manager.cleanup_stale_locks()
        
        # Reset error projects that have been idle too long
        error_projects = self.state_machine.get_projects_by_state(ProjectState.ERROR)
        reset_count = 0
        for project in error_projects:
            # Could add time-based logic here
            pass
        
        return {
            "stale_locks_removed": stale_locks,
            "error_projects_reset": reset_count
        }
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on all projects.
        
        Returns:
            Health check results
        """
        projects = self.get_all_projects()
        issues = []
        
        for project in projects:
            # Check for stuck projects
            if project.status == ProjectState.RUNNING.value:
                lock_info = self.lock_manager.get_lock_info(project.name)
                if lock_info and lock_info.is_expired():
                    issues.append({
                        "project": project.name,
                        "issue": "running_with_expired_lock"
                    })
            
            # Check for projects in error state
            if project.status == ProjectState.ERROR.value:
                issues.append({
                    "project": project.name,
                    "issue": "in_error_state"
                })
        
        return {
            "total_projects": len(projects),
            "healthy_projects": len(projects) - len(issues),
            "issues": issues,
            "timestamp": datetime.now().isoformat()
        }
    
    # --- Product Plan Integration ---
    
    def get_project_health_from_plan(self, name: str) -> Dict[str, Any]:
        """
        Get comprehensive project health from product plan.
        
        Args:
            name: Project name
            
        Returns:
            Health summary with feature completion, coverage, blockers
        """
        from .product_plan import ProductPlan
        
        plan = ProductPlan(name, str(self.products_dir))
        if not plan.exists():
            return {
                "project": name,
                "overall_status": "no_plan",
                "message": "Product plan not found"
            }
        
        return plan.get_project_health()
    
    def detect_plan_drift(self, name: str) -> Dict[str, Any]:
        """
        Detect when implementation diverges from plan.
        
        Checks:
        - Features implemented but not in plan
        - Planned features with no activity
        - Requirements with no linked features
        - Tests failing but feature marked complete
        - Security issues on completed features
        
        Args:
            name: Project name
            
        Returns:
            Drift analysis results
        """
        from .product_plan import ProductPlan
        from .traceability import TraceabilityMatrix
        
        plan = ProductPlan(name, str(self.products_dir))
        trace = TraceabilityMatrix(name, str(self.products_dir))
        
        drift_issues = []
        
        if plan.exists():
            all_features = plan.get_all_features()
            
            # Check for features with issues
            for feature in all_features:
                # Test failure on completed feature
                if (feature.status == "completed" and
                    feature.testing and
                    feature.testing.pass_rate < 1.0):
                    drift_issues.append({
                        "type": "test_failure_on_complete",
                        "feature": feature.id,
                        "details": f"Feature marked complete but test pass rate is {feature.testing.pass_rate * 100}%"
                    })
                
                # Security issues on completed feature
                if (feature.status == "completed" and
                    feature.security and
                    feature.security.issues):
                    drift_issues.append({
                        "type": "security_issue_on_complete",
                        "feature": feature.id,
                        "details": f"Feature has {len(feature.security.issues)} security issues"
                    })
                
                # Blocked feature
                if feature.status == "blocked":
                    drift_issues.append({
                        "type": "blocked_feature",
                        "feature": feature.id,
                        "details": "Feature is blocked"
                    })
        
        if trace.exists():
            # Check for untested requirements
            untested = trace.get_untested_requirements()
            for req in untested:
                drift_issues.append({
                    "type": "untested_requirement",
                    "requirement": req.requirement_id,
                    "details": f"Requirement {req.requirement_id} has no tests"
                })
        
        return {
            "project": name,
            "drift_detected": len(drift_issues) > 0,
            "issues": drift_issues,
            "timestamp": datetime.now().isoformat()
        }
    
    def show_features_needing_rework(self, name: str) -> List[Dict[str, Any]]:
        """
        Show all features that need rework.
        
        Criteria:
        - Test pass rate < 100%
        - Security issues open
        - Code review not approved
        - Status is 'blocked'
        
        Args:
            name: Project name
            
        Returns:
            List of features needing rework
        """
        from .product_plan import ProductPlan
        
        plan = ProductPlan(name, str(self.products_dir))
        if not plan.exists():
            return []
        
        rework_features = plan.get_features_needing_rework()
        return [f.to_dict() for f in rework_features]
    
    def generate_status_report(self, name: str) -> str:
        """
        Generate structured status report from product plan data.
        
        Args:
            name: Project name
            
        Returns:
            Markdown status report
        """
        from .product_plan import ProductPlan
        from .traceability import TraceabilityMatrix
        
        report = []
        report.append(f"# Project Status Report: {name}")
        report.append("")
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append("")
        
        # Product Plan Status
        plan = ProductPlan(name, str(self.products_dir))
        if plan.exists():
            health = plan.get_project_health()
            report.append("## Overall Health")
            report.append("")
            report.append(f"- **Status:** {health['overall_status']}")
            report.append(f"- **Feature Completion:** {health['feature_completion']['completed']}/{health['feature_completion']['total']} ({health['feature_completion']['percent_complete']:.1f}%)")
            report.append(f"- **Needs Rework:** {health['needs_rework']}")
            report.append(f"- **Modules:** {health['modules']}")
            report.append("")
            
            # Features by status
            report.append("## Feature Status")
            report.append("")
            for status in ["completed", "in-progress", "planned", "blocked"]:
                features = plan.get_features_by_status(status)
                if features:
                    report.append(f"### {status.title()} ({len(features)})")
                    for f in features[:5]:  # Show first 5
                        report.append(f"- {f.id}: {f.name}")
                    if len(features) > 5:
                        report.append(f"- ... and {len(features) - 5} more")
                    report.append("")
        
        # Traceability Status
        trace = TraceabilityMatrix(name, str(self.products_dir))
        if trace.exists():
            coverage = trace.get_coverage()
            report.append("## Requirement Coverage")
            report.append("")
            report.append(f"- **Implemented:** {coverage['percent_implemented']}%")
            report.append(f"- **Tested:** {coverage['percent_tested']}%")
            report.append(f"- **Secured:** {coverage['percent_secured']}%")
            report.append(f"- **Fully Covered:** {coverage['percent_fully_covered']}%")
            report.append("")
        
        return "\n".join(report)
    
    def impact_analysis(self, name: str, requirement_id: str) -> Dict[str, Any]:
        """
        Run impact analysis for a requirement change.
        
        Args:
            name: Project name
            requirement_id: Requirement to analyze
            
        Returns:
            Impact analysis results
        """
        from .product_plan import ProductPlan
        from .traceability import TraceabilityMatrix
        
        trace = TraceabilityMatrix(name, str(self.products_dir))
        if not trace.exists():
            return {
                "requirement_id": requirement_id,
                "error": "Traceability matrix not found"
            }
        
        # Build requirement to features mapping
        plan = ProductPlan(name, str(self.products_dir))
        req_features = {}
        if plan.exists():
            for feature in plan.get_all_features():
                for req_id in feature.requirements:
                    if req_id not in req_features:
                        req_features[req_id] = []
                    req_features[req_id].append(feature.id)
        
        analysis = trace.impact_analysis(requirement_id, req_features)
        return analysis.to_dict()
    
    def get_all_projects_health(self) -> Dict[str, Dict[str, Any]]:
        """
        Get health summary for all projects.
        
        Returns:
            Dict mapping project name to health summary
        """
        projects = self.get_all_projects()
        health = {}
        
        for project in projects:
            health[project.name] = self.get_project_health_from_plan(project.name)
        
        return health
