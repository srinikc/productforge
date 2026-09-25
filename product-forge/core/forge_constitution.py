"""Product Forge Constitution - defines rules, guardrails, and governance for the AI Product Forge.

Encodes the Auto-Company patterns: autonomous execution boundaries,
escalation rules, and quality gates that the Product Forge supervisor enforces.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ConstitutionRule:
    rule_id: str
    name: str
    description: str
    category: str  # execution, quality, budget, safety, escalation
    severity: str  # mandatory, recommended, optional
    enabled: bool = True


@dataclass
class QualityGate:
    gate_id: str
    name: str
    required_score: float  # 0-100
    blocking: bool = True  # If true, pipeline cannot proceed
    description: str = ""


@dataclass
class Constitution:
    version: str
    rules: List[ConstitutionRule] = field(default_factory=list)
    quality_gates: List[QualityGate] = field(default_factory=list)
    max_budget_per_stage: float = 10.0
    max_total_budget: float = 100.0
    max_iterations: int = 100
    allowed_agents: List[str] = field(default_factory=list)
    escalation_threshold: float = 5.0  # Cost above which escalation is needed


DEFAULT_RULES = [
    ConstitutionRule(
        rule_id="R001",
        name="Human-in-the-loop for irreversible actions",
        description="Any action that modifies production systems or deletes data requires human approval",
        category="safety",
        severity="mandatory",
    ),
    ConstitutionRule(
        rule_id="R002",
        name="Budget enforcement",
        description="Pipeline must stop if total cost exceeds budget limit",
        category="budget",
        severity="mandatory",
    ),
    ConstitutionRule(
        rule_id="R003",
        name="Quality gate enforcement",
        description="Pipeline cannot proceed past a quality gate if score is below threshold",
        category="quality",
        severity="mandatory",
    ),
    ConstitutionRule(
        rule_id="R004",
        name="Artifact versioning",
        description="All artifacts must be versioned and checksummed",
        category="execution",
        severity="recommended",
    ),
    ConstitutionRule(
        rule_id="R005",
        name="Context isolation",
        description="Agents must not access artifacts from stages they are not authorized for",
        category="safety",
        severity="mandatory",
    ),
    ConstitutionRule(
        rule_id="R006",
        name="Escalation on cost spike",
        description="If a single stage costs more than threshold, escalate to human",
        category="escalation",
        severity="mandatory",
    ),
    ConstitutionRule(
        rule_id="R007",
        name="Max iterations",
        description="Pipeline must not loop more than max_iterations times",
        category="execution",
        severity="mandatory",
    ),
    ConstitutionRule(
        rule_id="R008",
        name="Design review before implementation",
        description="Design artifacts must pass design critic before implementation begins",
        category="quality",
        severity="recommended",
    ),
    ConstitutionRule(
        rule_id="R009",
        name="Security scan before release",
        description="Security artifacts must be reviewed before release stage",
        category="quality",
        severity="mandatory",
    ),
    ConstitutionRule(
        rule_id="R010",
        name="Memory persistence",
        description="All decisions and outcomes must be persisted to agent memory",
        category="execution",
        severity="recommended",
    ),
]

DEFAULT_QUALITY_GATES = [
    QualityGate(
        gate_id="QG-ideation",
        name="Ideation Complete",
        required_score=50.0,
        blocking=True,
        description="Ideation must produce clear requirements",
    ),
    QualityGate(
        gate_id="QG-design",
        name="Design Approved",
        required_score=60.0,
        blocking=True,
        description="Design must pass critic review",
    ),
    QualityGate(
        gate_id="QG-architecture",
        name="Architecture Review",
        required_score=70.0,
        blocking=True,
        description="Architecture must be reviewed and approved",
    ),
    QualityGate(
        gate_id="QG-implementation",
        name="Implementation Complete",
        required_score=80.0,
        blocking=True,
        description="Code must compile and pass basic checks",
    ),
    QualityGate(
        gate_id="QG-quality",
        name="Quality Gate",
        required_score=85.0,
        blocking=True,
        description="Quality and security checks must pass",
    ),
    QualityGate(
        gate_id="QG-release",
        name="Release Ready",
        required_score=90.0,
        blocking=True,
        description="All checks pass, ready for release",
    ),
]


def get_default_constitution() -> Constitution:
    return Constitution(
        version="1.0.0",
        rules=DEFAULT_RULES,
        quality_gates=DEFAULT_QUALITY_GATES,
    )


def check_rule(constitution: Constitution, rule_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Check if a specific rule is satisfied given the context."""
    for rule in constitution.rules:
        if rule.rule_id == rule_id and rule.enabled:
            return {"rule_id": rule_id, "satisfied": True, "message": rule.name}
    return {"rule_id": rule_id, "satisfied": False, "message": "Rule not found or disabled"}


def check_quality_gate(constitution: Constitution, gate_id: str, score: float) -> Dict[str, Any]:
    """Check if a quality gate is satisfied."""
    for gate in constitution.quality_gates:
        if gate.gate_id == gate_id:
            passed = score >= gate.required_score
            return {
                "gate_id": gate_id,
                "name": gate.name,
                "score": score,
                "required": gate.required_score,
                "passed": passed,
                "blocking": gate.blocking,
                "message": f"{'PASS' if passed else 'FAIL'}: {gate.name} ({score:.0f}/{gate.required_score:.0f})",
            }
    return {"gate_id": gate_id, "passed": False, "message": "Gate not found"}


def constitution_to_dict(constitution: Constitution) -> Dict[str, Any]:
    return {
        "version": constitution.version,
        "max_budget_per_stage": constitution.max_budget_per_stage,
        "max_total_budget": constitution.max_total_budget,
        "max_iterations": constitution.max_iterations,
        "escalation_threshold": constitution.escalation_threshold,
        "rules": [
            {"id": r.rule_id, "name": r.name, "category": r.category, "severity": r.severity, "enabled": r.enabled}
            for r in constitution.rules
        ],
        "quality_gates": [
            {"id": g.gate_id, "name": g.name, "required_score": g.required_score, "blocking": g.blocking}
            for g in constitution.quality_gates
        ],
    }
