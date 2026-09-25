"""
Budget Protection System

Manages token budgets across the pipeline to prevent:
1. Loading too many knowledge resources (token exhaustion)
2. Agent context overflow
3. Pipeline-wide token overuse

Provides:
- Per-stage token budgets
- Per-agent token budgets
- Per-knowledge-load token budgets
- Budget monitoring and alerts
- Automatic summarization when over budget
"""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum
from pathlib import Path


class BudgetType(str, Enum):
    """Types of token budgets."""
    KNOWLEDGE_LOAD = "knowledge_load"      # Per knowledge load operation
    AGENT_CONTEXT = "agent_context"        # Per agent execution
    STAGE_TOTAL = "stage_total"            # Per pipeline stage
    PIPELINE_TOTAL = "pipeline_total"      # Per pipeline execution
    RESPONSE = "response"                  # Per LLM response


class BudgetStatus(str, Enum):
    """Status of a budget."""
    HEALTHY = "healthy"         # < 70% used
    WARNING = "warning"         # 70-90% used
    CRITICAL = "critical"       # 90-100% used
    EXCEEDED = "exceeded"       # > 100% used


@dataclass
class TokenBudget:
    """A token budget for a specific scope."""
    budget_id: str
    budget_type: BudgetType
    max_tokens: int
    used_tokens: int = 0
    reserved_tokens: int = 0  # Reserved but not yet used
    scope: str = ""            # Stage, agent, or operation name
    
    @property
    def remaining(self) -> int:
        return max(0, self.max_tokens - self.used_tokens - self.reserved_tokens)
    
    @property
    def used_percent(self) -> float:
        if self.max_tokens == 0:
            return 0
        return (self.used_tokens + self.reserved_tokens) / self.max_tokens * 100
    
    @property
    def status(self) -> BudgetStatus:
        pct = self.used_percent
        if pct < 70:
            return BudgetStatus.HEALTHY
        elif pct < 90:
            return BudgetStatus.WARNING
        elif pct < 100:
            return BudgetStatus.CRITICAL
        else:
            return BudgetStatus.EXCEEDED
    
    def can_allocate(self, tokens: int) -> bool:
        """Check if we can allocate the requested tokens."""
        return (self.used_tokens + self.reserved_tokens + tokens) <= self.max_tokens
    
    def reserve(self, tokens: int) -> bool:
        """Reserve tokens for future use."""
        if not self.can_allocate(tokens):
            return False
        self.reserved_tokens += tokens
        return True
    
    def commit(self, reserved_tokens: int) -> bool:
        """Commit reserved tokens as used."""
        if reserved_tokens > self.reserved_tokens:
            return False
        self.reserved_tokens -= reserved_tokens
        self.used_tokens += reserved_tokens
        return True
    
    def release(self, reserved_tokens: int):
        """Release reserved tokens back to available pool."""
        self.reserved_tokens = max(0, self.reserved_tokens - reserved_tokens)


@dataclass
class BudgetAlert:
    """An alert when a budget reaches a threshold."""
    budget_id: str
    budget_type: BudgetType
    status: BudgetStatus
    used_tokens: int
    max_tokens: int
    message: str
    timestamp: str
    scope: str = ""


class BudgetManager:
    """
    Manages token budgets across the pipeline.
    
    Prevents token exhaustion by enforcing budgets at multiple levels:
    - Per knowledge load (max tokens for knowledge resources)
    - Per agent execution (max context for one agent)
    - Per stage (max tokens for all agents in a stage)
    - Per pipeline (max tokens for entire execution)
    """
    
    # Default budget limits (in tokens)
    DEFAULT_LIMITS = {
        BudgetType.KNOWLEDGE_LOAD: 5000,      # 5K tokens per knowledge load
        BudgetType.AGENT_CONTEXT: 8000,        # 8K tokens per agent context
        BudgetType.STAGE_TOTAL: 30000,         # 30K tokens per stage
        BudgetType.PIPELINE_TOTAL: 100000,     # 100K tokens per pipeline
        BudgetType.RESPONSE: 4000,             # 4K tokens per LLM response
    }
    
    def __init__(self, products_dir: str = "products", project: str = "default"):
        self.products_dir = products_dir
        self.project = project
        self.budget_file = Path(products_dir) / project / "budget-tracking.json"
        self.budget_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Active budgets
        self.budgets: Dict[str, TokenBudget] = {}
        
        # Alert history
        self.alerts: List[BudgetAlert] = []
        
        # Total tracking
        self.total_used = 0
        self.total_max = 0
        
        # Load existing state
        self._load()
    
    def _load(self):
        """Load budget state from the unified budget store (section: state)."""
        try:
            from core import budget as _b
            _b.migrate_legacy(self.project, self.products_dir)
            st = _b.read_section(self.project, "state", self.products_dir)
            self.total_used = st.get("total_used", 0)
            self.total_max = st.get("total_max", 0)
            self.alerts = [BudgetAlert(**a) for a in st.get("alerts", [])]
        except Exception:
            pass

    def _save(self):
        """Save budget state into the unified budget store (section: state)."""
        try:
            from core import budget as _b
            _b.update_section(self.project, "state", {
                "total_used": self.total_used,
                "total_max": self.total_max,
                "alerts": [asdict(a) for a in self.alerts[-100:]]}, self.products_dir)
        except Exception:
            pass
    
    def create_budget(
        self, 
        budget_id: str,
        budget_type: BudgetType,
        max_tokens: int = None,
        scope: str = ""
    ) -> TokenBudget:
        """Create a new budget."""
        if max_tokens is None:
            max_tokens = self.DEFAULT_LIMITS.get(budget_type, 10000)

        # If this id already exists (e.g. re-created per agent run), replace it
        # without double-counting total_max.
        old = self.budgets.get(budget_id)
        if old is not None:
            self.total_max -= old.max_tokens

        budget = TokenBudget(
            budget_id=budget_id,
            budget_type=budget_type,
            max_tokens=max_tokens,
            scope=scope
        )
        self.budgets[budget_id] = budget
        self.total_max += max_tokens
        return budget
    
    def get_budget(self, budget_id: str) -> Optional[TokenBudget]:
        """Get an existing budget."""
        return self.budgets.get(budget_id)
    
    def get_or_create_budget(
        self, 
        budget_id: str,
        budget_type: BudgetType,
        scope: str = ""
    ) -> TokenBudget:
        """Get existing budget or create a new one."""
        if budget_id in self.budgets:
            return self.budgets[budget_id]
        return self.create_budget(budget_id, budget_type, scope=scope)
    
    def request_tokens(
        self, 
        budget_id: str, 
        tokens: int
    ) -> bool:
        """
        Request tokens from a budget. Returns True if approved.
        
        This is the main budget enforcement point.
        If the request exceeds the budget, it will be denied.
        """
        budget = self.budgets.get(budget_id)
        if not budget:
            # No budget tracked - allow but log
            return True
        
        # Check if we can allocate
        if not budget.can_allocate(tokens):
            # Budget would be exceeded
            self._create_alert(
                budget, 
                f"Token request denied: {tokens} tokens would exceed budget "
                f"({budget.used_tokens + budget.reserved_tokens}/{budget.max_tokens})"
            )
            return False
        
        # Reserve tokens
        budget.reserve(tokens)
        return True
    
    def commit_tokens(self, budget_id: str, tokens: int):
        """Commit tokens as used (directly, no reservation needed)."""
        budget = self.budgets.get(budget_id)
        if budget:
            # Only add if it fits
            if budget.used_tokens + tokens <= budget.max_tokens:
                budget.used_tokens += tokens
                self.total_used += tokens
                self._save()
                
                # Check if we need to alert
                if budget.status in (BudgetStatus.CRITICAL, BudgetStatus.EXCEEDED):
                    # Knowledge routing intentionally fills up to its cap, so a
                    # CRITICAL (>=90%) knowledge budget is expected, not an anomaly.
                    if not (budget.budget_type == BudgetType.KNOWLEDGE_LOAD
                            and budget.status == BudgetStatus.CRITICAL):
                        self._create_alert(
                            budget,
                            f"Budget {budget.budget_id} is at {budget.used_percent:.1f}% "
                            f"({budget.used_tokens}/{budget.max_tokens})"
                        )
            else:
                # Truncate to what fits
                actual = budget.max_tokens - budget.used_tokens
                if actual > 0:
                    budget.used_tokens += actual
                    self.total_used += actual
                    self._create_alert(
                        budget,
                        f"Budget {budget.budget_id} truncated to {budget.used_tokens}/{budget.max_tokens}"
                    )
    
    def release_tokens(self, budget_id: str, tokens: int):
        """Release reserved tokens back to available pool."""
        budget = self.budgets.get(budget_id)
        if budget:
            budget.release(tokens)
    
    def get_status(self, budget_id: str) -> Dict:
        """Get status of a specific budget."""
        budget = self.budgets.get(budget_id)
        if not budget:
            return {"error": "Budget not found"}
        
        return {
            "budget_id": budget.budget_id,
            "budget_type": budget.budget_type.value,
            "max_tokens": budget.max_tokens,
            "used_tokens": budget.used_tokens,
            "reserved_tokens": budget.reserved_tokens,
            "remaining": budget.remaining,
            "used_percent": budget.used_percent,
            "status": budget.status.value,
            "scope": budget.scope
        }
    
    def get_all_statuses(self) -> List[Dict]:
        """Get status of all budgets."""
        return [self.get_status(bid) for bid in self.budgets.keys()]
    
    def get_total_usage(self) -> Dict:
        """Get total usage across all budgets."""
        return {
            "total_used": self.total_used,
            "total_max": self.total_max,
            "used_percent": (self.total_used / self.total_max * 100) if self.total_max > 0 else 0,
            "active_budgets": len(self.budgets),
            "alerts": len(self.alerts)
        }
    
    def get_alerts(self, status: BudgetStatus = None) -> List[BudgetAlert]:
        """Get alerts, optionally filtered by status."""
        if status is None:
            return self.alerts
        return [a for a in self.alerts if a.status == status]
    
    def _create_alert(self, budget: TokenBudget, message: str):
        """Create a budget alert."""
        alert = BudgetAlert(
            budget_id=budget.budget_id,
            budget_type=budget.budget_type,
            status=budget.status,
            used_tokens=budget.used_tokens,
            max_tokens=budget.max_tokens,
            message=message,
            timestamp=datetime.now().isoformat(),
            scope=budget.scope
        )
        self.alerts.append(alert)
        self._save()
        
        # Print warning to console
        print(f"[BUDGET {budget.status.value.upper()}] {message}")
    
    def reset_budget(self, budget_id: str):
        """Reset a specific budget."""
        budget = self.budgets.get(budget_id)
        if budget:
            self.total_used -= budget.used_tokens
            budget.used_tokens = 0
            budget.reserved_tokens = 0
            self._save()
    
    def clear_all(self):
        """Clear all budgets and alerts."""
        self.budgets.clear()
        self.alerts.clear()
        self.total_used = 0
        self.total_max = 0
        self._save()


def safe_knowledge_route(
    router,
    task: str,
    budget_manager: BudgetManager,
    budget_id: str = "knowledge_default",
    max_tokens: int = 5000,
    **kwargs
):
    """
    Safely route knowledge with budget protection.
    
    This is a wrapper around router.route() that enforces budget limits.
    If the estimated tokens would exceed the budget, it reduces the limit
    to fit within the budget.
    """
    # Create or get budget
    budget = budget_manager.get_or_create_budget(
        budget_id,
        BudgetType.KNOWLEDGE_LOAD,
        scope=task[:50]
    )
    
    # Check if budget is already exhausted (used, not reserved)
    if budget.used_tokens >= budget.max_tokens:
        budget_manager._create_alert(
            budget, 
            f"Knowledge routing skipped - budget exhausted "
            f"({budget.used_tokens}/{budget.max_tokens})"
        )
        from core.knowledge_router import RoutingDecision
        return RoutingDecision(
            task_description=task,
            selected_resources=[],
            total_tokens=0,
            confidence=0.0,
            reasoning="Budget exhausted - no knowledge loaded",
            agent=kwargs.get("agent"),
            stage=kwargs.get("stage")
        )
    
    # Calculate how much we can actually use
    available = budget.max_tokens - budget.used_tokens
    actual_max = min(max_tokens, available)
    
    if actual_max <= 0:
        from core.knowledge_router import RoutingDecision
        return RoutingDecision(
            task_description=task,
            selected_resources=[],
            total_tokens=0,
            confidence=0.0,
            reasoning="No budget remaining",
            agent=kwargs.get("agent"),
            stage=kwargs.get("stage")
        )
    
    # Route with the (possibly reduced) max_tokens
    result = router.route(task=task, max_tokens=actual_max, **kwargs)
    
    # Commit the actual tokens used
    budget_manager.commit_tokens(budget_id, result.total_tokens)
    
    return result
