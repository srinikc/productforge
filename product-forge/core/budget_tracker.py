"""
Budget Tracker
API spend tracking and budget-aware scheduling
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta


@dataclass
class BudgetWindow:
    """Budget window configuration"""
    name: str
    limit: float
    window_hours: int
    current_spend: float
    window_start: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SpendRecord:
    """Spend record"""
    project: str
    agent: str
    model: str
    tokens_input: int
    tokens_output: int
    cost: float
    timestamp: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BudgetTracker:
    """
    Budget tracker for API spend management.
    
    Features:
    - Multi-window budget tracking (hourly, daily, weekly, monthly)
    - Per-project spend tracking
    - Budget-aware scheduling
    - Spend alerts
    """
    
    def __init__(self, products_dir: str = "products"):
        """
        Initialize budget tracker.
        
        Args:
            products_dir: Path to products directory
        """
        self.products_dir = Path(products_dir)
        self.budget_path = self.products_dir / "budget.json"
        self._ensure_budget()
    
    def _ensure_budget(self):
        """Ensure budget file exists with defaults"""
        if not self.budget_path.exists():
            default_budget = {
                "windows": {
                    "hourly": {
                        "name": "Hourly",
                        "limit": 12.0,
                        "window_hours": 5,
                        "current_spend": 0.0,
                        "window_start": datetime.now().isoformat()
                    },
                    "daily": {
                        "name": "Daily",
                        "limit": 30.0,
                        "window_hours": 168,  # 1 week
                        "current_spend": 0.0,
                        "window_start": datetime.now().isoformat()
                    },
                    "weekly": {
                        "name": "Weekly",
                        "limit": 60.0,
                        "window_hours": 720,  # 30 days
                        "current_spend": 0.0,
                        "window_start": datetime.now().isoformat()
                    }
                },
                "per_project": {},
                "spend_history": [],
                "alerts": []
            }
            self._save_budget(default_budget)
    
    def _load_budget(self) -> Dict[str, Any]:
        """Load the global budget from the unified store (products/budget.json)."""
        try:
            from core import budget as _b
            _b.migrate_legacy(None, str(self.products_dir))
            limits = _b.read_section(None, "limits", str(self.products_dir))
            usage = _b.read_section(None, "usage", str(self.products_dir))
            state = _b.read_section(None, "state", str(self.products_dir))
            hist = _b.read_section(None, "history", str(self.products_dir))
            return {"windows": limits.get("windows", {}),
                    "per_project": usage.get("per_project", {}),
                    "spend_history": hist if isinstance(hist, list) else [],
                    "alerts": state.get("alerts", [])}
        except Exception:
            return {"windows": {}, "per_project": {}, "spend_history": [], "alerts": []}

    def _save_budget(self, budget: Dict[str, Any]):
        """Persist the global budget into the unified store sections."""
        try:
            from core import budget as _b
            _b.update_section(None, "limits", {"windows": budget.get("windows", {})}, str(self.products_dir))
            _b.update_section(None, "usage", {"per_project": budget.get("per_project", {})}, str(self.products_dir))
            _b.update_section(None, "state", {"alerts": budget.get("alerts", [])}, str(self.products_dir))
            hist = budget.get("spend_history", [])
            if hist:
                cur = _b.read_section(None, "history", str(self.products_dir))
                if len(cur) < len(hist):
                    data = _b.load(None, str(self.products_dir))
                    data["history"] = hist[-5000:]
                    _b.save(None, data, str(self.products_dir))
        except Exception as e:
            raise Exception(f"Failed to save budget: {e}")
    
    def _check_window_expiry(self, budget: Dict[str, Any]) -> Dict[str, Any]:
        """Check and reset expired budget windows"""
        now = datetime.now()
        
        for window_name, window in budget.get("windows", {}).items():
            try:
                window_start_str = window["window_start"].replace("Z", "+00:00")
                window_start = datetime.fromisoformat(window_start_str).replace(tzinfo=None)
                window_duration = timedelta(hours=window.get("window_hours", 24))
                
                if now - window_start > window_duration:
                    # Window expired, reset
                    window["current_spend"] = 0.0
                    window["window_start"] = now.isoformat()
            except Exception:
                pass
        
        return budget
    
    def record_spend(
        self,
        project: str,
        agent: str,
        model: str,
        tokens_input: int,
        tokens_output: int,
        cost: float
    ) -> bool:
        """
        Record API spend.
        
        Args:
            project: Project name
            agent: Agent name
            model: Model identifier
            tokens_input: Input tokens used
            tokens_output: Output tokens used
            cost: Cost in dollars
            
        Returns:
            True if recorded successfully
        """
        budget = self._load_budget()
        budget = self._check_window_expiry(budget)
        
        # Ensure required keys exist
        if "windows" not in budget:
            budget["windows"] = {}
        if "per_project" not in budget:
            budget["per_project"] = {}
        if "spend_history" not in budget:
            budget["spend_history"] = []
        if "alerts" not in budget:
            budget["alerts"] = []
        
        # Update windows
        for window_name in budget.get("windows", {}):
            budget["windows"][window_name]["current_spend"] += cost
        
        # Update per-project
        if project not in budget["per_project"]:
            budget["per_project"][project] = 0.0
        budget["per_project"][project] += cost
        
        # Add to history (keep last 1000 records)
        record = SpendRecord(
            project=project,
            agent=agent,
            model=model,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            cost=cost,
            timestamp=datetime.now().isoformat()
        )
        budget["spend_history"].append(record.to_dict())
        if len(budget["spend_history"]) > 1000:
            budget["spend_history"] = budget["spend_history"][-1000:]
        
        # Check for alerts
        self._check_alerts(budget)
        
        self._save_budget(budget)
        return True
    
    def _check_alerts(self, budget: Dict[str, Any]):
        """Check for budget alerts"""
        alerts = []
        
        for window_name, window in budget.get("windows", {}).items():
            if window.get("limit", 0) > 0:
                usage_percent = (window.get("current_spend", 0) / window["limit"]) * 100
                
                if usage_percent >= 90:
                    alerts.append({
                        "type": "critical",
                        "window": window_name,
                        "message": f"{window.get('name', window_name)} budget at {usage_percent:.1f}%"
                    })
                elif usage_percent >= 75:
                    alerts.append({
                        "type": "warning",
                        "window": window_name,
                        "message": f"{window['name']} budget at {usage_percent:.1f}%"
                    })
        
        budget["alerts"] = alerts
    
    def can_spend(self, amount: float) -> bool:
        """
        Check if we can spend the given amount.
        
        Args:
            amount: Amount to spend
            
        Returns:
            True if spending is within budget
        """
        budget = self._load_budget()
        budget = self._check_window_expiry(budget)
        
        # Check all windows
        for window_name, window in budget["windows"].items():
            if window["current_spend"] + amount > window["limit"]:
                return False
        
        return True
    
    def get_remaining_budget(self) -> float:
        """
        Get minimum remaining budget across all windows.
        
        Returns:
            Remaining budget in dollars
        """
        budget = self._load_budget()
        budget = self._check_window_expiry(budget)
        
        min_remaining = float('inf')
        for window_name, window in budget["windows"].items():
            remaining = window["limit"] - window["current_spend"]
            min_remaining = min(min_remaining, remaining)
        
        return max(0, min_remaining)
    
    def get_project_spend(self, project: str) -> float:
        """
        Get total spend for a project.
        
        Args:
            project: Project name
            
        Returns:
            Total spend in dollars
        """
        budget = self._load_budget()
        return budget.get("per_project", {}).get(project, 0.0)
    
    def get_window_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all budget windows.
        
        Returns:
            Window status dictionary
        """
        budget = self._load_budget()
        budget = self._check_window_expiry(budget)
        
        status = {}
        for window_name, window in budget["windows"].items():
            remaining = window["limit"] - window["current_spend"]
            usage_percent = (window["current_spend"] / window["limit"]) * 100 if window["limit"] > 0 else 0
            
            status[window_name] = {
                "name": window["name"],
                "limit": window["limit"],
                "spent": window["current_spend"],
                "remaining": remaining,
                "usage_percent": usage_percent,
                "window_start": window["window_start"],
                "window_hours": window["window_hours"]
            }
        
        return status
    
    def get_alerts(self) -> List[Dict[str, Any]]:
        """
        Get current budget alerts.
        
        Returns:
            List of alerts
        """
        budget = self._load_budget()
        return budget.get("alerts", [])
    
    def set_budget_limit(self, window_name: str, limit: float) -> bool:
        """
        Set budget limit for a window.
        
        Args:
            window_name: Window identifier
            limit: New limit in dollars
            
        Returns:
            True if updated successfully
        """
        budget = self._load_budget()
        
        if window_name in budget["windows"]:
            budget["windows"][window_name]["limit"] = limit
            self._save_budget(budget)
            return True
        
        return False
