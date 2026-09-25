"""
Token Budget Allocator - Phase 2.4

Dynamically reallocates token budgets across stages/agents based on
priority, complexity, and historical performance.

Phase 2.4 (IMPORTANT): Dynamic Token Budget - ensures critical stages
get enough tokens while limiting wasteful stages.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field, asdict
from enum import Enum


class AllocationStrategy(str, Enum):
    """Strategy for budget allocation."""
    EQUAL = "equal"                  # Equal split across stages
    PRIORITY = "priority"            # Based on stage priority
    HISTORICAL = "historical"        # Based on past usage
    ADAPTIVE = "adaptive"            # Adjusts based on current usage
    MANUAL = "manual"                # Manually configured


@dataclass
class StageAllocation:
    """Token budget allocation for a stage."""
    stage: int
    stage_name: str
    allocated_tokens: int
    used_tokens: int = 0
    priority: int = 50
    complexity: int = 50  # 0-100
    metadata: dict = field(default_factory=dict)
    
    @property
    def remaining(self) -> int:
        return max(0, self.allocated_tokens - self.used_tokens)
    
    @property
    def utilization(self) -> float:
        if self.allocated_tokens == 0:
            return 0.0
        return self.used_tokens / self.allocated_tokens


@dataclass
class BudgetReallocation:
    """A budget reallocation event."""
    timestamp: str
    from_stage: int
    to_stage: int
    tokens: int
    reason: str


class TokenBudgetAllocator:
    """
    Manages dynamic token budget allocation across stages.
    
    Phase 2.4: Ensures critical stages have enough tokens by reallocating
    from under-utilizing stages.
    """
    
    ALLOCATIONS_FILE = "budget_allocations.json"
    TOTAL_BUDGET_DEFAULT = 1_000_000  # 1M tokens per project
    
    # Default stage priorities (higher = more tokens)
    STAGE_PRIORITIES = {
        0: 60,   # Ideation
        1: 70,   # Design
        2: 90,   # Architect (critical)
        3: 70,   # Review
        4: 100,  # Implement (most critical)
        5: 80,   # Code Review
        6: 70,   # Validate
        7: 70,   # Fix
        8: 50,   # Document
        9: 40,   # Package
    }
    
    STAGE_NAMES = {
        0: "Ideation",
        1: "Design",
        2: "Architect",
        3: "Review",
        4: "Implement",
        5: "Code Review",
        6: "Validate",
        7: "Fix",
        8: "Document",
        9: "Package",
    }
    
    def __init__(self, project: str, products_dir: str = "products"):
        self.project = project
        self.products_dir = Path(products_dir)
        self.allocations_file = self.products_dir / project / self.ALLOCATIONS_FILE
        self.allocations_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.allocations: dict[int, StageAllocation] = {}
        self.history: list[BudgetReallocation] = []
        self._load()
    
    def _load(self) -> None:
        """Load allocations from the unified budget store (section: allocations)."""
        try:
            from core import budget as _b
            _b.migrate_legacy(self.project, str(self.products_dir))
            data = _b.read_section(self.project, "allocations", str(self.products_dir))
            for a in data.get("stages", data.get("allocations", [])):
                try:
                    self.allocations[a["stage"]] = StageAllocation(**a)
                except TypeError:
                    continue
        except Exception:
            pass

    def _save(self) -> None:
        """Save allocations into the unified budget store (section: allocations)."""
        try:
            from core import budget as _b
            _b.update_section(self.project, "allocations", {
                "stages": [asdict(a) for a in self.allocations.values()],
                "updated_at": datetime.utcnow().isoformat()}, str(self.products_dir))
        except Exception:
            pass
    
    def initialize_allocations(
        self,
        strategy: str = AllocationStrategy.PRIORITY.value,
        total_budget: int = TOTAL_BUDGET_DEFAULT,
    ) -> dict[int, StageAllocation]:
        """
        Initialize stage allocations based on strategy.
        """
        if strategy == AllocationStrategy.EQUAL.value:
            per_stage = total_budget // 10
            self.allocations = {
                stage: StageAllocation(
                    stage=stage,
                    stage_name=self.STAGE_NAMES.get(stage, f"Stage {stage}"),
                    allocated_tokens=per_stage,
                    priority=50,
                )
                for stage in range(10)
            }
        elif strategy == AllocationStrategy.PRIORITY.value:
            # Distribute based on priority weights
            total_priority = sum(self.STAGE_PRIORITIES.values())
            self.allocations = {}
            for stage in range(10):
                priority = self.STAGE_PRIORITIES.get(stage, 50)
                tokens = int(total_budget * priority / total_priority)
                self.allocations[stage] = StageAllocation(
                    stage=stage,
                    stage_name=self.STAGE_NAMES.get(stage, f"Stage {stage}"),
                    allocated_tokens=tokens,
                    priority=priority,
                )
        
        self._save()
        return self.allocations
    
    def record_usage(self, stage: int, tokens: int) -> None:
        """Record token usage for a stage."""
        if stage not in self.allocations:
            return
        self.allocations[stage].used_tokens += tokens
        self._save()
    
    def reallocate(
        self,
        from_stage: int,
        to_stage: int,
        tokens: int,
        reason: str = "dynamic reallocation",
    ) -> bool:
        """
        Reallocate tokens from one stage to another.
        """
        if from_stage not in self.allocations or to_stage not in self.allocations:
            return False
        
        source = self.allocations[from_stage]
        target = self.allocations[to_stage]
        
        if source.remaining < tokens:
            return False  # Not enough to give
        
        source.allocated_tokens -= tokens
        target.allocated_tokens += tokens
        
        self.history.append(BudgetReallocation(
            timestamp=datetime.utcnow().isoformat(),
            from_stage=from_stage,
            to_stage=to_stage,
            tokens=tokens,
            reason=reason,
        ))
        
        self._save()
        return True
    
    def auto_rebalance(self) -> int:
        """
        Automatically rebalance budgets based on utilization.
        Stages using >80% get more; using <20% give some.
        """
        if not self.allocations:
            return 0
        
        rebalanced = 0
        # Find stages over/under utilized
        over_utilized = [
            (s, a) for s, a in self.allocations.items()
            if a.utilization > 0.8 and a.remaining < a.allocated_tokens * 0.2
        ]
        under_utilized = [
            (s, a) for s, a in self.allocations.items()
            if a.utilization < 0.2 and a.remaining > a.allocated_tokens * 0.5
        ]
        
        for over_stage, over_alloc in over_utilized:
            for under_stage, under_alloc in under_utilized:
                if over_alloc.remaining < 50000:
                    break
                # Transfer 10% of under-utilized's remaining
                transfer = min(
                    int(under_alloc.remaining * 0.1),
                    over_alloc.allocated_tokens // 2,  # Don't over-allocate
                )
                if transfer > 0 and self.reallocate(
                    under_stage, over_stage, transfer,
                    reason=f"auto-rebalance: stage {over_stage} over-utilized"
                ):
                    rebalanced += 1
        
        return rebalanced
    
    def get_allocation(self, stage: int) -> Optional[StageAllocation]:
        """Get allocation for a specific stage."""
        return self.allocations.get(stage)
    
    def get_summary(self) -> dict:
        """Get budget summary."""
        total_allocated = sum(a.allocated_tokens for a in self.allocations.values())
        total_used = sum(a.used_tokens for a in self.allocations.values())
        
        return {
            "total_allocated": total_allocated,
            "total_used": total_used,
            "utilization": round(total_used / max(1, total_allocated) * 100, 1),
            "stages": {
                a.stage: {
                    "name": a.stage_name,
                    "allocated": a.allocated_tokens,
                    "used": a.used_tokens,
                    "remaining": a.remaining,
                    "utilization": round(a.utilization * 100, 1),
                }
                for a in self.allocations.values()
            },
            "reallocation_count": len(self.history),
        }
