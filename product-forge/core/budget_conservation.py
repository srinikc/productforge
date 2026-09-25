"""Budget Conservation - Graceful degradation when approaching budget limits.

When budget approaches limits, Product Forge can:
- Stop unnecessary agents
- Reduce optional reviews
- Use cheaper models
- Stop additional iterations
- Produce final result with known limitations
"""
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path


@dataclass
class ConservationAction:
    """An action to take when budget is low."""
    action: str  # skip_agent, reduce_review, use_cheaper_model, stop_iterations, finalize
    target: str  # agent_id or review_type
    reason: str
    savings_estimate: float = 0.0  # estimated token savings


@dataclass
class ConservationState:
    """Current conservation state."""
    mode: str = "normal"  # normal, conservative, critical, emergency
    budget_used_percent: float = 0.0
    actions_taken: List[ConservationAction] = field(default_factory=list)
    skipped_agents: List[str] = field(default_factory=list)
    reduced_reviews: List[str] = field(default_factory=list)
    model_downgrades: List[str] = field(default_factory=list)
    created_at: str = ""


# Conservation thresholds
CONSERVATION_THRESHOLDS = {
    "conservative": 70.0,  # 70% budget used
    "critical": 85.0,      # 85% budget used
    "emergency": 95.0,     # 95% budget used
}

# Actions per conservation mode
CONSERVATION_ACTIONS = {
    "conservative": [
        ConservationAction("reduce_review", "design_critic", "Reduce design critic to critical checks only", 500),
        ConservationAction("reduce_review", "visual_qa", "Reduce visual QA to essential checks only", 300),
    ],
    "critical": [
        ConservationAction("skip_agent", "design_critic", "Skip design critic review", 1000),
        ConservationAction("skip_agent", "visual_qa", "Skip visual QA", 800),
        ConservationAction("use_cheaper_model", "implement", "Use cheaper model for implementation", 2000),
        ConservationAction("reduce_review", "code_review", "Reduce code review to critical issues only", 500),
    ],
    "emergency": [
        ConservationAction("skip_agent", "design_critic", "Skip design critic", 1000),
        ConservationAction("skip_agent", "visual_qa", "Skip visual QA", 800),
        ConservationAction("skip_agent", "code_review", "Skip code review", 1500),
        ConservationAction("skip_agent", "document", "Skip documentation generation", 500),
        ConservationAction("stop_iterations", "all", "Stop all iteration loops", 5000),
        ConservationAction("finalize", "pipeline", "Finalize with current state", 0),
    ],
}


def determine_conservation_mode(budget_used_percent: float) -> str:
    """Determine conservation mode based on budget usage."""
    if budget_used_percent >= CONSERVATION_THRESHOLDS["emergency"]:
        return "emergency"
    elif budget_used_percent >= CONSERVATION_THRESHOLDS["critical"]:
        return "critical"
    elif budget_used_percent >= CONSERVATION_THRESHOLDS["conservative"]:
        return "conservative"
    else:
        return "normal"


def get_conservation_actions(mode: str) -> List[ConservationAction]:
    """Get actions to take for a conservation mode."""
    return CONSERVATION_ACTIONS.get(mode, [])


def should_skip_agent(agent_id: str, conservation_state: ConservationState) -> bool:
    """Check if an agent should be skipped based on conservation state."""
    if conservation_state.mode == "normal":
        return False
    
    actions = get_conservation_actions(conservation_state.mode)
    for action in actions:
        if action.action == "skip_agent" and action.target == agent_id:
            return True
    
    return False


def should_reduce_review(review_type: str, conservation_state: ConservationState) -> bool:
    """Check if a review should be reduced based on conservation state."""
    if conservation_state.mode == "normal":
        return False
    
    actions = get_conservation_actions(conservation_state.mode)
    for action in actions:
        if action.action == "reduce_review" and action.target == review_type:
            return True
    
    return False


def get_model_downgrade(agent_id: str, conservation_state: ConservationState) -> Optional[str]:
    """Get a cheaper model for an agent based on conservation state."""
    if conservation_state.mode not in ["critical", "emergency"]:
        return None
    
    # Map agents to cheaper models
    downgrade_map = {
        "implement": "gpt-4o-mini",
        "design": "gpt-4o-mini",
        "architect": "gpt-4o-mini",
        "code_review": "gpt-4o-mini",
    }
    
    return downgrade_map.get(agent_id)


def apply_conservation_actions(conservation_state: ConservationState, 
                               budget_used_percent: float) -> ConservationState:
    """Apply conservation actions based on current budget usage."""
    new_mode = determine_conservation_mode(budget_used_percent)
    
    if new_mode != conservation_state.mode:
        conservation_state.mode = new_mode
        conservation_state.actions_taken.extend(get_conservation_actions(new_mode))
    
    conservation_state.budget_used_percent = budget_used_percent
    
    return conservation_state


def generate_conservation_report(state: ConservationState) -> str:
    """Generate a conservation status report."""
    report = f"""# Budget Conservation Report

## Current Mode: {state.mode.upper()}

## Budget Usage: {state.budget_used_percent:.1f}%

## Thresholds
- Conservative: {CONSERVATION_THRESHOLDS['conservative']}%
- Critical: {CONSERVATION_THRESHOLDS['critical']}%
- Emergency: {CONSERVATION_THRESHOLDS['emergency']}%

## Actions Taken

"""
    for action in state.actions_taken:
        report += f"- **{action.action}** on {action.target}: {action.reason}\n"
    
    if state.skipped_agents:
        report += "\n## Skipped Agents\n\n"
        for agent in state.skipped_agents:
            report += f"- {agent}\n"
    
    if state.reduced_reviews:
        report += "\n## Reduced Reviews\n\n"
        for review in state.reduced_reviews:
            report += f"- {review}\n"
    
    if state.model_downgrades:
        report += "\n## Model Downgrades\n\n"
        for downgrade in state.model_downgrades:
            report += f"- {downgrade}\n"
    
    return report


def conservation_state_to_dict(state: ConservationState) -> Dict:
    """Convert conservation state to dict for serialization."""
    return {
        "mode": state.mode,
        "budget_used_percent": state.budget_used_percent,
        "actions_taken": [{"action": a.action, "target": a.target, "reason": a.reason, "savings_estimate": a.savings_estimate} for a in state.actions_taken],
        "skipped_agents": state.skipped_agents,
        "reduced_reviews": state.reduced_reviews,
        "model_downgrades": state.model_downgrades,
        "created_at": state.created_at,
    }


def create_conservation_state() -> ConservationState:
    """Create a new conservation state."""
    return ConservationState(
        mode="normal",
        budget_used_percent=0.0,
        created_at=datetime.now().isoformat(),
    )


if __name__ == "__main__":
    # Test conservation
    state = create_conservation_state()
    print(f"Initial mode: {state.mode}")
    
    # Simulate budget usage
    state = apply_conservation_actions(state, 75.0)
    print(f"After 75%: {state.mode}")
    
    state = apply_conservation_actions(state, 90.0)
    print(f"After 90%: {state.mode}")
    print(f"Actions taken: {len(state.actions_taken)}")
    
    # Generate report
    report = generate_conservation_report(state)
    print(f"\nReport generated ({len(report)} chars)")
