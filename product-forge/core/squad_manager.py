"""Squad Manager - Dynamic Agent Squad Formation.
Analyzes task requirements, selects agents by capabilities, forms temporary squads.
"""
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class AgentCapability:
    name: str
    capabilities: List[str]
    tools: List[str] = field(default_factory=list)
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    decision_rights: Dict[str, bool] = field(default_factory=dict)
    constraints: List[str] = field(default_factory=list)
    cost_tier: str = "standard"
    max_concurrent: int = 1


@dataclass
class Squad:
    squad_id: str
    task: str
    agents: List[str]
    formed_at: str
    dissolved_at: str = ""
    stage: str = ""
    total_tokens: int = 0
    total_cost: float = 0.0


# Default agent capability registry
DEFAULT_AGENTS: Dict[str, AgentCapability] = {
    "ideation": AgentCapability(
        name="ideation",
        capabilities=["brainstorming", "idea_validation", "market_research"],
        tools=["web_search", "knowledge_base"],
        inputs=["requirement"],
        outputs=["product_spec", "market_analysis"],
        decision_rights={"can_approve_spec": False},
    ),
    "design": AgentCapability(
        name="design",
        capabilities=["ui_design", "ux_research", "wireframing", "prototyping"],
        tools=["figma", "design_tokens"],
        inputs=["product_spec", "design_tokens"],
        outputs=["design_spec", "wireframes"],
        decision_rights={"can_approve_design": True},
    ),
    "architect": AgentCapability(
        name="architect",
        capabilities=["system_design", "api_design", "database_design", "architecture"],
        tools=["diagrams", "codebase"],
        inputs=["product_spec", "design_spec"],
        outputs=["architecture", "api_contract"],
        decision_rights={"can_approve_architecture": True, "can_block_release": False},
    ),
    "implement": AgentCapability(
        name="implement",
        capabilities=["coding", "database", "api", "ui_implementation", "testing"],
        tools=["repository", "terminal", "git"],
        inputs=["design_spec", "component_plan", "api_contract"],
        outputs=["source_code", "unit_tests"],
        decision_rights={"can_modify_code": True},
    ),
    "code-review": AgentCapability(
        name="code-review",
        capabilities=["code_review", "quality_check", "best_practices"],
        tools=["repository", "linter"],
        inputs=["source_code", "design_spec"],
        outputs=["review_report", "approval"],
        decision_rights={"can_block_release": True},
    ),
    "validate": AgentCapability(
        name="validate",
        capabilities=["testing", "validation", "qa"],
        tools=["test_runner", "browser"],
        inputs=["source_code", "test_specs"],
        outputs=["test_report", "validation_result"],
        decision_rights={"can_block_release": True},
    ),
    "fix": AgentCapability(
        name="fix",
        capabilities=["bug_fix", "refactoring", "error_resolution"],
        tools=["repository", "terminal", "debugger"],
        inputs=["test_report", "source_code"],
        outputs=["fixed_code"],
        decision_rights={"can_modify_code": True},
    ),
    "security": AgentCapability(
        name="security",
        capabilities=["security_scan", "vulnerability_analysis", "threat_modeling"],
        tools=["security_scanner", "repository"],
        inputs=["source_code", "architecture"],
        outputs=["security_report", "remediation_plan"],
        decision_rights={"can_block_release": True},
    ),
    "devops": AgentCapability(
        name="devops",
        capabilities=["build", "deploy", "ci_cd", "infrastructure"],
        tools=["terminal", "docker", "cloud"],
        inputs=["source_code", "deploy_config"],
        outputs=["build_output", "deploy_result"],
        decision_rights={"can_deploy": True},
    ),
    "document": AgentCapability(
        name="document",
        capabilities=["documentation", "api_docs", "user_guide"],
        tools=["markdown", "repository"],
        inputs=["product_spec", "architecture", "api_contract"],
        outputs=["documentation"],
        decision_rights={},
    ),
    "package": AgentCapability(
        name="package",
        capabilities=["packaging", "release", "distribution"],
        tools=["build_system", "package_manager"],
        inputs=["source_code", "build_config"],
        outputs=["release_package"],
        decision_rights={"can_block_release": True},
    ),
    "orchestrator": AgentCapability(
        name="orchestrator",
        capabilities=["coordination", "scheduling", "resource_management"],
        tools=["dag_executor", "state_machine"],
        inputs=["project_state", "budget_state"],
        outputs=["coordination_plan"],
        decision_rights={"can_pause": True, "can_stop": True, "can_override": True},
    ),
    "design_critic": AgentCapability(
        name="design_critic",
        capabilities=["design_review", "quality_scoring", "usability_evaluation"],
        tools=["design_analyzer"],
        inputs=["design_spec", "design_tokens", "screenshot"],
        outputs=["design_scorecard", "review_feedback"],
        decision_rights={"can_block_release": True},
    ),
    "visual_qa": AgentCapability(
        name="visual_qa",
        capabilities=["screenshot_capture", "visual_comparison", "rendering_check"],
        tools=["playwright", "vision_model"],
        inputs=["screenshot", "design_spec", "design_tokens"],
        outputs=["visual_review", "regression_report"],
        decision_rights={"can_block_release": True},
    ),
}


class SquadManager:
    """Dynamically forms agent squads based on task capabilities."""
    
    def __init__(self, products_dir: str = "products", project: str = "default"):
        self.products_dir = Path(products_dir)
        self.project = project
        self.agents = dict(DEFAULT_AGENTS)
        self._active_squads: List[Squad] = []
    
    def analyze_task(self, task: str, stage: str = "") -> List[str]:
        """Determine which capabilities are needed for a task."""
        task_lower = task.lower()
        needed: Set[str] = set()
        
        keyword_map = {
            "design": ["design", "ui", "ux", "wireframe", "prototype", "mockup"],
            "architect": ["architecture", "system design", "api design", "database"],
            "implement": ["implement", "code", "build", "develop", "write"],
            "code-review": ["review", "code review", "quality"],
            "validate": ["test", "validate", "verify", "qa"],
            "fix": ["fix", "bug", "error", "broken"],
            "security": ["security", "vulnerability", "threat"],
            "devops": ["deploy", "build", "ci", "cd", "infrastructure"],
            "document": ["document", "docs", "documentation"],
            "ideation": ["ideation", "brainstorm", "research", "idea"],
            "design_critic": ["critique", "scorecard", "design review"],
            "visual_qa": ["visual", "screenshot", "render", "regression"],
        }
        
        for agent_name, keywords in keyword_map.items():
            for kw in keywords:
                if kw in task_lower:
                    needed.add(agent_name)
                    break
        
        if not needed:
            needed = {"orchestrator"}
        
        return sorted(needed)
    
    def form_squad(self, task: str, stage: str = "", max_agents: int = 5) -> Squad:
        """Form a squad for a task based on capability analysis."""
        needed_caps = self.analyze_task(task, stage)
        selected = needed_caps[:max_agents]
        
        squad = Squad(
            squad_id=f"squad-{stage}-{int(datetime.now().timestamp())}",
            task=task,
            agents=selected,
            formed_at=datetime.now().isoformat(),
            stage=stage,
        )
        self._active_squads.append(squad)
        return squad
    
    def dissolve_squad(self, squad_id: str):
        for squad in self._active_squads:
            if squad.squad_id == squad_id:
                squad.dissolved_at = datetime.now().isoformat()
                break
    
    def get_agent_capabilities(self, agent_name: str) -> Optional[Dict]:
        agent = self.agents.get(agent_name)
        return asdict(agent) if agent else None
    
    def get_status(self) -> Dict:
        return {
            "total_agents": len(self.agents),
            "active_squads": len([s for s in self._active_squads if not s.dissolved_at]),
            "total_squads_formed": len(self._active_squads),
            "available_agents": list(self.agents.keys()),
        }
