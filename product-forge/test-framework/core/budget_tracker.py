"""
Budget Tracker - Tracks token and cost budgets per project.

Phase 1.6 (CRITICAL): Token and cost tracking with budget enforcement.
"""
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, field, asdict
from enum import Enum


class BudgetPeriod(str, Enum):
    """Budget tracking period."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    PER_PROJECT = "per_project"


@dataclass
class BudgetUsage:
    """Token usage for a single operation."""
    timestamp: str
    project: str
    agent: str
    stage: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    model: str
    metadata: dict = field(default_factory=dict)
    
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class BudgetTracker:
    """Tracks token usage and enforces budget limits."""
    
    BUDGET_FILE = "budget.json"
    USAGE_FILE = "usage.jsonl"
    
    DEFAULT_BUDGETS = {
        BudgetPeriod.HOURLY.value: 100.0,
        BudgetPeriod.DAILY.value: 1000.0,
        BudgetPeriod.WEEKLY.value: 5000.0,
        BudgetPeriod.PER_PROJECT.value: 500.0,
    }
    
    # Cost per 1K tokens (input, output) by model
    MODEL_COSTS = {
        "gpt-4": (0.03, 0.06),
        "gpt-4-turbo": (0.01, 0.03),
        "gpt-3.5-turbo": (0.0005, 0.0015),
        "claude-3-opus": (0.015, 0.075),
        "claude-3-sonnet": (0.003, 0.015),
        "claude-3-haiku": (0.00025, 0.00125),
        "mimo": (0.0, 0.0),  # Free
        "hy3": (0.0001, 0.0001),  # Very cheap
    }
    
    def __init__(self, products_dir: str = "products"):
        self.products_dir = Path(products_dir)
        self.budget_file = self.products_dir / self.BUDGET_FILE
        self.usage_file = self.products_dir / self.USAGE_FILE
        self.budget_file.parent.mkdir(parents=True, exist_ok=True)
    
    def _load_budgets(self) -> dict:
        """Load budget configuration."""
        if not self.budget_file.exists():
            return {"budgets": self.DEFAULT_BUDGETS.copy(), "usage": {}}
        
        try:
            return json.loads(self.budget_file.read_text())
        except (json.JSONDecodeError, OSError):
            return {"budgets": self.DEFAULT_BUDGETS.copy(), "usage": {}}
    
    def _save_budgets(self, data: dict) -> None:
        """Save budget configuration."""
        self.budget_file.write_text(json.dumps(data, indent=2, default=str))
    
    def set_budget(self, period: str, amount: float) -> None:
        """Set a budget for a specific period."""
        data = self._load_budgets()
        data["budgets"][period] = amount
        self._save_budgets(data)
    
    def get_budget(self, period: str) -> float:
        """Get the budget for a specific period."""
        data = self._load_budgets()
        return data["budgets"].get(period, 0.0)
    
    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost in USD for token usage."""
        if model not in self.MODEL_COSTS:
            model = "gpt-3.5-turbo"  # Default
        
        input_cost, output_cost = self.MODEL_COSTS[model]
        cost = (input_tokens / 1000) * input_cost + (output_tokens / 1000) * output_cost
        return round(cost, 6)
    
    def record_usage(
        self,
        project: str,
        agent: str,
        stage: str,
        input_tokens: int,
        output_tokens: int,
        model: str = "gpt-3.5-turbo",
        metadata: Optional[dict] = None,
    ) -> BudgetUsage:
        """Record token usage for a project."""
        cost = self.calculate_cost(model, input_tokens, output_tokens)
        
        usage = BudgetUsage(
            timestamp=datetime.utcnow().isoformat(),
            project=project,
            agent=agent,
            stage=stage,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            model=model,
            metadata=metadata or {},
        )
        
        # Append to usage log
        with open(self.usage_file, "a") as f:
            f.write(json.dumps(asdict(usage)) + "\n")
        
        # Update summary
        data = self._load_budgets()
        if project not in data["usage"]:
            data["usage"][project] = {"total_cost": 0.0, "total_tokens": 0}
        data["usage"][project]["total_cost"] += cost
        data["usage"][project]["total_tokens"] += usage.total_tokens
        self._save_budgets(data)
        
        return usage
    
    def get_project_spend(self, project: str) -> float:
        """Get total spend for a project."""
        data = self._load_budgets()
        return data.get("usage", {}).get(project, {}).get("total_cost", 0.0)
    
    def get_period_spend(self, period: BudgetPeriod) -> float:
        """Get total spend for a time period."""
        if not self.usage_file.exists():
            return 0.0
        
        now = datetime.utcnow()
        if period == BudgetPeriod.HOURLY:
            cutoff = now - timedelta(hours=1)
        elif period == BudgetPeriod.DAILY:
            cutoff = now - timedelta(days=1)
        elif period == BudgetPeriod.WEEKLY:
            cutoff = now - timedelta(weeks=1)
        elif period == BudgetPeriod.MONTHLY:
            cutoff = now - timedelta(days=30)
        else:
            cutoff = now - timedelta(days=1)
        
        total = 0.0
        with open(self.usage_file) as f:
            for line in f:
                try:
                    usage = json.loads(line)
                    if datetime.fromisoformat(usage["timestamp"]) >= cutoff:
                        total += usage["cost_usd"]
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue
        
        return round(total, 2)
    
    def check_budget(
        self, project: str, estimated_cost: float = 0.0
    ) -> tuple[bool, dict]:
        """
        Check if a project is within budget.
        
        Returns:
            (within_budget, status_dict)
        """
        project_spend = self.get_project_spend(project) + estimated_cost
        project_budget = self.get_budget(BudgetPeriod.PER_PROJECT.value)
        
        hourly_spend = self.get_period_spend(BudgetPeriod.HOURLY) + estimated_cost
        hourly_budget = self.get_budget(BudgetPeriod.HOURLY.value)
        
        daily_spend = self.get_period_spend(BudgetPeriod.DAILY) + estimated_cost
        daily_budget = self.get_budget(BudgetPeriod.DAILY.value)
        
        status = {
            "project": {
                "spent": round(project_spend, 2),
                "limit": project_budget,
                "remaining": round(project_budget - project_spend, 2),
                "within_budget": project_spend <= project_budget,
            },
            "hourly": {
                "spent": round(hourly_spend, 2),
                "limit": hourly_budget,
                "remaining": round(hourly_budget - hourly_spend, 2),
                "within_budget": hourly_spend <= hourly_budget,
            },
            "daily": {
                "spent": round(daily_spend, 2),
                "limit": daily_budget,
                "remaining": round(daily_budget - daily_spend, 2),
                "within_budget": daily_spend <= daily_budget,
            },
        }
        
        within_budget = all(
            status[k]["within_budget"] for k in ["project", "hourly", "daily"]
        )
        
        return within_budget, status
    
    def get_recent_usage(self, project: Optional[str] = None, limit: int = 100) -> list[dict]:
        """Get recent usage entries."""
        if not self.usage_file.exists():
            return []
        
        usages = []
        with open(self.usage_file) as f:
            for line in f:
                try:
                    usage = json.loads(line)
                    if project is None or usage.get("project") == project:
                        usages.append(usage)
                except (json.JSONDecodeError, OSError):
                    continue
        
        return usages[-limit:]
    
    def get_summary(self) -> dict:
        """Get overall budget summary."""
        data = self._load_budgets()
        return {
            "budgets": data.get("budgets", {}),
            "project_spend": data.get("usage", {}),
            "period_spend": {
                "hourly": self.get_period_spend(BudgetPeriod.HOURLY),
                "daily": self.get_period_spend(BudgetPeriod.DAILY),
                "weekly": self.get_period_spend(BudgetPeriod.WEEKLY),
            },
        }
