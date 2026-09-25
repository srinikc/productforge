"""
Agent Runtime / Harness
Provides the execution environment for agents around LLMs.
"""

import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any, Callable
from datetime import datetime
from enum import Enum

class AgentState(Enum):
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class _EnumEncoder(json.JSONEncoder):
    """Custom JSON encoder that serializes Enum values via .value."""
    def default(self, obj):
        if isinstance(obj, Enum):
            return obj.value
        return super().default(obj)

@dataclass
class AgentContext:
    task_id: str
    agent_id: str
    goal: str
    constraints: List[str]
    available_tools: List[str]
    max_tokens: int = 10000
    max_cost: float = 1.0  # dollars
    timeout_seconds: int = 300

@dataclass
class ExecutionResult:
    task_id: str
    agent_id: str
    state: AgentState
    output: Any
    tokens_used: int
    cost: float
    duration_seconds: float
    error: str = ""
    verification_passed: bool = False

@dataclass
class AgentCheckpoint:
    checkpoint_id: str
    task_id: str
    agent_id: str
    state: AgentState
    context: AgentContext
    intermediate_results: Dict[str, Any]
    timestamp: str

class AgentRuntime:
    def __init__(self, products_dir: str = "products", project: str = "default"):
        self.products_dir = products_dir
        self.project = project
        self.checkpoint_dir = os.path.join(products_dir, project, "checkpoints")
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        self.hooks: Dict[str, List[Callable]] = {
            "before_execute": [],
            "after_execute": [],
            "on_error": [],
            "before_verify": [],
            "after_verify": []
        }
        self.cost_tracker: Dict[str, float] = {}
    
    def register_hook(self, event: str, hook: Callable):
        """Register a lifecycle hook."""
        if event in self.hooks:
            self.hooks[event].append(hook)
    
    def _trigger_hooks(self, event: str, context: Dict[str, Any]):
        """Trigger lifecycle hooks."""
        for hook in self.hooks.get(event, []):
            try:
                hook(context)
            except Exception as e:
                print(f"Hook error: {e}")
    
    def create_checkpoint(self, task_id: str, agent_id: str, state: AgentState, 
                         context: AgentContext, intermediate_results: Dict) -> str:
        """Create a checkpoint for resume/retry."""
        checkpoint_id = f"cp-{task_id}-{int(time.time())}"
        checkpoint = AgentCheckpoint(
            checkpoint_id=checkpoint_id,
            task_id=task_id,
            agent_id=agent_id,
            state=state,
            context=context,
            intermediate_results=intermediate_results,
            timestamp=datetime.now().isoformat()
        )
        file_path = os.path.join(self.checkpoint_dir, f"{checkpoint_id}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(checkpoint), f, indent=2, ensure_ascii=False, cls=_EnumEncoder)
        return checkpoint_id
    
    def restore_checkpoint(self, checkpoint_id: str) -> Optional[AgentCheckpoint]:
        """Restore from a checkpoint."""
        file_path = os.path.join(self.checkpoint_dir, f"{checkpoint_id}.json")
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Convert state string back to AgentState enum
                if isinstance(data.get("state"), str):
                    try:
                        data["state"] = AgentState(data["state"])
                    except ValueError:
                        data["state"] = AgentState.IDLE
                # Rebuild nested dataclass
                if isinstance(data.get("context"), dict):
                    data["context"] = AgentContext(**data["context"])
                return AgentCheckpoint(**data)
        return None
    
    def check_budget(self, agent_id: str, estimated_cost: float, max_budget: float) -> bool:
        """Check if agent is within budget."""
        current_cost = self.cost_tracker.get(agent_id, 0.0)
        return (current_cost + estimated_cost) <= max_budget
    
    def track_cost(self, agent_id: str, cost: float):
        """Track cost for an agent."""
        self.cost_tracker[agent_id] = self.cost_tracker.get(agent_id, 0.0) + cost
    
    def get_cost_report(self) -> Dict[str, float]:
        """Get cost report for all agents."""
        return dict(self.cost_tracker)
