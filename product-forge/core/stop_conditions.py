"""
Stop Conditions and Human Escalation - Phase 1.8

Defines conditions under which agents should stop and escalate to humans,
rather than continuing to spend tokens on a failing task.

Phase 1.8 (CRITICAL): Stop Conditions - prevents infinite loops and
excessive token spend on failing operations.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field, asdict
from enum import Enum


class StopReason(str, Enum):
    """Reasons why an agent should stop."""
    MAX_RETRIES = "max_retries"
    MAX_TOKENS = "max_tokens"
    MAX_DURATION = "max_duration"
    MAX_COST = "max_cost"
    CIRCUIT_OPEN = "circuit_open"
    HUMAN_REQUIRED = "human_required"
    VALIDATION_FAILED = "validation_failed"
    BUDGET_EXCEEDED = "budget_exceeded"
    DEADLOCK = "deadlock"
    LOW_CONFIDENCE = "low_confidence"
    UNKNOWN_ERROR = "unknown_error"


class EscalationPriority(str, Enum):
    """Priority of human escalation."""
    LOW = "low"           # Informational
    MEDIUM = "medium"     # Should review when convenient
    HIGH = "high"         # Needs attention soon
    URGENT = "urgent"     # Block pipeline until reviewed
    CRITICAL = "critical" # Production-impacting, immediate


@dataclass
class StopCondition:
    """A condition that triggers stopping."""
    name: str
    metric: str  # "retries", "tokens", "duration_seconds", "cost_usd", "failures"
    threshold: float
    enabled: bool = True
    action: str = "stop"  # "stop", "escalate", "circuit_break"
    message: str = ""


@dataclass
class EscalationRequest:
    """A request for human review."""
    id: str
    project: str
    stage: int
    agent: str
    reason: str
    priority: str
    context: dict
    created_at: str
    status: str = "pending"  # pending, acknowledged, resolved, dismissed
    assigned_to: Optional[str] = None
    resolution: Optional[str] = None
    resolved_at: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class StopConditionManager:
    """
    Manages stop conditions and human escalation for agent operations.
    
    Phase 1.8: Stops runaway agents and escalates to humans when needed.
    """
    
    DEFAULT_CONDITIONS = [
        StopCondition(
            name="max_retries_per_agent",
            metric="retries",
            threshold=100,  # High threshold - not used as primary stop condition
            action="stop",
            message="Agent has retried 100 times without success",
        ),
        StopCondition(
            name="max_tokens_per_stage",
            metric="tokens",
            threshold=500000,
            action="stop",
            message="Stage has exceeded 500K tokens",
        ),
        StopCondition(
            name="max_duration_per_stage",
            metric="duration_seconds",
            threshold=3600,  # 1 hour
            action="stop",
            message="Stage has run for over 1 hour",
        ),
        StopCondition(
            name="max_cost_per_stage",
            metric="cost_usd",
            threshold=10.0,
            action="stop",
            message="Stage has spent over $10",
        ),
        StopCondition(
            name="consecutive_failures",
            metric="failures",
            threshold=5,
            action="circuit_break",
            message="5 consecutive failures detected",
        ),
        StopCondition(
            name="low_confidence_threshold",
            metric="confidence",
            threshold=0.5,
            action="escalate",
            message="Agent confidence below 50%",
        ),
    ]
    
    def __init__(self, products_dir: str = "products"):
        self.products_dir = Path(products_dir)
        self.conditions_file = self.products_dir / ".pipeline" / "stop_conditions.json"
        self.escalations_file = self.products_dir / ".pipeline" / "escalations.jsonl"
        self.conditions_file.parent.mkdir(parents=True, exist_ok=True)
        
        if not self.conditions_file.exists():
            self._initialize()
        
        self.conditions: list[StopCondition] = self._load_conditions()
        self._metrics: dict[str, dict] = {}  # project -> {metric: value}
    
    def _initialize(self) -> None:
        """Initialize default conditions."""
        data = {
            "conditions": [asdict(c) for c in self.DEFAULT_CONDITIONS],
            "created_at": datetime.utcnow().isoformat(),
        }
        self.conditions_file.write_text(json.dumps(data, indent=2, default=str))
    
    def _load_conditions(self) -> list[StopCondition]:
        """Load conditions from file."""
        try:
            data = json.loads(self.conditions_file.read_text())
            return [StopCondition(**c) for c in data.get("conditions", [])]
        except (json.JSONDecodeError, OSError, TypeError):
            self._initialize()
            return list(self.DEFAULT_CONDITIONS)
    
    def check_conditions(
        self,
        project: str,
        stage: int,
        metrics: dict,
    ) -> tuple[bool, list[StopCondition]]:
        """
        Check if any stop conditions are triggered.
        
        Args:
            project: Project name
            stage: Current stage
            metrics: Dict of metric name -> current value
        
        Returns:
            (should_stop, list of triggered conditions)
        """
        triggered = []
        
        for condition in self.conditions:
            if not condition.enabled:
                continue
            
            value = metrics.get(condition.metric, 0)
            if value >= condition.threshold:
                triggered.append(condition)
        
        should_stop = any(c.action in ["stop", "circuit_break"] for c in triggered)
        return should_stop, triggered
    
    def record_metric(self, project: str, agent: str, metric: str, value: float) -> None:
        """Record a metric value for an agent."""
        if project not in self._metrics:
            self._metrics[project] = {}
        key = f"{agent}:{metric}"
        self._metrics[project][key] = value
    
    def get_metrics(self, project: str) -> dict:
        """Get all metrics for a project."""
        return self._metrics.get(project, {})
    
    def should_escalate(
        self,
        reason: str,
        confidence: Optional[float] = None,
        context: Optional[dict] = None,
    ) -> bool:
        """Determine if an operation should be escalated to humans."""
        escalation_triggers = [
            reason == StopReason.HUMAN_REQUIRED.value,
            reason == StopReason.LOW_CONFIDENCE.value,
            reason == StopReason.VALIDATION_FAILED.value,
            confidence is not None and confidence < 0.5,
        ]
        return any(escalation_triggers)
    
    def escalate(
        self,
        project: str,
        stage: int,
        agent: str,
        reason: str,
        priority: str = EscalationPriority.MEDIUM.value,
        context: Optional[dict] = None,
    ) -> EscalationRequest:
        """Create a human escalation request."""
        import uuid
        request_id = f"esc_{uuid.uuid4().hex[:12]}"
        
        request = EscalationRequest(
            id=request_id,
            project=project,
            stage=stage,
            agent=agent,
            reason=reason,
            priority=priority,
            context=context or {},
            created_at=datetime.utcnow().isoformat(),
        )
        
        # Append to file
        with open(self.escalations_file, "a") as f:
            f.write(json.dumps(asdict(request)) + "\n")
        
        return request
    
    def list_escalations(
        self,
        project: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> list[EscalationRequest]:
        """List escalation requests with optional filters."""
        if not self.escalations_file.exists():
            return []
        
        requests = []
        with open(self.escalations_file) as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if project and data.get("project") != project:
                        continue
                    if status and data.get("status") != status:
                        continue
                    if priority and data.get("priority") != priority:
                        continue
                    requests.append(EscalationRequest(**data))
                except (json.JSONDecodeError, OSError, TypeError):
                    continue
        
        return requests
    
    def resolve_escalation(
        self,
        request_id: str,
        resolution: str,
        assigned_to: Optional[str] = None,
    ) -> bool:
        """Mark an escalation as resolved."""
        if not self.escalations_file.exists():
            return False
        
        # Read all lines
        lines = []
        found = False
        with open(self.escalations_file) as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if data.get("id") == request_id:
                        data["status"] = "resolved"
                        data["resolution"] = resolution
                        data["resolved_at"] = datetime.utcnow().isoformat()
                        if assigned_to:
                            data["assigned_to"] = assigned_to
                        found = True
                    lines.append(json.dumps(data))
                except json.JSONDecodeError:
                    continue
        
        if found:
            self.escalations_file.write_text("\n".join(lines) + "\n")
        
        return found
    
    def get_escalation_stats(self) -> dict:
        """Get escalation statistics."""
        requests = self.list_escalations()
        
        return {
            "total": len(requests),
            "pending": sum(1 for r in requests if r.status == "pending"),
            "resolved": sum(1 for r in requests if r.status == "resolved"),
            "by_priority": {
                p.value: sum(1 for r in requests if r.priority == p.value)
                for p in EscalationPriority
            },
            "by_agent": {
                agent: sum(1 for r in requests if r.agent == agent)
                for agent in {r.agent for r in requests}
            },
        }
