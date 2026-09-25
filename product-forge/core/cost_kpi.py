"""
Cost per Successful Task KPI - Phase 2.7

Tracks cost-per-successful-task as a key performance indicator,
enabling cost optimization by stage, agent, and project.

Phase 2.7 (IMPORTANT): Cost KPI - measures true cost of productive work.
"""
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, field, asdict
from collections import defaultdict


@dataclass
class TaskCost:
    """Cost of a single task."""
    task_id: str
    project: str
    stage: int
    stage_name: str
    agent: str
    success: bool
    input_tokens: int
    output_tokens: int
    cost_usd: float
    duration_seconds: float
    retries: int = 0
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()


@dataclass
class CostKPI:
    """Cost KPI summary."""
    period: str
    total_tasks: int
    successful_tasks: int
    failed_tasks: int
    total_cost: float
    cost_per_successful_task: float
    cost_per_failed_task: float
    success_rate: float
    avg_tokens_per_task: int
    by_stage: dict = field(default_factory=dict)
    by_agent: dict = field(default_factory=dict)


class CostKPITracker:
    """
    Tracks Cost per Successful Task (CPS) as primary KPI.
    
    Phase 2.7: Measures the true cost of productive agent work.
    """
    
    METRICS_FILE = "cost_metrics.jsonl"
    
    def __init__(self, products_dir: str = "products"):
        self.products_dir = Path(products_dir)
        self.metrics_file = self.products_dir / ".pipeline" / self.METRICS_FILE
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)
        self.tasks: list[TaskCost] = self._load()
    
    def _load(self) -> list[TaskCost]:
        """Load task costs from the unified budget store (history, kind=task_cost)."""
        try:
            from core import budget as _b
            _b.migrate_legacy(None, str(self.products_dir))
            hist = _b.read_section(None, "history", str(self.products_dir)) or []
            tasks = []
            for entry in hist:
                if entry.get("kind") != "task_cost":
                    continue
                data = {k: v for k, v in entry.items() if k not in ("at", "kind")}
                try:
                    tasks.append(TaskCost(**data))
                except TypeError:
                    continue
            return tasks
        except Exception:
            return []

    def record_task(self, task: TaskCost) -> None:
        """Record a task's cost into the unified budget store."""
        self.tasks.append(task)
        try:
            from core import budget as _b
            _b.append_history(None, {"kind": "task_cost", **asdict(task)}, str(self.products_dir))
        except Exception:
            pass
    
    def _filter_tasks(
        self,
        project: Optional[str] = None,
        stage: Optional[int] = None,
        agent: Optional[str] = None,
        period_days: Optional[int] = None,
    ) -> list[TaskCost]:
        """Filter tasks by criteria."""
        filtered = self.tasks
        
        if project:
            filtered = [t for t in filtered if t.project == project]
        if stage is not None:
            filtered = [t for t in filtered if t.stage == stage]
        if agent:
            filtered = [t for t in filtered if t.agent == agent]
        if period_days:
            cutoff = datetime.utcnow() - timedelta(days=period_days)
            filtered = [
                t for t in filtered
                if datetime.fromisoformat(t.timestamp) >= cutoff
            ]
        
        return filtered
    
    def calculate_cps(
        self,
        project: Optional[str] = None,
        stage: Optional[int] = None,
        agent: Optional[str] = None,
        period_days: int = 30,
    ) -> CostKPI:
        """
        Calculate Cost Per Successful task.
        """
        filtered = self._filter_tasks(project, stage, agent, period_days)
        
        successful = [t for t in filtered if t.success]
        failed = [t for t in filtered if not t.success]
        
        total_cost = sum(t.cost_usd for t in filtered)
        total_tokens = sum(t.input_tokens + t.output_tokens for t in filtered)
        
        cost_per_success = (
            total_cost / len(successful) if successful else 0.0
        )
        cost_per_failure = (
            sum(t.cost_usd for t in failed) / len(failed) if failed else 0.0
        )
        success_rate = (
            len(successful) / len(filtered) * 100 if filtered else 0.0
        )
        
        # Per-stage breakdown
        by_stage: dict = defaultdict(lambda: {"count": 0, "success": 0, "cost": 0.0})
        for t in filtered:
            by_stage[t.stage_name]["count"] += 1
            by_stage[t.stage_name]["cost"] += t.cost_usd
            if t.success:
                by_stage[t.stage_name]["success"] += 1
        
        for stage_data in by_stage.values():
            stage_data["cps"] = (
                stage_data["cost"] / stage_data["success"]
                if stage_data["success"] > 0 else 0.0
            )
        
        # Per-agent breakdown
        by_agent: dict = defaultdict(lambda: {"count": 0, "success": 0, "cost": 0.0})
        for t in filtered:
            by_agent[t.agent]["count"] += 1
            by_agent[t.agent]["cost"] += t.cost_usd
            if t.success:
                by_agent[t.agent]["success"] += 1
        
        for agent_data in by_agent.values():
            agent_data["cps"] = (
                agent_data["cost"] / agent_data["success"]
                if agent_data["success"] > 0 else 0.0
            )
        
        return CostKPI(
            period=f"{period_days}d",
            total_tasks=len(filtered),
            successful_tasks=len(successful),
            failed_tasks=len(failed),
            total_cost=round(total_cost, 4),
            cost_per_successful_task=round(cost_per_success, 4),
            cost_per_failed_task=round(cost_per_failure, 4),
            success_rate=round(success_rate, 1),
            avg_tokens_per_task=total_tokens // len(filtered) if filtered else 0,
            by_stage=dict(by_stage),
            by_agent=dict(by_agent),
        )
    
    def get_project_cps(self, project: str, period_days: int = 30) -> float:
        """Get simple CPS for a project."""
        kpi = self.calculate_cps(project=project, period_days=period_days)
        return kpi.cost_per_successful_task
    
    def get_top_expensive_agents(
        self,
        project: Optional[str] = None,
        period_days: int = 30,
        limit: int = 10,
    ) -> list[dict]:
        """Get most expensive agents by CPS."""
        kpi = self.calculate_cps(project=project, period_days=period_days)
        
        agents = [
            {
                "agent": agent,
                "tasks": data["count"],
                "success": data["success"],
                "cps": round(data["cps"], 4),
                "total_cost": round(data["cost"], 4),
            }
            for agent, data in kpi.by_agent.items()
        ]
        agents.sort(key=lambda x: -x["cps"])
        return agents[:limit]
    
    def get_summary(self) -> dict:
        """Get overall KPI summary."""
        kpi = self.calculate_cps()
        return {
            "period": kpi.period,
            "total_tasks": kpi.total_tasks,
            "successful_tasks": kpi.successful_tasks,
            "failed_tasks": kpi.failed_tasks,
            "total_cost": kpi.total_cost,
            "cost_per_successful_task": kpi.cost_per_successful_task,
            "cost_per_failed_task": kpi.cost_per_failed_task,
            "success_rate": kpi.success_rate,
        }
