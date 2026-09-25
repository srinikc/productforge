"""
Compliance Action Handler

Handles compliance check results and takes appropriate actions:
- CRITICAL: Block stage, retry agent with feedback
- HIGH: Retry once, then require HITL approval
- MEDIUM: Log and require HITL approval
- LOW: Log only

Max retries per agent before escalating to human.
"""
import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path


@dataclass
class RetryState:
    """Track retry state for an agent."""
    agent_id: str
    stage_id: str
    retry_count: int = 0
    max_retries: int = 3
    last_violations: List[Dict] = field(default_factory=list)
    feedback_given: List[str] = field(default_factory=list)
    escalated_to_human: bool = False
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ComplianceAction:
    """Action to take based on compliance result."""
    action: str  # retry, approve, block, escalate, continue
    agent_id: str
    stage_id: str
    reason: str
    violations: List[Dict] = field(default_factory=list)
    feedback_prompt: str = ""
    requires_human: bool = False
    
    def to_dict(self) -> Dict:
        return asdict(self)


class ComplianceActionHandler:
    """Handle compliance results and take appropriate actions."""
    
    def __init__(self, products_dir: str = "products", project: str = "default"):
        self.products_dir = Path(products_dir)
        self.project = project
        self.project_dir = self.products_dir / project
        self.retry_states: Dict[str, RetryState] = {}
        self.state_file = self.project_dir / "compliance-retry-state.json"
        self._load_states()
    
    def _load_states(self):
        """Load retry states from disk."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for key, state in data.items():
                    self.retry_states[key] = RetryState(**state)
            except Exception:
                pass
    
    def _save_states(self):
        """Save retry states to disk."""
        data = {key: state.to_dict() for key, state in self.retry_states.items()}
        os.makedirs(self.project_dir, exist_ok=True)
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _get_retry_key(self, agent_id: str, stage_id: str) -> str:
        return f"{agent_id}_{stage_id}"
    
    def handle_compliance_result(
        self,
        agent_id: str,
        stage_id: str,
        compliance_result: Dict,
        artifacts: List[str],
        auto_approve: bool = False
    ) -> ComplianceAction:
        """Handle compliance result and determine action.
        
        Args:
            agent_id: Agent that was checked
            stage_id: Stage being executed
            compliance_result: Result from compliance check
            artifacts: List of artifact paths generated
            auto_approve: If True, skip HITL for non-critical
            
        Returns:
            ComplianceAction with action to take
        """
        violations = compliance_result.get("violations", [])
        summary = compliance_result.get("summary", {})
        
        critical = [v for v in violations if v.get("severity") == "critical"]
        high = [v for v in violations if v.get("severity") == "high"]
        medium = [v for v in violations if v.get("severity") == "medium"]
        low = [v for v in violations if v.get("severity") == "low"]
        
        retry_key = self._get_retry_key(agent_id, stage_id)
        retry_state = self.retry_states.get(retry_key, RetryState(
            agent_id=agent_id,
            stage_id=stage_id
        ))
        
        # CRITICAL violations - must retry
        if critical:
            if retry_state.retry_count < retry_state.max_retries:
                retry_state.retry_count += 1
                retry_state.last_violations = [v for v in critical]
                self.retry_states[retry_key] = retry_state
                self._save_states()
                
                feedback = self._build_feedback_prompt(agent_id, critical, artifacts)
                return ComplianceAction(
                    action="retry",
                    agent_id=agent_id,
                    stage_id=stage_id,
                    reason=f"CRITICAL violations found ({len(critical)}). Retry {retry_state.retry_count}/{retry_state.max_retries}",
                    violations=critical,
                    feedback_prompt=feedback,
                    requires_human=False
                )
            else:
                # Max retries reached - escalate to human
                retry_state.escalated_to_human = True
                self.retry_states[retry_key] = retry_state
                self._save_states()
                
                return ComplianceAction(
                    action="escalate",
                    agent_id=agent_id,
                    stage_id=stage_id,
                    reason=f"Max retries ({retry_state.max_retries}) reached for CRITICAL violations",
                    violations=critical,
                    requires_human=True
                )
        
        # HIGH violations - retry once, then HITL
        if high:
            if retry_state.retry_count == 0:
                retry_state.retry_count += 1
                retry_state.last_violations = [v for v in high]
                self.retry_states[retry_key] = retry_state
                self._save_states()
                
                feedback = self._build_feedback_prompt(agent_id, high, artifacts)
                return ComplianceAction(
                    action="retry",
                    agent_id=agent_id,
                    stage_id=stage_id,
                    reason=f"HIGH violations found ({len(high)}). Retrying once",
                    violations=high,
                    feedback_prompt=feedback,
                    requires_human=False
                )
            else:
                # Already retried once - require HITL
                if auto_approve:
                    return ComplianceAction(
                        action="continue",
                        agent_id=agent_id,
                        stage_id=stage_id,
                        reason=f"HIGH violations but auto_approve enabled",
                        violations=high,
                        requires_human=False
                    )
                else:
                    return ComplianceAction(
                        action="approve",
                        agent_id=agent_id,
                        stage_id=stage_id,
                        reason=f"HIGH violations require human approval",
                        violations=high,
                        requires_human=True
                    )
        
        # MEDIUM violations - require HITL
        if medium:
            if auto_approve:
                return ComplianceAction(
                    action="continue",
                    agent_id=agent_id,
                    stage_id=stage_id,
                    reason=f"MEDIUM violations but auto_approve enabled",
                    violations=medium,
                    requires_human=False
                )
            else:
                return ComplianceAction(
                    action="approve",
                    agent_id=agent_id,
                    stage_id=stage_id,
                    reason=f"MEDIUM violations require human approval",
                    violations=medium,
                    requires_human=True
                )
        
        # LOW violations - log and continue
        if low:
            return ComplianceAction(
                action="continue",
                agent_id=agent_id,
                stage_id=stage_id,
                reason=f"LOW violations found ({len(low)}). Logged for reference",
                violations=low,
                requires_human=False
            )
        
        # No violations - continue
        return ComplianceAction(
            action="continue",
            agent_id=agent_id,
            stage_id=stage_id,
            reason="All compliance checks passed",
            violations=[],
            requires_human=False
        )
    
    def _build_feedback_prompt(
        self, 
        agent_id: str, 
        violations: List[Dict],
        artifacts: List[str]
    ) -> str:
        """Build feedback prompt for agent to fix violations."""
        violations_text = "\n".join([
            f"- [{v.get('severity', 'unknown').upper()}] {v.get('description', 'Unknown violation')}\n"
            f"  Guideline: {v.get('guideline_file', 'Unknown')}\n"
            f"  Suggestion: {v.get('suggestion', 'Review and fix')}"
            for v in violations
        ])
        
        artifacts_text = "\n".join([f"- {a}" for a in artifacts])
        
        return f"""COMPLIANCE CHECK FAILED - FIX REQUIRED

You have {len(violations)} violations that must be fixed:

VIOLATIONS:
{violations_text}

ARTIFACTS TO FIX:
{artifacts_text}

INSTRUCTIONS:
1. Review each violation above
2. Fix the issues in the artifacts
3. Regenerate the artifacts with fixes applied
4. Ensure all guideline requirements are met

Focus on fixing CRITICAL and HIGH violations first.
MEDIUM and LOW can be addressed if time permits.
"""
    
    def reset_retry_state(self, agent_id: str, stage_id: str):
        """Reset retry state for an agent (e.g., after successful fix)."""
        retry_key = self._get_retry_key(agent_id, stage_id)
        if retry_key in self.retry_states:
            del self.retry_states[retry_key]
            self._save_states()
    
    def get_retry_count(self, agent_id: str, stage_id: str) -> int:
        """Get current retry count for an agent."""
        retry_key = self._get_retry_key(agent_id, stage_id)
        state = self.retry_states.get(retry_key)
        return state.retry_count if state else 0
    
    def has_exceeded_max_retries(self, agent_id: str, stage_id: str) -> bool:
        """Check if agent has exceeded max retries."""
        retry_key = self._get_retry_key(agent_id, stage_id)
        state = self.retry_states.get(retry_key)
        if state:
            return state.retry_count >= state.max_retries
        return False
    
    def get_retry_summary(self) -> Dict[str, Any]:
        """Get summary of all retry states."""
        return {
            "total_agents": len(self.retry_states),
            "agents_with_retries": sum(1 for s in self.retry_states.values() if s.retry_count > 0),
            "agents_escalated": sum(1 for s in self.retry_states.values() if s.escalated_to_human),
            "details": {key: state.to_dict() for key, state in self.retry_states.items()}
        }
