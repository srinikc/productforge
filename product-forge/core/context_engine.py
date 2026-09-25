"""
Context Engine - Phase 1.7

Formal separation of context from agent logic. Manages what context each agent
sees, with size budgets, summarization, and token tracking.

Phase 1.7 (CRITICAL): Context Engine - separates context preparation from
agent logic, enabling consistent behavior and cost control.
"""
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field, asdict
from enum import Enum


class ContextType(str, Enum):
    """Types of context that can be loaded."""
    SYSTEM = "system"
    PROJECT = "project"
    STAGE = "stage"
    AGENT = "agent"
    PREVIOUS_OUTPUT = "previous_output"
    KNOWLEDGE = "knowledge"
    USER_INPUT = "user_input"


@dataclass
class ContextBudget:
    """Token budget for a context component."""
    context_type: str
    max_tokens: int
    current_tokens: int = 0
    priority: int = 0  # Higher = more important
    
    @property
    def remaining(self) -> int:
        return max(0, self.max_tokens - self.current_tokens)


@dataclass
class ContextItem:
    """A single piece of context."""
    id: str
    context_type: str
    content: str
    tokens: int
    source: str  # File path, agent name, etc.
    priority: int = 0
    created_at: str = ""
    metadata: dict = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()
        if not self.id:
            self.id = hashlib.md5(
                f"{self.source}:{self.content[:100]}".encode()
            ).hexdigest()[:16]


class ContextEngine:
    """
    Engine for managing agent context with budgets and prioritization.
    
    Phase 1.7: Formal context separation from agent logic.
    - Token budgets per context type
    - Priority-based eviction
    - Automatic summarization for over-budget
    - Context sharing across stages
    """
    
    DEFAULT_BUDGETS = {
        ContextType.SYSTEM.value: 2000,
        ContextType.PROJECT.value: 4000,
        ContextType.STAGE.value: 3000,
        ContextType.AGENT.value: 2000,
        ContextType.PREVIOUS_OUTPUT.value: 5000,
        ContextType.KNOWLEDGE.value: 3000,
        ContextType.USER_INPUT.value: 1000,
    }
    
    def __init__(self, products_dir: str = "products"):
        self.products_dir = Path(products_dir)
        self.context_dir = self.products_dir / ".pipeline" / "contexts"
        self.context_dir.mkdir(parents=True, exist_ok=True)
        self.budgets: dict[str, ContextBudget] = {}
        self._initialize_budgets()
    
    def _initialize_budgets(self) -> None:
        """Initialize default token budgets."""
        for ctx_type, max_tokens in self.DEFAULT_BUDGETS.items():
            self.budgets[ctx_type] = ContextBudget(
                context_type=ctx_type,
                max_tokens=max_tokens,
            )
    
    def estimate_tokens(self, text: str) -> int:
        """
        Rough token estimation.
        For accuracy, use tiktoken or model-specific tokenizer.
        """
        if not text:
            return 0
        # Rule of thumb: 1 token ≈ 4 characters for English
        return len(text) // 4 + 1
    
    def add_context(
        self,
        context_type: str,
        content: str,
        source: str,
        priority: int = 0,
        metadata: Optional[dict] = None,
    ) -> Optional[ContextItem]:
        """Add a context item, respecting budgets."""
        tokens = self.estimate_tokens(content)
        budget = self.budgets.get(context_type)
        
        if not budget:
            return None
        
        # If would exceed budget, check priority
        if budget.current_tokens + tokens > budget.max_tokens:
            if priority <= budget.priority:
                return None  # Can't fit and not high enough priority
        
        item = ContextItem(
            id="",
            context_type=context_type,
            content=content,
            tokens=tokens,
            source=source,
            priority=priority,
            metadata=metadata or {},
        )
        
        budget.current_tokens += tokens
        if priority > budget.priority:
            budget.priority = priority
        
        return item
    
    def set_budget(self, context_type: str, max_tokens: int) -> None:
        """Set token budget for a context type."""
        if context_type in self.budgets:
            self.budgets[context_type].max_tokens = max_tokens
        else:
            self.budgets[context_type] = ContextBudget(
                context_type=context_type,
                max_tokens=max_tokens,
            )
    
    def get_budget(self, context_type: str) -> Optional[ContextBudget]:
        """Get current budget for a context type."""
        return self.budgets.get(context_type)
    
    def get_budget_status(self) -> dict:
        """Get status of all context budgets."""
        return {
            ctx_type: {
                "max_tokens": budget.max_tokens,
                "current_tokens": budget.current_tokens,
                "remaining": budget.remaining,
                "utilization": round(
                    budget.current_tokens / budget.max_tokens * 100, 1
                ) if budget.max_tokens > 0 else 0,
            }
            for ctx_type, budget in self.budgets.items()
        }
    
    def prepare_context(
        self,
        system_prompt: str,
        project_context: str,
        stage_context: str,
        agent_context: str = "",
        previous_output: str = "",
        knowledge: str = "",
        user_input: str = "",
    ) -> dict:
        """
        Prepare a complete context package, respecting budgets.
        
        Returns a dict of context_type -> content, only including what fits.
        """
        prepared = {}
        
        # Priority order: system > user_input > agent > stage > project > previous > knowledge
        components = [
            (ContextType.SYSTEM.value, system_prompt, 100),
            (ContextType.USER_INPUT.value, user_input, 90),
            (ContextType.AGENT.value, agent_context, 70),
            (ContextType.STAGE.value, stage_context, 60),
            (ContextType.PROJECT.value, project_context, 50),
            (ContextType.PREVIOUS_OUTPUT.value, previous_output, 40),
            (ContextType.KNOWLEDGE.value, knowledge, 30),
        ]
        
        total_tokens = 0
        max_total = sum(b.max_tokens for b in self.budgets.values())
        
        for ctx_type, content, priority in components:
            if not content:
                continue
            if total_tokens >= max_total:
                break
            
            item = self.add_context(
                context_type=ctx_type,
                content=content,
                source=f"context_engine:{ctx_type}",
                priority=priority,
            )
            if item:
                prepared[ctx_type] = content
                total_tokens += item.tokens
        
        return prepared
    
    def summarize_if_needed(
        self,
        content: str,
        context_type: str,
        max_length: int = 1000,
    ) -> str:
        """
        Summarize content if it exceeds max_length.
        Simple truncation-based fallback (real impl would use LLM).
        """
        if len(content) <= max_length:
            return content
        
        # Keep first 60% and last 40% with marker
        keep_start = int(max_length * 0.6)
        keep_end = max_length - keep_start - 50  # Leave room for marker
        
        return (
            content[:keep_start]
            + "\n\n[... content summarized for context budget ...]\n\n"
            + content[-keep_end:]
        )
    
    def clear_budgets(self) -> None:
        """Reset all context budgets (for new context session)."""
        for budget in self.budgets.values():
            budget.current_tokens = 0
            budget.priority = 0
    
    def get_total_tokens(self) -> int:
        """Get total tokens used across all contexts."""
        return sum(b.current_tokens for b in self.budgets.values())
    
    def get_max_tokens(self) -> int:
        """Get max total tokens available."""
        return sum(b.max_tokens for b in self.budgets.values())
