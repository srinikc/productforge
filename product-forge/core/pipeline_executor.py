"""
Pipeline Execution Engine
Real execution engine that wires together all components:
- DAGExecutor for stage management
- KnowledgeRouter for knowledge loading
- ComplianceCheck for verification
- AgentMemory for state persistence
- ReasoningSkills for decision-making
- Context Manager for minimum context per agent
- Budget Protection for cost control
- Design Critic for quality review
- Visual QA for UI validation
- Product Design Spec for structured specs
- Design Tokens for consistent styling
- Model Registry for model routing
- Artifact Store for artifact management
- Human Controls for approval gates
- Forced Convergence for stuck detection
- Product Forge Constitution for rule enforcement
- Circuit Breakers for failure handling
- Squad Manager for dynamic agent selection
- Cross-Project Learning for insights
- Discovery Engine for multi-perspective ideation
- Dashboard Archetypes for layout templates
- Budget Conservation for graceful degradation
- Quality Metrics for performance tracking
- Issue Tracker for structured issues

This is the bridge between the Python infrastructure and the pipeline workflow.
"""

import json
import os
import sys
import hashlib
import re
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable, Tuple

from core import stage_paths as _sp
from core import status as _status


def new_run_id() -> str:
    """The SINGLE place a run id is minted. Canonical format: ``run-<epoch>``."""
    import time as _t
    return f"run-{int(_t.time())}"


def norm_run_id(run_id: str) -> str:
    """Back-compat: any historical form (``pipeline-123``/``run-123``) -> ``run-123``."""
    r = str(run_id or "")
    m = re.match(r"^(?:pipeline|run)-(\d+)$", r)
    return f"run-{m.group(1)}" if m else r
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.knowledge_router import KnowledgeRouter, RoutingDecision
from core.agent_memory import AgentMemory, MemoryType, MemoryEntry, MemoryQuery
from core.knowledge_compiler import KnowledgeCompiler
from core.skill_contracts import SkillContractRegistry
from core.agent_runtime import AgentRuntime, AgentState, AgentContext
from core.dag_executor import DAGExecutor, StageStatus, StageType
from core.reasoning_skills import ReasoningSkills
from core.budget_protection import BudgetManager, BudgetType, safe_knowledge_route
from core.context_manager import build_context_package, get_contract, check_budget as ctx_check_budget
from core.stop_conditions import StopConditionManager
from core.budget_tracker import BudgetTracker

# Newly wired modules
from core.product_design_spec import create_spec_from_artifacts, save_spec
from core.design_tokens import get_default_tokens, tokens_to_css_custom_properties, save_tokens
from core.model_registry import ModelCapabilityRegistry
from core.artifact_store import scan_project_artifacts, create_or_update_artifact, get_artifacts_for_context
from core.forced_convergence import ConvergenceState, check_convergence, force_complete_stage, convergence_to_dict
from core.forge_constitution import check_rule, check_quality_gate, constitution_to_dict
from core.circuit_breaker import CircuitBreakerRegistry
from core.squad_manager import SquadManager
from core.cross_project_learning import build_learning_index, get_relevant_insights
from core.discovery_engine import run_discovery, discovery_to_dict  # noqa: F401 (available; not invoked in the core loop)
from core.dashboard_archetypes import select_archetype, get_archetype, archetype_to_dict
from core.budget_conservation import create_conservation_state, apply_conservation_actions, should_skip_agent
from core.quality_metrics import QualityMetrics, calculate_quality_score, save_quality_metrics, generate_quality_report

# Knowledge compliance and action handling
from core.knowledge_compliance_checker import KnowledgeComplianceChecker, GuidelineContentLoader
from core.compliance_action_handler import ComplianceActionHandler
from core.issue_tracker import create_issue_list, add_issue, save_issue_list, generate_issue_report, prioritize_issues
from core.project_journal import ProjectJournal
from core.run_breaker import RunBreaker
from core.iteration_planner import (plan_iterations, iteration_feature_map,
                                    ITERATION_STAGES as PHASE_STAGES)
from core.tech_stack import (detect_tech_from_text, stack_to_layers, is_web_stack,
                             parse_tech_stack_block, build_decision, load_tech_stack,
                             save_tech_stack)


# Last-resort defaults. These are ONLY used when no model-tier config can be
# found anywhere. They are overridable via environment variables so that model
# selection is never truly hardcoded in the pipeline logic.
FALLBACK_MODEL = os.getenv("PIPELINE_FALLBACK_MODEL", "mimo-v2.5")
FALLBACK_PROVIDER = os.getenv("PIPELINE_FALLBACK_PROVIDER", "opencode-go")
FALLBACK_ENDPOINT = os.getenv(
    "PIPELINE_FALLBACK_ENDPOINT",
    "https://opencode.ai/zen/go/v1/chat/completions",
)


# Extracted to core/orchestrator/* (modularity - 1A.11)
from core.orchestrator.storage import AgentAuditLog, LLMCache, ArtifactSummarizer, InputCache
from core.orchestrator.types import PipelinePhase, AgentExecution, PipelineExecution
from core.orchestrator.llm_client import LLMClient
from core.orchestrator.model_router import ModelRouter
from core.orchestrator.compliance import ComplianceOrchestrator
from core.orchestrator.phasing import PhasingManager
from core.orchestrator.checkpoint import CheckpointWriter
from core.orchestrator.delegation_coord import DelegationCoordinator
from core.orchestrator.agent_runner import AgentRunnerMixin
from core.orchestrator.stage_runner import StageRunnerMixin
from core.orchestrator.agent_execution import AgentExecutionMixin
from core.orchestrator.feature_tracker import FeatureTracker


class PipelineExecutor(AgentExecutionMixin, AgentRunnerMixin, StageRunnerMixin):
    """
    Real pipeline execution engine that wires all components together.
    
    Usage:
        executor = PipelineExecutor(products_dir="products", project="<project>")
        success = executor.execute_pipeline("pipeline-definition.json")
    """
    
    def __init__(self, products_dir: str = "products", project: str = "default"):
        self.products_dir = products_dir
        self.project = project
        self.project_dir = os.path.join(products_dir, project)
        
        # Initialize all components
        self.knowledge_router = KnowledgeRouter(products_dir)
        self.memory = AgentMemory(products_dir, project)
        self.compiler = KnowledgeCompiler()
        self.skills = SkillContractRegistry()
        self.runtime = AgentRuntime(products_dir, project)
        self.reasoning = ReasoningSkills()
        
        # Budget protection
        self.budget_manager = BudgetManager(products_dir, project)
        self.budget_tracker = BudgetTracker(products_dir)
        self.stop_conditions = StopConditionManager(products_dir)
        self._initialize_budgets()
        
        # Newly wired components
        self.model_registry = ModelCapabilityRegistry()
        self.circuit_breakers = CircuitBreakerRegistry(project)
        self.squad_manager = SquadManager()
        self.conservation_state = create_conservation_state()
        
        # Audit logging, caching, and summarization
        self.audit_log = AgentAuditLog(os.path.join(products_dir, project))
        self.llm_cache = LLMCache(os.path.join(products_dir, project))
        # Layer 2: project-scoped input cache (assembled prompts, never outputs).
        self.input_cache = InputCache(os.path.join(products_dir, project))
        self.summarizer = ArtifactSummarizer()
        self.llm = LLMClient(self.model_registry, self._get_agent_model_config,
                             self.llm_cache, project=project)
        self.model_router = ModelRouter(self.model_registry, products_dir,
                                        self.project_dir, getattr(self, "pipeline_def", None))
        
        # Knowledge compliance and action handling
        self.knowledge_compliance = KnowledgeComplianceChecker(products_dir, "docs/guidelines")
        self.guideline_loader = GuidelineContentLoader("docs/guidelines")
        self.compliance_handler = ComplianceActionHandler(products_dir, project)
        self.compliance_orchestrator = ComplianceOrchestrator(
            products_dir=products_dir, project=project, project_dir=self.project_dir,
            knowledge_compliance=self.knowledge_compliance,
            compliance_handler=self.compliance_handler,
            stack_compliance=self._stack_compliance,
            llm_verify=self._run_llm_verification,
            use_test_suites=getattr(self, "enable_test_suites", False),
            multi_review=self._run_multi_model_review,
            test_cycle=self._run_test_cycle,
            coverage=self._nfr_coverage,
            enforce_coverage=self._enforce_coverage_enabled(),
            spec_review=self._run_spec_review,
            qa_gate=self._run_qa_gate,
        )
        
        # Pipeline state
        self.pipeline_def: Optional[Dict] = None
        self.dag_executor: Optional[DAGExecutor] = None
        self.execution: Optional[PipelineExecution] = None
        self.iteration_count: int = 0
        self.max_iterations: int = 100
        self._stop_requested: bool = False
        self._pause_requested: bool = False
        # 1.3: optional HIL step mode — pause after every agent
        self.step_pause: bool = (os.environ.get("PIPELINE_STEP", "0") == "1")
        self.only_stages: Optional[set] = None  # selective "run only these stages"
        self.only_agents: Optional[set] = None  # selective "run only these agents"
        self._idle_loops: int = 0
        
        # Orchestrator: Time Management
        self.pipeline_start_time: float = 0
        self.stage_durations: List[float] = []  # History of stage durations
        self.stage_timings: Dict[str, Dict] = {}  # stage_id -> {started_at, completed_at, duration_s}
        self.agent_timings: List[Dict] = []  # per-agent {stage, agent, started_at, completed_at, duration_s}
        self.max_total_time: int = 1800  # 30 min default
        self.per_stage_timeout: int = 300  # 5 min per stage
        self.min_remaining_time: int = 120  # Minimum 2 min to continue
        
        # Orchestrator: Human-in-the-Loop
        self.auto_approve: bool = False  # Default: HITL required
        self.approval_mode: str = "interactive"  # interactive, auto, semi
        self.budget_spec: Dict = {}  # project budget (soft/hard/tolerance)
        self.project_idea: str = ""  # intended product brief for Stage 0
        self.tech_stack_hints: List[str] = []  # project-declared tech stack
        self.requested_tech_stack: List[str] = []  # user-requested stack (constraint)
        self.tech_stack: Dict = {}  # agreed stack decision (docs/tech-stack.json)
        self.max_compliance_retries: int = 2  # bounded re-run on compliance retry
        self.pending_approvals: List[Dict] = []
        
        # Orchestrator: Parallel Execution
        self.max_parallel_stages: int = 3
        self.parallel_enabled: bool = True
        self._state_lock = threading.Lock()  # guards shared mutable state across threads
        
        # Orchestrator: Checkpoint/Resume
        self.state_file: str = os.path.join(self.project_dir, "pipeline-state.json")
        self.control_file: str = os.path.join(self.project_dir, "control.json")
        self.run_scope_file: str = os.path.join(self.project_dir, "run-scope.json")
        self.live_file: str = os.path.join(self.project_dir, "agents-live.json")
        self.checkpoint_data: Dict = {}
        
        # Orchestrator: Self-Monitoring
        self.health_log: List[Dict] = []
        self.anomaly_threshold: float = 3.0  # 3x average = anomaly
        
        # Orchestrator: Decision Log
        self.decision_log: List[Dict] = []
        
        # Issue tracking
        self.security_issues = create_issue_list(project, "security", "security")
        self.nfr_issues = create_issue_list(project, "nfr", "validate")
        self.test_issues = create_issue_list(project, "tests", "validate")
        
        # Quality metrics
        self.quality_metrics = QualityMetrics(
            run_id=f"run-{int(datetime.now().timestamp())}",
            project=project,
            started_at=datetime.now().isoformat(),
        )
        
        # Ensure directories exist
        os.makedirs(self.project_dir, exist_ok=True)
        os.makedirs(os.path.join(self.project_dir, "compliance"), exist_ok=True)
        os.makedirs(os.path.join(self.project_dir, "memory"), exist_ok=True)
        _sp.artifacts_root(self.project_dir, create=True)
        os.makedirs(os.path.join(self.project_dir, "issues"), exist_ok=True)
        os.makedirs(os.path.join(self.project_dir, "specs"), exist_ok=True)
        os.makedirs(os.path.join(self.project_dir, "approvals"), exist_ok=True)
        os.makedirs(os.path.join(self.project_dir, "docs"), exist_ok=True)
        
        # Dynamic implementation phasing (must exist before config load, which
        # sets phases_override from project-config.json).
        self.phasing = PhasingManager(self.project_dir)
        # Knowledge token budget per agent (configurable; env-configurable).
        try:
            self.knowledge_budget_tokens = int(os.getenv("KNOWLEDGE_BUDGET_TOKENS", "12000"))
        except (TypeError, ValueError):
            self.knowledge_budget_tokens = 12000
        # LLM-as-verifier (second model reviews agent work) - opt-in.
        self.enable_llm_verification = str(os.getenv("ENABLE_LLM_VERIFICATION", "0")).lower() in ("1", "true", "yes")
        # Per-phase test suites (test-framework bridge) - opt-in.
        self.enable_test_suites = str(os.getenv("ENABLE_TEST_SUITES", "0")).lower() in ("1", "true", "yes")
        # Multi-model review for design/architecture - opt-in.
        self.enable_multi_model_review = str(os.getenv("ENABLE_MULTI_MODEL_REVIEW", "0")).lower() in ("1", "true", "yes")

        # Load project config (auto_approve, etc.)
        self._load_project_config()
        # Materialize the canonical project-config.json expected by compliance
        self._ensure_project_config()
        # Reconcile token budgets with the project budget spec
        self._apply_budget_spec()
        # Live journal / project state (best-effort)
        try:
            self.journal = ProjectJournal(products_dir, project)
        except Exception:
            self.journal = None
        self.checkpoints = CheckpointWriter(self.journal, self.phasing,
                                            self.summarizer, PHASE_STAGES)
        # Run breaker + alerts (budget-spec driven)
        try:
            self.run_breaker = RunBreaker(project, products_dir, self.budget_spec)
        except Exception:
            self.run_breaker = None
        self._force_cheap = False
        # Delegation (orchestrator-routed A2A) - opt-in, off by default
        self.delegation_enabled = False
        self.delegation_router = None
        self.delegations: List[Dict] = []
        self.delegation_coord = DelegationCoordinator(products_dir, project, self.delegations)
        # Framework-agnostic AgentSpec + ToolRegistry
        self.enable_tools = True  # default ON; per-agent gated by spec.tools
        try:
            from core.agent_spec import load_specs
            from core.tool_registry import ToolRegistry
            _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.agent_specs = load_specs(os.path.join(_root, "agents"))
            self.tool_registry = ToolRegistry()
        except Exception as _e:
            print(f"[Executor] agent specs/tools unavailable: {_e}")
            self.agent_specs = {}
            self.tool_registry = None
        # Tool result cache (avoids redundant read_file/list_dir/http_get calls)
        try:
            from core.tool_cache import ToolResultCache
            self.tool_cache = ToolResultCache(products_dir)
        except Exception:
            self.tool_cache = None
        # Semantic cache (opt-in, 4.9)
        if str(os.getenv("ENABLE_SEMANTIC_CACHE", "0")).lower() in ("1", "true", "yes"):
            try:
                from core.phase3_advanced import SemanticCache
                self.llm.semantic_cache = SemanticCache(products_dir)
            except Exception:
                pass
        # Loop controller (long-running ops) + optional knowledge graph (4.9)
        try:
            from core.loop_modes import LoopController
            self.loop_controller = LoopController(products_dir)
        except Exception:
            self.loop_controller = None
        self._post_deploy = None
        self._test_cycle = None
        self._fix_review_active = False
        self._schema_validation = None
        self.knowledge_graph = None
        if str(os.getenv("ENABLE_KNOWLEDGE_GRAPH", "0")).lower() in ("1", "true", "yes"):
            try:
                from core.phase3_advanced import KnowledgeGraph
                self.knowledge_graph = KnowledgeGraph(products_dir)
            except Exception:
                self.knowledge_graph = None
        # Cost-per-successful-task KPI tracker
        try:
            from core.cost_kpi import CostKPITracker
            self.cost_kpi = CostKPITracker(products_dir)
        except Exception:
            self.cost_kpi = None
        # Reliability: DLQ, notifications, LLM error log (best-effort)
        try:
            from core.dead_letter_queue import DeadLetterQueue
            self.dlq = DeadLetterQueue(project)
        except Exception:
            self.dlq = None
        try:
            from core.notification_system import NotificationSystem
            self.notifications = NotificationSystem(project)
        except Exception:
            self.notifications = None
        try:
            from core.llm_error_handler import LLMErrorHandler
            self.llm_error_handler = LLMErrorHandler(project)
        except Exception:
            self.llm_error_handler = None
        # Feature-level status tracking (ProductPlan)
        self.feature_tracker = FeatureTracker(project, products_dir)

    def _apply_budget_spec(self):
        """Align the pipeline token budget with the project budget spec."""
        try:
            cap = self.budget_spec.get("hard_tokens") or self.budget_spec.get("soft_tokens")
            if cap:
                self.budget_manager.create_budget(
                    "pipeline_total", BudgetType.PIPELINE_TOTAL,
                    max_tokens=int(cap), scope=self.project)
        except Exception:
            pass

    def _write_project_agents_md(self):
        """Emit products/<project>/AGENTS.md — project-wide rules for all agents (0.5)."""
        try:
            chosen = (getattr(self, "tech_stack", {}) or {}).get("chosen") or {}
            idea = (getattr(self, "project_idea", "") or "").strip()
            path = os.path.join(self.project_dir, "AGENTS.md")
            lines = [
                f"# AGENTS.md — {self.project}",
                "",
                "> Project-wide rules for ALL agents. Generated at run start.",
                "",
                "## Purpose",
                idea or "(see docs/product-plan.md)",
                "",
                "## Tech stack (MUST follow docs/tech-stack.json)",
                f"- kind: {chosen.get('kind', '')}",
                f"- languages: {chosen.get('languages', [])}",
                f"- frameworks: {chosen.get('frameworks', [])}",
                f"- database: {chosen.get('database', '')}",
                "",
                "## Conventions",
                "- No mocks, stubs, TODOs, or placeholders.",
                "- Write real files (write_file); run tests before declaring done.",
                "- Follow docs/CONSTITUTION.md and docs/guidelines.",
                "",
                "## Verification / Definition of Done",
                "- `validate` must actually run the test suite and report real results.",
                "- Compliance must pass: no-mock gate, knowledge, architecture completeness, no secrets.",
            ]
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except Exception as e:
            print(f"  [AGENTS.md] skipped: {e}")

    def _ensure_project_config(self):
        """Write project-config.json (canonical layout) from project.json.

        The compliance checklists expect product_type/product_domain/
        tech_stack_hints in project-config.json, not project.json.
        """
        src = os.path.join(self.project_dir, "project.json")
        dst = os.path.join(self.project_dir, "project-config.json")
        config = {}
        if os.path.exists(src):
            try:
                with open(src, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except Exception:
                config = {}
        existing = {}
        if os.path.exists(dst):
            try:
                with open(dst, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
            except Exception:
                existing = {}
        existing.setdefault("name", config.get("name", self.project))
        existing.setdefault("product_type", config.get("business_model", config.get("product_type", "web_app")))
        existing.setdefault("product_domain", config.get("product_domain", "technology"))
        existing.setdefault("tech_stack_hints", config.get("tech_stack_hints", []))
        try:
            with open(dst, 'w', encoding='utf-8') as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Orchestrator] Could not write project-config.json: {e}")

    # Canonical document each agent's output maps to (compliance layout).
    CANONICAL_DOC_MAP = {
        "ideation": ["docs/product-plan.md"],
        "design": ["docs/requirements.md", "docs/design.md"],
        "architect": ["docs/architecture.md"],
        "researcher": ["docs/research-notes.md"],
    }

    def _materialize_canonical_artifacts(self, agent_id: str, stage_id: str, artifacts: List[str]):
        """Copy an agent's output to the canonical doc path(s) compliance expects.

        Agents return markdown; the rule-based compliance checklists look for
        docs/*.md files. Writing the output there lets file/content checks run
        against the real generated content instead of always failing on a path
        mismatch.
        """
        doc_paths = self.CANONICAL_DOC_MAP.get(agent_id)
        if not doc_paths or not artifacts:
            return
        # Use the latest artifact produced by this agent.
        source = artifacts[-1]
        try:
            with open(source, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            return
        for rel in doc_paths:
            target = os.path.join(self.project_dir, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            try:
                with open(target, 'w', encoding='utf-8') as f:
                    f.write(content)
            except Exception as e:
                print(f"[Compliance] Could not write {rel}: {e}")

    def _append_agent_audit_md(self, agent_id: str, stage_id: str, status: str):
        """Append a line to agent-audit.md (canonical audit layout)."""
        audit_md = os.path.join(self.project_dir, "agent-audit.md")
        line = (f"- {datetime.now().isoformat()} | agent={agent_id} | "
                f"stage={stage_id} | status={status}\n")
        try:
            new_file = not os.path.exists(audit_md)
            with open(audit_md, 'a', encoding='utf-8') as f:
                if new_file:
                    f.write("# Agent Audit Log\n\n")
                f.write(line)
        except Exception:
            pass
    
    def _load_project_config(self):
        """Load project config including auto_approve setting."""
        config_file = os.path.join(self.project_dir, "project.json")
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.auto_approve = config.get("auto_approve", False)
                self.approval_mode = config.get("approval_mode", "interactive")
                self.max_total_time = config.get("max_total_time", 1800)
                # Env override (0 = unlimited) for long interactive sessions.
                try:
                    _mt = os.getenv("PIPELINE_MAX_TOTAL_TIME", "")
                    if _mt != "":
                        self.max_total_time = int(float(_mt))
                except (TypeError, ValueError):
                    pass
                self.parallel_enabled = config.get("parallel_stages", True)
                self.budget_spec = config.get("budget", {}) if isinstance(config.get("budget"), dict) else {}
                self.delegation_enabled = bool(config.get("enable_delegation", False))
                # Tools are ON by default (code agents write real files); set
                # "enable_tools": false for cheap markdown-only runs.
                self.enable_tools = bool(config.get("enable_tools", True))
                # Model tier profile (e.g. "actual" or "free-trial"). The env var
                # PIPELINE_MODEL_TIER takes precedence and is read by the router.
                if config.get("model_tier"):
                    self.model_router.tier_profile = config.get("model_tier")
                # Knowledge token budget per agent (overrides env default).
                if config.get("knowledge_budget_tokens"):
                    try:
                        self.knowledge_budget_tokens = int(config.get("knowledge_budget_tokens"))
                    except (TypeError, ValueError):
                        pass
                # Opt-in LLM-as-verifier.
                if "enable_llm_verification" in config:
                    self.enable_llm_verification = bool(config.get("enable_llm_verification"))
                # Opt-in per-phase test suites; keep orchestrator in sync.
                if "enable_test_suites" in config:
                    self.enable_test_suites = bool(config.get("enable_test_suites"))
                try:
                    if getattr(self, "compliance_orchestrator", None) is not None:
                        self.compliance_orchestrator.use_test_suites = self.enable_test_suites
                except Exception:
                    pass
                # Intended product idea/brief (so Stage 0 works on OUR product).
                self.project_idea = config.get("idea") or config.get("description") or ""
                self.tech_stack_hints = config.get("tech_stack_hints", []) or []
                # Requested stack = explicit config + anything detected in the idea.
                explicit = list(config.get("tech_stack") or []) + list(self.tech_stack_hints)
                detected = detect_tech_from_text(self.project_idea)
                self.requested_tech_stack = sorted(set([str(x).lower() for x in explicit] + detected))
                # Previously agreed stack (resume).
                self.tech_stack = load_tech_stack(self.project_dir)
                idea_file = os.path.join(self.project_dir, "idea.md")
                if os.path.exists(idea_file):
                    try:
                        with open(idea_file, "r", encoding="utf-8") as f:
                            self.project_idea = f.read().strip() or self.project_idea
                    except Exception:
                        pass
                # Dynamic phasing override: "auto" (default) or an integer.
                ip = config.get("implementation_phases", "auto")
                try:
                    self.phasing.phases_override = None if (isinstance(ip, str) and ip.lower() == "auto") else int(ip)
                except (TypeError, ValueError):
                    self.phasing.phases_override = None
                # Planning mode: "epic" (Scrum-style grouping) or "feature".
                if config.get("planning_mode"):
                    self.phasing.planning_mode = str(config.get("planning_mode"))
                msg = f"[Orchestrator] Loaded config: auto_approve={self.auto_approve}, mode={self.approval_mode}"
                if self.budget_spec:
                    msg += (f", budget(soft_cost={self.budget_spec.get('soft_cost')}, "
                            f"hard_cost={self.budget_spec.get('hard_cost')}, "
                            f"tolerance={self.budget_spec.get('tolerance_percent', 10)}%)")
                print(msg)
            except Exception as e:
                print(f"[Orchestrator] Warning: Could not load project config: {e}")
    
    def _log_decision(self, decision_type: str, details: str, reason: str):
        """Log orchestrator decision for audit trail."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": decision_type,
            "details": details,
            "reason": reason,
            "elapsed_time": time.time() - self.pipeline_start_time if self.pipeline_start_time else 0
        }
        self.decision_log.append(entry)
        print(f"[Orchestrator Decision] {decision_type}: {details} ({reason})")
    
    def _check_time_budget(self) -> Tuple[bool, str]:
        """Check if pipeline should continue based on time budget.
        
        Returns:
            (should_continue, reason)
        """
        if not self.pipeline_start_time:
            return True, "pipeline not started"
        
        elapsed = time.time() - self.pipeline_start_time
        # Human-wait (approvals/prompts) is not pipeline WORK time.
        human_wait = float(getattr(self, "_total_human_wait_seconds", 0.0)) + \
            float(getattr(self, "_stage_human_wait_seconds", 0.0))
        work_elapsed = max(0.0, elapsed - human_wait)

        # 0/unset budget = unlimited (interactive sessions).
        if not self.max_total_time or self.max_total_time <= 0:
            return True, f"no time budget (work {work_elapsed:.0f}s)"

        # Remaining = stages not yet terminal.
        try:
            done = {"completed", "skipped", "failed"}
            remaining_stages = sum(1 for st in self.dag_executor.states.values()
                                   if st.status.value not in done)
        except Exception:
            remaining_stages = len(self.dag_executor.get_ready_stages()) if self.dag_executor else 0

        # Calculate average stage duration (work-only; recorded at stage end)
        avg_duration = (sum(self.stage_durations) / len(self.stage_durations)) if self.stage_durations else 45

        # Estimate remaining time
        estimated_remaining = avg_duration * remaining_stages

        # Check if we should continue (on WORK time)
        if work_elapsed + estimated_remaining > self.max_total_time:
            return False, (f"estimated work time ({work_elapsed + estimated_remaining:.0f}s) "
                           f"exceeds max ({self.max_total_time}s)")

        if work_elapsed + self.min_remaining_time > self.max_total_time:
            return False, (f"insufficient remaining time "
                           f"({self.max_total_time - work_elapsed:.0f}s < {self.min_remaining_time}s)")

        return True, f"on track (work {work_elapsed:.0f}s, ~{estimated_remaining:.0f}s remaining)"
    
    def _record_stage_duration(self, duration: float):
        """Record stage duration for time estimation."""
        self.stage_durations.append(duration)
        self._log_decision("stage_duration", f"{duration:.1f}s", "recorded for time estimation")
    
    def _save_checkpoint(self):
        """Save pipeline state for checkpoint/resume (pipeline-state.v1)."""
        now = datetime.now().isoformat()
        # stages map (status per stage) from the DAG + executions
        stages_state = {}
        try:
            if self.dag_executor:
                stages_state = self.dag_executor.export_state().get("stages", {})
        except Exception:
            stages_state = {}
        checkpoint = {
            "project": self.project,
            "spec_version": "1.0",
            "created_at": self.execution.started_at if self.execution else now,
            "updated_at": now,
            "current_stage": self.execution.current_stage if self.execution else "",
            "pipeline_complete": bool(self.execution and self.execution.phase == PipelinePhase.COMPLETION),
            "completed_at": self.execution.completed_at if self.execution else "",
            "stages": stages_state,
            # extended (allowed by schema)
            "pipeline_id": self.execution.pipeline_id if self.execution else "",
            "started_at": self.execution.started_at if self.execution else now,
            "current_iteration": self.iteration_count,
            "completed_stages": list(self.execution.stage_executions.keys()) if self.execution else [],
            "total_tokens": self.execution.total_tokens if self.execution else 0,
            "total_cost": self.execution.total_cost if self.execution else 0,
            "stage_durations": self.stage_durations,
            "decision_log": self.decision_log[-50:],
            "saved_at": now,
        }
        try:
            # Atomic write: only the orchestrator owns pipeline-state.json.
            tmp = self.state_file + ".tmp"
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(checkpoint, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.state_file)
            # BI-0005: keep the legacy `pipeline.json` view as a DERIVED projection
            # (config from project.json + this state) so existing readers stay valid.
            try:
                from core.pipeline_store import sync as _psync
                _psync(self.project, self.products_dir)
            except Exception:
                pass
        except Exception as e:
            print(f"[Orchestrator] Warning: Could not save checkpoint: {e}")
    
    def _load_checkpoint(self) -> Optional[Dict]:
        """Load pipeline state from checkpoint."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def _restore_from_checkpoint(self, checkpoint: Dict):
        """Restore DAG stage states (+ rehydrate artifacts) so resume skips done work."""
        stages = (checkpoint or {}).get("stages") or {}
        # A stage left `running` by a killed process is not runnable and blocks its
        # dependents forever — reset it so resume re-runs it.
        for _sid, _info in list(stages.items()):
            if isinstance(_info, dict) and _info.get("status") == "running":
                _info["status"] = "pending"
                _info["started_at"] = ""
        try:
            if self.dag_executor and stages:
                self.dag_executor.restore_states(stages)
        except Exception as e:
            print(f"[Orchestrator] Warning: could not restore stage states: {e}")
        if not self.execution:
            return
        import glob as _glob
        for sid, info in stages.items():
            if (info or {}).get("status") != "completed":
                continue
            adir = _sp.find_stage_dir(self.project_dir, sid)
            arts = sorted(_glob.glob(os.path.join(adir, "*-output.md")))
            if not arts:
                continue
            bucket = self.execution.stage_executions.setdefault(sid, [])
            existing = {getattr(e, "agent_id", "") for e in bucket}
            for a in arts:
                agent = os.path.basename(a).replace("-output.md", "")
                if agent in existing:
                    continue
                bucket.append(AgentExecution(agent_id=agent, stage_id=sid,
                                             status="completed", artifacts=[a]))

    def invalidate_for_rerun(self, only_stages: Optional[List[str]] = None,
                             from_stage: Optional[str] = None,
                             agents: Optional[List[str]] = None,
                             run_only: bool = False) -> Dict:
        """Reset selected stages/agents (and stale ALL downstream) for a selective rerun.

        Default (no `--only`): re-run selected + **all transitive downstream** (conservative,
        correctness-first). Agent-level selection also expands to downstream agents *within*
        the same stage via `agent_dependencies`.

        Returns {"rerun": [...stages], "invalidated": [...downstream stages], "agents": [..]}.
        """
        if not self.dag_executor:
            return {"rerun": [], "invalidated": [], "agents": []}
        cp = self._load_checkpoint()
        if cp:
            self._restore_from_checkpoint(cp)

        stages_cfg = (self.pipeline_def or {}).get("stages", {}) or {}
        seeds: set = set()
        agent_mode = bool(agents)
        selected_agents: set = set(agents or [])

        if agents:
            for sid in list(self.dag_executor.states):
                flow = (stages_cfg.get(sid, {}) or {}).get("ideal_flow", []) or []
                if not any(a in flow for a in agents):
                    continue
                seeds.add(sid)
                # within-stage downstream closure via agent_dependencies
                adeps = (stages_cfg.get(sid, {}) or {}).get("agent_dependencies", {}) or {}
                rev: Dict[str, set] = {}
                for a, preds in adeps.items():
                    for p in (preds or []):
                        rev.setdefault(p, set()).add(a)
                stack = [a for a in agents if a in flow]
                seen: set = set()
                while stack:
                    cur = stack.pop()
                    if cur in seen:
                        continue
                    seen.add(cur)
                    for nxt in rev.get(cur, ()):
                        selected_agents.add(nxt)
                        if nxt not in seen:
                            stack.append(nxt)

            # Artifact-provenance consumers (precise, complements agent_dependencies)
            try:
                from core.orchestrator.artifacts_map import consumers_transitive
                for nxt in consumers_transitive(list(selected_agents), getattr(self, "agent_specs", {})):
                    selected_agents.add(nxt)
            except Exception:
                pass

            # Any stage containing a (newly) selected agent is a rerun seed.
            for sid in list(self.dag_executor.states):
                flow = (stages_cfg.get(sid, {}) or {}).get("ideal_flow", []) or []
                if any(a in flow for a in selected_agents):
                    seeds.add(sid)
        if only_stages:
            seeds.update(s for s in only_stages if s in self.dag_executor.states)
            if run_only:
                # Include dependency ancestors so the scoped run is self-contained
                # (otherwise pending stages are blocked by out-of-scope deps and nothing runs).
                try:
                    deps = {sid: (self.pipeline_def.get("stages", {}).get(sid, {}) or {}).get("depends_on") or []
                            for sid in self.dag_executor.states}
                    stack = list(seeds)
                    while stack:
                        s = stack.pop()
                        for d in deps.get(s, []):
                            if d in self.dag_executor.states and d not in seeds:
                                seeds.add(d)
                                stack.append(d)
                except Exception:
                    pass
        if from_stage and from_stage in self.dag_executor.states:
            seeds.add(from_stage)
            seeds.update(self.dag_executor.downstream_of([from_stage]))

        seeds = sorted(seeds)
        downstream = self.dag_executor.downstream_of(seeds)

        if agent_mode:
            self.only_agents = selected_agents

        def _mark_rerun(sid: str, clear: bool):
            """STALE only if it was completed before; otherwise leave PENDING."""
            cur = self.dag_executor.states[sid].status.value
            if cur == "completed":
                self.dag_executor.mark_stale(sid)
            else:
                self.dag_executor.reset_stage(sid)
            if clear and self.execution:
                self.execution.stage_executions.pop(sid, None)

        for sid in seeds:
            # agent-level: keep prior executions (merge on run); stage-level: clear.
            _mark_rerun(sid, clear=not agent_mode)
        for sid in downstream:
            # Never-run downstream stays pending (not stale); completed ones go stale.
            _mark_rerun(sid, clear=False)

        self._save_checkpoint()
        # Layer 1: a deliberate rerun invalidates the fingerprint-keyed INPUT cache
        # for the affected agents/stages, so a rerun recomputes inputs too (the
        # generation output itself is never cached).
        try:
            ic = getattr(self, "input_cache", None)
            if ic is not None:
                if agent_mode:
                    _n = ic.clear(agents=sorted(selected_agents))
                else:
                    _n = ic.clear(stages=seeds)
                print(f"  [RERUN] input-cache invalidated: {_n} entr(ies)")
        except Exception as _e:
            print(f"  [RERUN] input-cache invalidation skipped: {_e}")
        # Persist scope so the (re)launched run honors agent-level / run-only selection.
        self._write_run_scope(
            only_stages=(seeds if run_only else None),
            only_agents=(sorted(selected_agents) if agent_mode else None),
        )
        print(f"  [RERUN] seeds={seeds} agents={sorted(selected_agents) if agent_mode else []} "
              f"invalidated_downstream={downstream}")
        # BI-0088: rerunning a stage must not leave stale prior-stage artifacts behind.
        try:
            cleared = self._clear_stale_stage_artifacts(seeds + list(downstream))
            if cleared:
                print(f"  [RERUN] cleared stale artifact(s): {cleared}")
        except Exception as _se:
            print(f"  [RERUN] stale-artifact cleanup skipped: {_se}")
        return {"rerun": seeds, "invalidated": downstream,
                "agents": sorted(selected_agents) if agent_mode else []}

    def _clear_stale_stage_artifacts(self, stage_ids):
        """BI-0088: remove a stage's prior agent outputs (and .partial) so a rerun
        cannot leave stale artifacts (e.g. old design-output.md/design.md). Keeps
        the dir; removes only <agent>-output.md / .partial it will regenerate."""
        import os as _os
        removed = 0
        for sid in set(stage_ids or []):
            d = _sp.find_stage_dir(self.project_dir, str(sid))
            if not _os.path.isdir(d):
                continue
            for f in _os.listdir(d):
                if f.endswith("-output.md") or f.endswith(".partial"):
                    try:
                        _os.remove(_os.path.join(d, f))
                        removed += 1
                    except Exception:
                        pass
        return removed
    
    def _create_approval_request(self, agent_id: str, stage_id: str, artifacts: List[str], gate_id: str = None) -> Dict:
        """Create an approval request for human review."""
        request_id = f"approval-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{agent_id}"
        
        # Get review instructions from orchestrator.md or use default
        review_instructions = self._get_review_instructions(agent_id, stage_id)
        
        request = {
            "request_id": request_id,
            "stage_id": stage_id,
            "agent_id": agent_id,
            "gate_id": gate_id,
            "status": "pending",
            "run_id": (self.execution.pipeline_id if self.execution else ""),
            "artifacts": artifacts,
            "created_at": datetime.now().isoformat(),
            "review_instructions": review_instructions,
            "approved_by": None,
            "approved_at": None,
            "notes": ""
        }
        
        # Save approval request
        approval_dir = os.path.join(self.project_dir, "approvals", stage_id)
        os.makedirs(approval_dir, exist_ok=True)
        approval_file = os.path.join(approval_dir, f"{agent_id}-approval.json")
        with open(approval_file, 'w', encoding='utf-8') as f:
            json.dump(request, f, indent=2, ensure_ascii=False)
        
        self.pending_approvals.append(request)
        return request
    
    def _get_review_instructions(self, agent_id: str, stage_id: str) -> str:
        """Get review instructions for an agent's output."""
        instructions = {
            "ideation": "Review ideation document. Check: problem statement clarity, target user definition, requirements completeness.",
            "design": "Review design document. Check: requirements coverage, architecture feasibility, API contracts.",
            "architect": "Review architecture. Check: component design, file structure, technology choices, security.",
            "implement": "Review implementation. Check: code quality, error handling, configuration.",
            "validate": "Review validation results. Check: test coverage, NFR compliance.",
            "security": "Review security findings. Check: severity ratings, remediation suggestions.",
            "code-review": "Review code review findings. Check: issues identified, suggestions quality.",
        }
        return instructions.get(agent_id, f"Review {agent_id} output for stage {stage_id}. Check completeness and quality.")
    
    def _check_approval_status(self, agent_id: str, stage_id: str) -> str:
        """Check if an agent's output has been approved."""
        approval_file = os.path.join(self.project_dir, "approvals", stage_id, f"{agent_id}-approval.json")
        if os.path.exists(approval_file):
            try:
                with open(approval_file, 'r', encoding='utf-8') as f:
                    request = json.load(f)
                return request.get("status", "pending")
            except Exception:
                return "pending"
        return "no_request"
    
    def _approval_file(self, agent_id: str, stage_id: str) -> str:
        return os.path.join(self.project_dir, "approvals", stage_id, f"{agent_id}-approval.json")

    def _read_approval_request(self, agent_id: str, stage_id: str) -> Dict:
        try:
            with open(self._approval_file(agent_id, stage_id), 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def _write_approval_request(self, agent_id: str, stage_id: str, request: Dict):
        try:
            path = self._approval_file(agent_id, stage_id)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(request, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"  [APPROVAL] could not update request: {e}")

    def _set_approval_status(self, agent_id: str, stage_id: str, status: str):
        req = self._read_approval_request(agent_id, stage_id)
        if req:
            req["status"] = status
            self._write_approval_request(agent_id, stage_id, req)

    def _approval_timeout_policy(self) -> str:
        """Timeout policy from project.json: wait|fail|skip|approve (default: wait)."""
        policy = "wait"
        try:
            pj = os.path.join(self.project_dir, "project.json")
            with open(pj, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            policy = str(cfg.get("approval_timeout_policy", "wait") or "wait").lower()
        except Exception:
            policy = "wait"
        if policy not in ("wait", "fail", "skip", "approve"):
            policy = "wait"
        return policy

    def _wait_for_approval_ex(self, agent_id: str, stage_id: str, artifacts: List[str]) -> Dict:
        """Full HIL decision model.

        Returns {"decision", "notes", "conditions"} where decision is one of:
        approved | approved_with_conditions | changes | regenerate | skip |
        rejected | abort | expired.
        """
        _ok = {"decision": "approved", "notes": "", "conditions": ""}
        # Auto mode: a Human-like agent (HIL proxy) makes the decision instead.
        try:
            if agent_id not in ("human", "product-owner"):
                from core.human_proxy import is_auto, decide
                if is_auto(self.project_dir):
                    d = decide(self, agent_id, stage_id, artifacts)
                    print(f"  [HUMAN-PROXY] {agent_id}@{stage_id}: {d.get('decision')} "
                          f"[{'; '.join(d.get('reasons') or [])[:120]}]")
                    self._log_decision("human_proxy", f"{agent_id} in stage {stage_id}",
                                       str(d.get("decision")))
                    return _ok
        except Exception as e:
            print(f"[HumanProxy] {e}")
        # Check auto_approve first
        if self.auto_approve:
            print(f"  [AUTO-APPROVE] {agent_id} (auto_approve=true)")
            self._log_decision("auto_approve", f"{agent_id} in stage {stage_id}", "auto_approve enabled")
            return _ok

        # Check approval mode
        if self.approval_mode == "auto":
            print(f"  [AUTO-APPROVE] {agent_id} (mode=auto)")
            return _ok

        # Semi / gates-only: routine agents auto-approve; only declared gates wait.
        # Gates are the ones invoked as `gate-<id>` (see _check_approval_gate).
        if self.approval_mode == "semi" and not str(agent_id).startswith("gate-"):
            print(f"  [SEMI-APPROVE] {agent_id} (gates-only mode)")
            return _ok

        # Create approval request
        request = self._create_approval_request(agent_id, stage_id, artifacts)
        # Brief summary (what was done + artifacts + next) so the reviewer has context.
        try:
            from core.progress import stage_summary as _ss
            print(_ss(self.pipeline_def, stage_id, agent_id, "awaiting-approval", artifacts,
                      project_dir=self.project_dir))
        except Exception:
            pass
        print(f"\n  [WAITING APPROVAL] {agent_id} in stage {stage_id}")
        print(f"  Artifacts: {len(artifacts)} files")
        print(f"  Approval file: approvals/{stage_id}/{agent_id}-approval.json")
        print(f"  Review instructions: {request['review_instructions']}")
        print(f"  approve: --approve | changes: --changes --notes \"...\" | regenerate: --regenerate | "
              f"skip: --skip | reject: --reject | abort: --abort")
        print(f"  approve+conditions: --approve --conditions \"...\" | snooze: --snooze <min> | "
              f"wait: --wait-minutes <min> | --wait-indefinite")

        # Non-interactive: the request is recorded; the run does not block.
        if self.approval_mode != "interactive":
            return _ok

        # Mark pipeline as paused
        if self.execution:
            self.execution.phase = PipelinePhase.PAUSED

        policy = self._approval_timeout_policy()
        # Honor PIPELINE_PROMPT_TIMEOUT; policy "wait" (interactive default) is indefinite.
        try:
            from core import env_flags as _ef
            max_wait = float(_ef.get("PIPELINE_PROMPT_TIMEOUT", "3600") or "0")
        except Exception:
            max_wait = 3600.0
        indefinite = (policy == "wait") or max_wait <= 0
        extended_until = None
        waited = 0
        _aw0 = time.time()
        try:
            while True:
                status = self._check_approval_status(agent_id, stage_id)

                if status in _status.APPROVAL_DECIDED or status in ("changes", "regenerate", "skip"):
                    req = self._read_approval_request(agent_id, stage_id)
                    notes = req.get("notes", "") or ""
                    conditions = req.get("conditions", "") or ""
                    print(f"  [DECISION] {agent_id} in stage {stage_id}: {status.upper()}")
                    self._log_decision(status, f"{agent_id} in stage {stage_id}",
                                       (notes or conditions or f"human {status}")[:160])
                    return {"decision": status, "notes": notes, "conditions": conditions}

                if status == "snoozed":
                    req = self._read_approval_request(agent_id, stage_id)
                    su = req.get("snooze_until", "")
                    future = False
                    if su:
                        try:
                            future = datetime.fromisoformat(su) > datetime.now()
                        except Exception:
                            future = False
                    if future:
                        print(f"  [SNOOZED] {agent_id}; deferring until {su}")
                        time.sleep(5)
                        waited += 5
                        if waited % 30 == 0:
                            print(f"  [WAITING] Still snoozed... ({waited}s)")
                        continue
                    self._set_approval_status(agent_id, stage_id, "pending")
                    print(f"  [SNOOZE] {agent_id}: snooze elapsed, awaiting new decision")
                    continue

                if status == "waiting":
                    req = self._read_approval_request(agent_id, stage_id)
                    if req.get("wait_indefinite"):
                        indefinite = True
                        print(f"  [WAIT] {agent_id}: waiting indefinitely")
                    elif req.get("wait_until"):
                        try:
                            dt = datetime.fromisoformat(req["wait_until"])
                            extended_until = max(extended_until or 0.0, dt.timestamp())
                            print(f"  [WAIT] {agent_id}: deadline extended to {req['wait_until']}")
                        except Exception:
                            pass
                    else:
                        indefinite = True
                    # Re-open the request so a later decision can be applied.
                    self._set_approval_status(agent_id, stage_id, "pending")
                    continue

                if status == "no_request":
                    # The request file vanished (e.g. rerun cleared it): recreate it.
                    self._create_approval_request(agent_id, stage_id, artifacts)

                # Normal "pending": honor a finite deadline if one applies.
                if not indefinite:
                    deadline = extended_until if extended_until is not None else (_aw0 + max_wait)
                    if time.time() >= deadline:
                        break

                time.sleep(5)
                waited += 5
                if waited % 30 == 0:
                    print(f"  [WAITING] Still waiting for approval... ({waited}s)")

            # Timeout -> apply policy: wait|fail|skip|approve
            print(f"  [TIMEOUT] Approval wait timed out (policy={policy})")
            self._set_approval_status(agent_id, stage_id, "expired")
            self._log_decision("expired", f"{agent_id} in stage {stage_id}",
                               f"approval timed out (policy={policy})")
            if policy == "approve":
                return {"decision": "approved", "notes": "auto-approved on timeout", "conditions": ""}
            if policy == "skip":
                return {"decision": "skip", "notes": "timeout policy: skip", "conditions": ""}
            return {"decision": "rejected", "notes": "approval timed out", "conditions": ""}
        finally:
            # Human-wait time must not count against the stage time budget (BI-0074).
            self._stage_human_wait_seconds = float(
                getattr(self, "_stage_human_wait_seconds", 0.0)) + (time.time() - _aw0)

    def _wait_for_approval(self, agent_id: str, stage_id: str, artifacts: List[str]) -> bool:
        """Wait for human approval. Returns True if approved (back-compat bool)."""
        res = self._wait_for_approval_ex(agent_id, stage_id, artifacts)
        return str(res.get("decision", "")) in ("approved", "approved_with_conditions")
    
    def _check_approval_gate(self, stage_id: str) -> bool:
        """Check if stage has an approval gate and wait for approval."""
        if not self.pipeline_def:
            return True
        
        stage_def = self.pipeline_def.get("stages", {}).get(stage_id, {})
        gate_id = stage_def.get("approval_gate")
        
        if not gate_id:
            return True  # No gate defined
        
        print(f"\n  [APPROVAL GATE] Stage {stage_id} requires gate approval: {gate_id}")
        return self._wait_for_approval(f"gate-{gate_id}", stage_id, [])
    
    def _detect_anomaly(self, stage_id: str, duration: float) -> bool:
        """Detect if stage took unusually long."""
        if len(self.stage_durations) < 3:
            return False
        
        avg = sum(self.stage_durations) / len(self.stage_durations)
        if duration > avg * self.anomaly_threshold:
            print(f"  [ANOMALY] Stage {stage_id} took {duration:.1f}s (avg: {avg:.1f}s, threshold: {self.anomaly_threshold}x)")
            self._log_decision("anomaly", f"stage {stage_id} duration {duration:.1f}s", f"exceeds {self.anomaly_threshold}x average")
            return True
        return False
    
    def _initialize_budgets(self):
        """Initialize token budgets for the pipeline."""
        # Pipeline-wide budget
        self.budget_manager.create_budget(
            "pipeline_total",
            BudgetType.PIPELINE_TOTAL,
            max_tokens=100000,  # 100K tokens total per pipeline
            scope=self.project
        )
        
        # Per-knowledge-load budget (default)
        self.budget_manager.create_budget(
            "knowledge_default",
            BudgetType.KNOWLEDGE_LOAD,
            max_tokens=5000,  # 5K tokens per knowledge load
            scope=self.project
        )
    
    def _load_tier_config(self) -> Dict:
        """Delegates to core/orchestrator/model_router (1A.11)."""
        return self.model_router.load_tier_config()

    def _get_model_tier(self, agent_id: str, stage_id: str) -> Optional[str]:
        """Delegates to core/orchestrator/model_router (1A.11)."""
        return self.model_router.get_model_tier(agent_id, stage_id)
    
    def load_pipeline(self, pipeline_file: str) -> bool:
        """Load a pipeline definition from file."""
        try:
            with open(pipeline_file, 'r', encoding='utf-8') as f:
                self.pipeline_def = json.load(f)
            # BI-0115: apply per-project tailoring (drop disabled OPTIONAL stages).
            # Ids stay stable; only the enabled set changes.
            try:
                from core import pipeline_tailoring as _pt
                _plan = _pt.load_plan(self.project_dir)
                if _plan:
                    self.pipeline_def = _pt.apply_plan(self.pipeline_def, _plan)
                    print(f"[Tailoring] applied pipeline-plan.json: "
                          f"enabled_optional={_plan.get('enabled_optional')} "
                          f"disabled_optional={_plan.get('disabled_optional')}")
                    # BI-0116: if the plan names a TEMPLATE, the template drives the stage map.
                    _tid = _plan.get("template") or _plan.get("template_id")
                    if _tid:
                        try:
                            from core import pipeline_templates as _tpl
                            _t = _tpl.get_template(_tid)
                            if _t:
                                self.pipeline_def = _tpl.apply_template(self.pipeline_def, _t)
                                print(f"[Template] applied template '{_tid}' "
                                      f"({len(self.pipeline_def['stages'])} stages)")
                        except Exception as _xe:
                            print(f"[Template] skipped: {_xe}")
            except Exception as _te:
                print(f"[Tailoring] skipped: {_te}")
            if getattr(self, "model_router", None):
                self.model_router.pipeline_def = self.pipeline_def
            
            # Create DAG executor
            self.dag_executor = DAGExecutor(self.pipeline_def)
            
            # Initialize execution state
            self.execution = PipelineExecution(
                pipeline_id=new_run_id(),
                project=self.project,
                pipeline_file=pipeline_file,
                phase=PipelinePhase.INIT,
                started_at=datetime.now().isoformat()
            )

            self._init_delegation()
            return True
        except Exception as e:
            print(f"[PipelineExecutor] Error loading pipeline: {e}")
            return False

    def _init_delegation(self):
        """(Re)build the delegation router from the loaded pipeline definition."""
        self.delegation_router = self.delegation_coord.init(self.pipeline_def, self.delegation_enabled)
    
    def load_pipeline_from_dict(self, pipeline_def: Dict) -> bool:
        """Load pipeline from dictionary."""
        try:
            self.pipeline_def = pipeline_def
            if getattr(self, "model_router", None):
                self.model_router.pipeline_def = self.pipeline_def
            self.dag_executor = DAGExecutor(pipeline_def)
            
            self.execution = PipelineExecution(
                pipeline_id=new_run_id(),
                project=self.project,
                pipeline_file="inline",
                phase=PipelinePhase.INIT,
                started_at=datetime.now().isoformat()
            )

            self._init_delegation()
            return True
        except Exception as e:
            print(f"[PipelineExecutor] Error loading pipeline dict: {e}")
            return False
    
    def get_knowledge_for_agent(self, agent_id: str, stage_id: str, task: str) -> RoutingDecision:
        """Get relevant knowledge for an agent with budget protection."""
        # Map every real agent id to a knowledge domain present in docs/guidelines.
        domain_map = {
            "ideation": "business",
            "discovery": "business-models",
            "design": "frontend",
            "product-design-spec": "frontend",
            "design_critic": "frontend",
            "ux-ia": "ui-ux",
            "visual_qa": "ui-ux",
            "architect": "architecture",
            "implement": "backend",
            "implement-db": "database",
            "implement-api": "api",
            "implement-logic": "backend",
            "implement-ui": "frontend",
            "devops": "infrastructure",
            "code-review": "coding",
            "validate": "testing",
            "security": "security",
            "document": "shared",
            "package": "packaging",
            "orchestrator": "shared",
        }
        
        domain = domain_map.get(agent_id, None)
        
        # Knowledge is loaded once per agent run, so give each agent a fresh
        # budget (avoids the persisted per-run budget cap of 5K blocking large
        # guides like the React/FastAPI docs).
        budget_id = f"knowledge_{stage_id}_{agent_id}"
        self.budget_manager.create_budget(
            budget_id,
            BudgetType.KNOWLEDGE_LOAD,
            max_tokens=self.knowledge_budget_tokens,
            scope=f"knowledge:{agent_id}@{stage_id}",
        )

        # Use safe routing with budget protection.
        return safe_knowledge_route(
            self.knowledge_router,
            task=task,
            budget_manager=self.budget_manager,
            budget_id=budget_id,
            max_tokens=self.knowledge_budget_tokens,
            domain=domain,
            stage=stage_id,
            agent=agent_id
        )
    
    def use_reasoning(self, skill_name: str, problem: str, context: Dict = None) -> Any:
        """Use a reasoning skill."""
        return self.reasoning.execute(skill_name, problem, context or {})
    
    def store_memory(self, memory_type: str, content: str, source: str, 
                     confidence: float = 0.9, tags: List[str] = None) -> bool:
        """Store a memory entry."""
        result = self.memory.store(
            memory_type=memory_type,
            content=content,
            source=source,
            confidence=confidence,
            tags=tags or []
        )
        return result is not None
    
    def run_compliance_check(self, agent_id: str, stage_id: str) -> Dict:
        """Delegates to core/orchestrator/compliance (1A.11)."""
        return self.compliance_orchestrator.run_rule_compliance(agent_id, stage_id)

    def _record_cost_kpi(self, agent_id: str, stage_id: str, execution):
        """Record a per-agent task in the cost-per-successful-task tracker."""
        if not getattr(self, "cost_kpi", None) or execution is None:
            return
        try:
            from core.cost_kpi import TaskCost
            self.cost_kpi.record_task(TaskCost(
                task_id=f"{self.project}:{stage_id}:{agent_id}",
                project=self.project,
                stage=stage_id,
                stage_name=stage_id,
                agent=agent_id,
                success=(execution.status == "completed"),
                input_tokens=getattr(execution, "input_tokens", 0),
                output_tokens=getattr(execution, "output_tokens", 0),
                cost_usd=getattr(execution, "cost", 0.0),
                duration_seconds=0.0,
                retries=getattr(execution, "retries", 0),
            ))
        except Exception:
            pass

    def _validate_state_schemas(self) -> Dict:
        """Validate project state files against docs/schemas (PART 6)."""
        out = {}
        try:
            from core.schema_validator import validate_artifact
        except Exception:
            return out
        candidates = [("pipeline-state", self.state_file),
                      ("project", os.path.join(self.project_dir, "project-config.json")),
                      ("infra", os.path.join(self.project_dir, "docs", "infra.json"))]
        for name, path in candidates:
            try:
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    r = validate_artifact(name, data)
                    out[name] = {"valid": bool(r.valid),
                                 "errors": [e.message for e in r.errors][:5]}
            except Exception as e:
                out[name] = {"valid": None, "error": str(e)}
        return out

    def _fix_review_enabled(self) -> bool:
        """Whether fixes must be approved by the reviewer agent (default ON)."""
        try:
            import json
            pj = os.path.join(self.project_dir, "project.json")
            if os.path.exists(pj):
                cfg = ((json.load(open(pj, encoding="utf-8")) or {}).get("review") or {})
                if "fix" in cfg:
                    return bool(cfg["fix"])
        except Exception:
            pass
        return os.environ.get("PIPELINE_FIX_REVIEW", "1") != "0"

    def _vcs(self):
        """Lazy VCS manager (enabled only when project.json declares `vcs`)."""
        try:
            v = getattr(self, "_vcs_mgr", None)
            if v is None:
                import json
                cfg = {}
                pj = os.path.join(self.project_dir, "project.json")
                if os.path.exists(pj):
                    cfg = ((json.load(open(pj, encoding="utf-8")) or {}).get("vcs") or {})
                if not cfg:
                    return None
                from core.vcs import VCSManager
                v = VCSManager(self.project_dir, cfg)
                self._vcs_mgr = v
            return v
        except Exception:
            return None

    def _vcs_stage_branch(self, stage_id: str):
        """Create a feature branch for an implementation stage (orchestrator-owned)."""
        v = self._vcs()
        if not v:
            return
        try:
            import time
            v.init()
            v.feature_branch(f"feat/stage-{stage_id}-{int(time.time())}")
        except Exception as e:
            print(f"  [VCS] branch: {e}")

    def _vcs_stage_finalize(self, stage_id: str):
        """Commit stage output, push, and merge the feature branch into develop."""
        v = self._vcs()
        if not v:
            return
        try:
            br = v.current_branch()
            v.commit(f"feat(stage-{stage_id}): pipeline output")
            v.push(br)
            res = v.merge(br, v.integration_branch, f"merge {br} into {v.integration_branch}")
            if res.get("blocked"):
                print(f"  [VCS] merge blocked (PR checklist): {res.get('reason')} "
                      f"| unmet={res.get('unmet')}")
            else:
                print(f"  [VCS] merged {br} -> {v.integration_branch}")
        except Exception as e:
            print(f"  [VCS] finalize: {e}")

    def _vcs_wip(self):
        v = self._vcs()
        if not v:
            return
        try:
            v.wip_snapshot(getattr(self, "execution", None) and self.execution.pipeline_id or "")
        except Exception:
            pass

    def _vcs_rc_tag(self):
        """Tag the staging build (RC) — most stable build, not every build."""
        v = self._vcs()
        if not v:
            return
        try:
            from core.build_manager import latest_build
            b = latest_build(self.project_dir) or {}
            if b.get("build_id"):
                v.tag(f"v{b.get('version')}-rc.{b.get('build_number')}",
                      f"staging RC {b.get('build_id')}")
                v.push(v.current_branch())
                print(f"  [VCS] RC tag v{b.get('version')}-rc.{b.get('build_number')}")
        except Exception as e:
            print(f"  [VCS] rc tag: {e}")

    def _vcs_release(self):
        """Release: develop -> main + release tag. Requires QA GO **and** HIL approval."""
        v = self._vcs()
        if not v:
            return
        try:
            from core.qa_report import load as gng_load
            if (gng_load(self.project) or {}).get("decision") != "GO":
                print("  [VCS] release skipped: QA Go/No-Go != GO")
                return
            # develop -> main needs HIL approval (auto mode = human pre-approved).
            if not (getattr(self, "auto_approve", False)
                    or os.environ.get("PIPELINE_RELEASE_APPROVED") == "1"):
                print("  [VCS] release pending HIL approval (set auto_approve or "
                      "PIPELINE_RELEASE_APPROVED=1)")
                return
            from core.build_manager import latest_build
            b = latest_build(self.project_dir) or {}
            v.merge(v.integration_branch, v.release_branch,
                    f"release v{b.get('version')} into {v.release_branch}")
            v.tag(f"v{b.get('version')}", f"release {b.get('build_id')}")
            v.push(v.release_branch)
            print(f"  [VCS] released v{b.get('version')} to {v.release_branch}")
        except Exception as e:
            print(f"  [VCS] release: {e}")

    def _audit_trail_log(self, action: str, agent_id: str, stage_id: str):
        """Durable, queryable audit stream (core/audit_trail)."""
        try:
            from core.audit_trail import AuditTrail, AuditAction
            trail = getattr(self, "_audit_trail", None)
            if trail is None:
                trail = AuditTrail(self.project)
                self._audit_trail = trail
            act = AuditAction(action) if action in {a.value for a in AuditAction} else AuditAction.CUSTOM
            st = int(stage_id) if str(stage_id).isdigit() else 0
            trail.log_action(act, agent_id, st, "")
        except Exception:
            pass

    def _review_fix(self, execution, stage_id: str, artifacts: List[str]):
        """Run the reviewer (code-review) agent over a fix; block on changes requested."""
        if getattr(self, "_fix_review_active", False):
            return
        self._fix_review_active = True
        try:
            task = (
                "Review the FIX just produced for this project. Open defects and fix "
                "artifacts are in context. Assess: (1) every open defect is actually "
                "addressed, (2) no regressions or new issues were introduced, "
                "(3) tests were added/updated to cover the fix. "
                "End with a line 'REVIEW: APPROVED' or 'REVIEW: CHANGES_REQUESTED' "
                "followed by the reasons."
            )
            rev = self.execute_agent("code-review", stage_id, task)
            text = ""
            for p in (getattr(rev, "artifacts", []) or []):
                try:
                    with open(p, encoding="utf-8") as f:
                        text += f.read()
                except Exception:
                    pass
            upper = text.upper()
            verdict = ("changes_requested" if "CHANGES_REQUESTED" in upper
                       else "approved" if "APPROVED" in upper else "unknown")
            try:
                execution.compliance_report = execution.compliance_report or {}
                execution.compliance_report["fix_review"] = {
                    "status": getattr(rev, "status", "unknown"),
                    "verdict": verdict,
                    "artifacts": getattr(rev, "artifacts", []),
                }
            except Exception:
                pass
            print(f"  [FIX-REVIEW] {verdict}")
            if verdict == "changes_requested":
                execution.status = "needs_retry"
                execution.error = "Fix review: changes requested by reviewer"
                try:
                    execution.compliance_report["retry_feedback"] = text[-2000:]
                except Exception:
                    pass
        except Exception as e:
            print(f"[FixReview] {e}")
        finally:
            self._fix_review_active = False

    def _ensure_test_scaffolds(self, stage_id: str):
        """Opt-in: generate stack-agnostic test scaffolds (FR/NFR tagged) for implement.

        Enabled by `project.json: test.generate` or env PIPELINE_GENERATE_TESTS=1.
        """
        try:
            import json
            pj = os.path.join(self.project_dir, "project.json")
            test_cfg = {}
            if os.path.exists(pj):
                test_cfg = ((json.load(open(pj, encoding="utf-8")) or {}).get("test") or {})
            enabled = bool(test_cfg.get("generate")) or os.environ.get("PIPELINE_GENERATE_TESTS") == "1"
            if not enabled:
                return None
            if os.path.isdir(os.path.join(self.project_dir, "tests", "generated")):
                return None
            feats = []
            try:
                feats = [{"id": f.get("id"), "name": f.get("title", "")}
                         for f in self.phasing.extract_features()]
            except Exception:
                pass
            if not feats:
                return None
            from core.defect_loop import generate_tests
            res = generate_tests(self.project_dir, feats,
                                 categories=test_cfg.get("categories") or {"unit": True})
            print(f"  [TestGen] scaffolds: {res}")
            return res
        except Exception as e:
            print(f"[TestGen] {e}")
            return None

    def _run_qa_gate(self, stage_id: str):
        """QA Go/No-Go gate (stage 10a) — decision + QIR + matrix."""
        try:
            from core.qa_report import go_no_go
            return go_no_go(self.project, self.project_dir,
                            getattr(self, "tech_stack", {}) or {})
        except Exception as e:
            print(f"[GoNoGo] {e}")
            return None

    def _select_target(self):
        """Deployment target: declared, or HIL-prompted catalog (default local)."""
        try:
            from core.target_selector import select
            res = select(self.project_dir, self.project)
            print(f"  [TARGET] {res.get('target')} (source={res.get('source')}) "
                  f"requires={res.get('requires') or 'none'}")
            return res
        except Exception as e:
            print(f"[Target] {e}")
            return None

    def _run_extended_capabilities(self):
        """Invoke extended capabilities once per run (git/cost/finops/release/...)."""
        try:
            import json
            from core.pipeline_capabilities import run as caps_run
            domain = ""
            try:
                pj = os.path.join(self.project_dir, "project.json")
                if os.path.exists(pj):
                    domain = str((json.load(open(pj, encoding="utf-8")) or {}).get("product_domain") or "")
            except Exception:
                domain = ""
            pkind = ""
            try:
                from core.test_matrix import product_kind
                pkind = product_kind(getattr(self, "tech_stack", {}) or {})
            except Exception:
                pkind = ""
            rep = caps_run(self.project_dir, self.project, domain=domain, product_kind=pkind)
            print(f"  [Capabilities] {rep.get('ok_count')} extended capabilities ran")
        except Exception as e:
            print(f"[Capabilities] {e}")

    def _recommend_integrations(self):
        """Pipeline intelligence recommends integrations.

        - internal / low-impact  -> auto-apply and continue (no prompt).
        - user-facing OR unclear -> needs HIL: prompt for confirmation (TTY);
          non-interactive falls back to internal-only and records it as pending.
        """
        try:
            import sys
            from core.integration_advisor import (recommend, plain_summary, hil_options,
                                                   apply_choices, choices_recommended,
                                                   choices_internal_only, needs_hil)
            rec = recommend(self.project_dir, self.project)
            print(plain_summary(rec))

            # DEFAULT: apply the recommended packs automatically. They help (domain
            # practices + an infra service catalog with defaults), so there is nothing to
            # ask. Opt in to being prompted with PIPELINE_ASK_INTEGRATIONS=1.
            if str(os.getenv("PIPELINE_ASK_INTEGRATIONS", "0")).lower() not in ("1", "true", "yes"):
                apply_choices(self.project_dir, rec, choices_recommended(rec))
                try:
                    from core.integration_advisor import _LABEL as _LBL
                    _on = [_LBL.get(n, n) for n, f in rec.get("flags", {}).items() if f.get("enabled")]
                except Exception:
                    _on = [n for n, f in rec.get("flags", {}).items() if f.get("enabled")]
                print("  [integrations] applied recommended packs automatically: "
                      + (", ".join(_on) if _on else "none"))
                return

            # Idempotent reuse of recorded choices — BUT in an interactive run we
            # must not silently skip; fall through so the operator can review/confirm.
            _cf = os.path.join(self.project_dir, "integration_choices.json")
            if os.path.exists(_cf):
                try:
                    with open(_cf, encoding="utf-8") as _fh:
                        _prev = (json.load(_fh) or {}).get("choices") or {}
                    if _prev:
                        _is_interactive = False
                        try:
                            from core import interactive as _ia
                            _is_interactive = _ia.enabled() or sys.stdin.isatty()
                        except Exception:
                            _is_interactive = False
                        if not _is_interactive:
                            apply_choices(self.project_dir, rec, _prev)
                            print("  [integrations] using previously recorded choices")
                            return
                        print("  [integrations] interactive: reviewing integration choices "
                              "(previously recorded; pick the recommended option to keep)")
                except Exception:
                    pass

            if not needs_hil(rec):
                apply_choices(self.project_dir, rec, choices_recommended(rec))
                print("  [integrations] auto-applied (internal only; no product impact)")
                return

            from core import interactive as _interactive
            if not _interactive.enabled() and not sys.stdin.isatty():
                apply_choices(self.project_dir, rec, choices_internal_only(rec))
                print("  [integrations] HIL needed for user-facing options; "
                      "applied internal-only pending confirmation")
                return

            opts = hil_options(rec)
            try:
                from core.integration_advisor import RISK as _IRISK
                from core.integration_advisor import _LABEL as _ILABEL
            except Exception:
                _IRISK, _ILABEL = {}, {}

            def _impact(choice: Dict) -> str:
                on = [n for n, v in (choice or {}).items() if v]
                if not on:
                    return "enables nothing"
                parts = []
                for n in on:
                    lbl = _ILABEL.get(n, n)
                    uf = _IRISK.get(n, "internal") != "internal"
                    parts.append(f"{lbl}{' [user-facing]' if uf else ' [internal]'}")
                return "enables: " + "; ".join(parts)

            uf = {n: f for n, f in rec.get("flags", {}).items()
                  if _IRISK.get(n, "internal") != "internal"}
            opt_lines = [f"{i}. {o['label']}" for i, o in enumerate(opts, 1)]
            opt_lines.append(f"{len(opts) + 1}. Customize - decide each product-shaping pack individually")
            prompt_txt = (
                "Some optional packs can change the shipped PRODUCT/UX - do you want them? "
                "(Quality-only 'internal' packs are applied automatically and are NOT asked.) "
                f"Pick 1-{len(opts) + 1}: ")
            print("  " + prompt_txt)
            for ln in opt_lines:
                print("    " + ln)
            try:
                from core.integration_advisor import _DESC as _IDESC
                if uf:
                    print("  Product-shaping packs (what they do):")
                    for n, f in uf.items():
                        print(f"    - {_ILABEL.get(n, n)}: {_IDESC.get(n, '')}  (why: {f.get('reason', '')})")
                intern = [n for n in (rec.get("flags") or {}) if _IRISK.get(n, "internal") == "internal"]
                if intern:
                    print("  Applied automatically (internal quality, no product impact): "
                          + "; ".join(_ILABEL.get(n, n) for n in intern))
            except Exception:
                pass
            try:
                ans = (_interactive.ask(prompt_txt, "1", project_dir=self.project_dir,
                                        options=opt_lines) or "1").strip()
            except Exception:
                ans = "1"
            if ans.isdigit() and 1 <= int(ans) <= len(opts):
                chosen = opts[int(ans) - 1]["choices"]
            elif ans.isdigit() and int(ans) == len(opts) + 1:
                # Customize: internal defaults are kept; only product-shaping packs are asked.
                try:
                    from core.integration_advisor import with_internal as _win
                    chosen = _win(rec, {})
                except Exception:
                    chosen = {}
                for n, f in uf.items():
                    try:
                        a = _interactive.ask(
                            f"    {_ILABEL.get(n, n)} ({f['reason']}) "
                            f"[{'Y/n' if f['enabled'] else 'y/N'}] > ",
                            "", project_dir=self.project_dir, kind="flag")
                    except Exception:
                        a = ""
                    a = (a or "").strip().lower()
                    chosen[n] = bool(f["enabled"]) if a == "" else a.startswith("y")
            else:
                chosen = opts[0]["choices"]
            apply_choices(self.project_dir, rec, chosen)
            print("  [integrations] choices recorded")
        except Exception as e:
            print(f"[Integrations] {e}")

    def _run_spec_review(self, stage_id: str):
        """QA spec review gate (stage 3a): review all design/architect artifacts."""
        try:
            from core.spec_review import review_all
            from core.feature_flags import enabled as _flag
            llm = self._spec_llm_review if _flag("spec_llm", self.project_dir) else None
            return review_all(self.project_dir, self.project, llm_review=llm)
        except Exception as e:
            print(f"[SpecReview] {e}")
            return None

    def _spec_llm_review(self, artifact: str, text: str) -> List[str]:
        """Optional LLM advisory findings for a spec artifact (PIPELINE_SPEC_LLM=1)."""
        try:
            prompt = (
                "You are a Senior QA reviewer. Review this spec artifact from E2E quality "
                "and customer/usability angles. List at most 6 concrete advisory issues, "
                "one per line, no preamble.\n\nARTIFACT: " + artifact + "\n\n" + text[:8000])
            out, _meta = self._call_llm(prompt, "validate", "3a")
            if not out:
                return []
            return [ln.strip(" -•\t") for ln in out.splitlines() if len(ln.strip()) > 12][:6]
        except Exception:
            return []

    def _run_test_cycle(self, stage_id: str):
        """Run a test-framework cycle for the validate stage (functional/NFR/...)."""
        try:
            from core.test_framework_integration import run_cycle
            feats = []
            try:
                feats = [{"id": f.get("id"), "name": f.get("title", "")}
                         for f in self.phasing.extract_features()]
            except Exception:
                pass
            res = run_cycle(self.project, self.project_dir, stage_id,
                            features=feats, products_dir=self.products_dir)
            self._test_cycle = res
            try:
                ins = (res or {}).get("insights") or {}
                if ins.get("high"):
                    self._notify("quality", "QA intelligence",
                                 f"{ins.get('high')} high-severity QA insight(s) in stage {stage_id}",
                                 priority="high", agent="validate",
                                 stage=int(stage_id) if str(stage_id).isdigit() else -1)
            except Exception:
                pass
            return res
        except Exception as e:
            print(f"[TestCycle] {e}")
            return None

    def _run_post_deploy(self) -> Dict:
        """Apply -> verify -> destroy via the selected deployment provider (gap 8)."""
        try:
            from core.deploy_providers import run_deploy, load_deploy_cfg
            cfg = load_deploy_cfg(self.project_dir)
            if "port" not in cfg:
                try:
                    p = os.path.join(self.project_dir, "docs", "ports.json")
                    if os.path.exists(p):
                        for _n, info in ((json.load(open(p, encoding="utf-8")).get("services")) or {}).items():
                            if info.get("external"):
                                cfg["port"] = info["external"]
                                break
                except Exception:
                    pass
            res = run_deploy(self.project_dir, cfg)
            self._post_deploy = res
            if res.get("ran"):
                print(f"  [POST-DEPLOY] provider={res.get('provider')} passed={res.get('passed')}")
            else:
                print(f"  [POST-DEPLOY] skipped: {res.get('reason')}")
            # LIVE/OPS phase (opt-in via project.json -> ops.enabled).
            try:
                from core.ops_phase import run as _ops_run, enabled as _ops_enabled
                if _ops_enabled(self.project_dir):
                    self._ops = _ops_run(self)
                    print(f"  [OPS] monitor={self._ops.get('monitor')} "
                          f"incidents={(self._ops.get('incidents') or {}).get('incidents')}")
                else:
                    self._ops = {"enabled": False}
            except Exception as e:
                self._ops = {"enabled": False, "error": str(e)}
            return res
        except Exception as e:
            print(f"[PostDeploy] {e}")
            self._post_deploy = {"ran": False, "error": str(e)}
            return self._post_deploy

    def run_loop(self, loop_id, action, duration_seconds=3600, interval=60):
        """Time-based long-running loop (4.9 / loop_modes) for monitor/deploy agents."""
        if not getattr(self, "loop_controller", None):
            return None
        try:
            return self.loop_controller.execute_time_based(
                loop_id=loop_id, action=action,
                duration_seconds=duration_seconds, interval=interval)
        except Exception as e:
            print(f"[LoopController] {e}")
            return None

    def _nfr_coverage(self):
        """NFR id -> test coverage (4.3)."""
        try:
            from core.nfr_coverage import compute_nfr_coverage
            return compute_nfr_coverage(self.project_dir)
        except Exception:
            return None

    def _enforce_coverage_enabled(self) -> bool:
        """Whether missing FR/NFR test coverage fails validation (default OFF)."""
        try:
            import json
            pj = os.path.join(self.project_dir, "project.json")
            if os.path.exists(pj):
                t = ((json.load(open(pj, encoding="utf-8")) or {}).get("test") or {})
                if "enforce_coverage" in t:
                    return bool(t["enforce_coverage"])
        except Exception:
            pass
        return os.environ.get("PIPELINE_ENFORCE_COVERAGE", "0") == "1"

    def _notify(self, ntype: str, title: str, message: str, priority: str = "medium",
                agent: str = "", stage: int = -1):
        """Send a human notification (best-effort; opt-in system)."""
        if not getattr(self, "notifications", None):
            return
        try:
            from core.notification_system import NotificationType
            valid = {t.value for t in NotificationType}
            t = NotificationType(ntype) if ntype in valid else NotificationType.CUSTOM
            self.notifications.send_notification(
                t, title, message, agent=agent, stage=stage, priority=priority)
        except Exception:
            pass

    def _handle_agent_failure(self, agent_id: str, stage_id: str, execution):
        """Route a failed agent to DLQ + LLM error log + notifications."""
        err = getattr(execution, "error", "") or getattr(execution, "status", "failed")
        if getattr(self, "dlq", None):
            try:
                self.dlq.add_item(task=f"{agent_id}@{stage_id}", agent=agent_id,
                                  stage=stage_id, error=err)
            except Exception:
                pass
        if getattr(self, "llm_error_handler", None) and (
                "LLM" in str(err) or not getattr(execution, "selected_model", "")):
            try:
                from core.llm_error_handler import LLMErrorType
                self.llm_error_handler.handle_error(
                    LLMErrorType.API_FAILURE, str(err), agent_id, stage_id)
            except Exception:
                pass
        self._notify("agent_error", f"{agent_id} failed at stage {stage_id}",
                     str(err), priority="high", agent=agent_id)

    def _track_features_for_stage(self, stage_id, stage_executions):
        """Update ProductPlan feature status based on a completed stage (3.2/3.9)."""
        ft = getattr(self, "feature_tracker", None)
        if not ft:
            return
        try:
            all_feats = self.phasing.extract_features()
        except Exception:
            all_feats = []
        if all_feats:
            ft.seed(all_feats)
        all_ids = [f["id"] for f in all_feats if f.get("id")]
        agents = [getattr(e, "agent_id", "") for e in (stage_executions or [])]
        try:
            if stage_id in PHASE_STAGES and any(a.startswith("implement") for a in agents):
                ids = [s.split(":")[0].strip() for s in self.phasing.features_for_stage(stage_id)]
                files = [f for e in (stage_executions or []) for f in (e.artifacts or [])]
                ft.mark_implemented(ids, agent=(agents[0] if agents else None), files=files)
            if "validate" in agents:
                ft.mark_tested(all_ids, status="passed")
            if any(a in ("security", "security-audit") for a in agents):
                ft.mark_security(all_ids)
            if "code-review" in agents:
                ft.mark_reviewed(all_ids)
        except Exception:
            pass
        ft.save()

    def _run_llm_verification(self, agent_id: str, stage_id: str, artifacts: List[str]):
        """Opt-in LLM-as-verifier (a second model reviews the agent's work).

        Returns the verification report dict, or None when disabled / no checks.
        """
        if not getattr(self, "enable_llm_verification", False):
            return None
        try:
            from core.compliance_verifier import execute_verification, save_verification_report
            cfg = self.model_router.get_agent_model_config(agent_id, stage_id)
            art_map = {}
            for p in (artifacts or []):
                try:
                    art_map[os.path.basename(p)] = p
                except Exception:
                    pass
            report = execute_verification(
                agent_id=agent_id, project=self.project, artifact_paths=art_map,
                model=cfg.get("model", ""), provider=cfg.get("provider", ""),
                api_endpoint=cfg.get("api_endpoint", ""),
            )
            if report and report.results:
                try:
                    save_verification_report(report)
                except Exception:
                    pass
                return report.to_dict()
        except Exception as e:
            print(f"[LLMVerifier] {e}")
        return None

    def _run_multi_model_review(self, agent_id: str, stage_id: str, artifacts: List[str]):
        """Multi-model review of design/architecture artifacts (opt-in, 4.2)."""
        if not getattr(self, "enable_multi_model_review", False):
            return None
        kind = {"architect": "architecture", "design": "design"}.get(agent_id)
        if not kind:
            return None
        try:
            from core.multi_model_review import review
            from core.compliance_verifier import _resolve_api_key
            cfg = self.model_router.get_agent_model_config(agent_id, stage_id)
            reviewers = []
            for cand in (cfg.get("candidates") or [])[:3]:
                reviewers.append({**cand, "api_key": _resolve_api_key(cand.get("provider", ""))})
            text = ""
            for p in (artifacts or []):
                try:
                    with open(p, "r", encoding="utf-8", errors="ignore") as f:
                        text += f.read() + "\n"
                except Exception:
                    pass
            return review(kind, text, reviewers)
        except Exception as e:
            print(f"[MultiReview] {e}")
            return None

    def _finalize_tech_stack(self, stage_executions):
        """Parse the architect's tech-stack JSON, persist docs/tech-stack.json, gate on change."""
        text = ""
        for ex in stage_executions:
            for a in (ex.artifacts or []):
                try:
                    with open(a, "r", encoding="utf-8") as f:
                        text += f.read() + "\n"
                except Exception:
                    pass
        block = parse_tech_stack_block(text)
        rationale = ""
        declared_changed = None
        if block:
            rationale = str(block.pop("rationale", "") or "")
            block.pop("requested", None)
            declared_changed = block.pop("changed_from_request", None)
            chosen = {k: block.get(k) for k in
                      ("kind", "languages", "frameworks", "database", "cache", "deploy", "runtime")}
        else:
            req = list(getattr(self, "requested_tech_stack", []) or [])
            chosen = {"kind": "cli", "languages": req, "frameworks": [],
                      "database": None, "cache": None, "deploy": None, "runtime": None}

        decision = build_decision(self.requested_tech_stack, chosen, rationale)
        decision["chosen"] = chosen
        if declared_changed is not None:
            decision["changed_from_request"] = bool(declared_changed)
        path = save_tech_stack(self.project_dir, decision)
        self.tech_stack = decision
        print(f"  [TECHSTACK] kind={chosen.get('kind')} languages={chosen.get('languages')} "
              f"frameworks={chosen.get('frameworks')} changed_from_request={decision['changed_from_request']}")

        if decision["changed_from_request"] and self.requested_tech_stack:
            print(f"  [STACK CHANGE] architect changed requested stack "
                  f"{decision['requested']} -> {chosen.get('languages')} {chosen.get('frameworks')}; "
                  f"requires user agreement")
            approved = self._wait_for_approval("architect", "2", [path])
            decision["approved_by"] = "auto" if approved else None
            decision["approved_at"] = datetime.now().isoformat() if approved else None
            save_tech_stack(self.project_dir, decision)
        # Derive per-service ports from the agreed stack (4.7).
        self._derive_ports(chosen)
        # Persist the infrastructure profile (compute/storage/network/.../vendors).
        self._finalize_infra(stage_executions)
        # Refresh the project contract now that the stack is known.
        self._write_project_agents_md()
        return decision

    _INFRA_KEYS = {"compute", "storage", "networking", "identity", "observability"}

    def _finalize_infra(self, stage_executions):
        """Parse the architect's second JSON block and persist docs/infra.json."""
        text = ""
        for ex in stage_executions:
            for a in (ex.artifacts or []):
                try:
                    with open(a, "r", encoding="utf-8", errors="ignore") as f:
                        text += f.read() + "\n"
                except Exception:
                    pass
        import re as _re
        chosen = None
        for b in _re.findall(r"```json\s*(.*?)```", text, _re.DOTALL):
            try:
                data = json.loads(b)
            except Exception:
                continue
            if isinstance(data, dict) and (set(data.keys()) & self._INFRA_KEYS):
                chosen = data
                break
        if chosen is None:
            return None
        try:
            chosen.setdefault("kind", (getattr(self, "tech_stack", {}) or {}).get("chosen", {}).get("kind", ""))
            out = os.path.join(self.project_dir, "docs", "infra.json")
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "w", encoding="utf-8") as f:
                json.dump(chosen, f, indent=2, ensure_ascii=False)
            self.infra = chosen
            print(f"  [INFRA] saved docs/infra.json (vendors={chosen.get('vendors')})")
        except Exception as e:
            print(f"  [INFRA] save failed: {e}")
        return chosen

    def _derive_ports(self, chosen: Dict):
        """Derive + persist per-service ports from the tech stack (docs/ports.json)."""
        if not chosen:
            return
        try:
            from core.port_config import derive_ports_from_tech_stack, detect_port_conflicts
            flat = {}
            for k in ("kind", "database", "cache", "deploy", "runtime"):
                v = chosen.get(k)
                if v:
                    flat[k] = v if isinstance(v, str) else " ".join(map(str, v))
            lang = chosen.get("languages") or []
            fw = chosen.get("frameworks") or []
            if lang:
                flat["languages"] = " ".join(map(str, lang))
            if fw:
                flat["frontend"] = " ".join(map(str, fw))
            allocations = derive_ports_from_tech_stack(flat, None, check_available=False) or {}
            ports = {name: {"internal": a.internal_port, "external": a.external_port,
                            "protocol": a.protocol, "reason": a.reason}
                     for name, a in allocations.items()}
            out = os.path.join(self.project_dir, "docs", "ports.json")
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "w", encoding="utf-8") as f:
                json.dump({"services": ports, "tech_stack": flat}, f, indent=2, ensure_ascii=False)
            conflicts = detect_port_conflicts(allocations) if allocations else []
            if ports:
                print(f"  [PORTS] {len(ports)} service(s) allocated"
                      + (f"; conflicts: {conflicts}" if conflicts else ""))
        except Exception as e:
            print(f"  [PORTS] skipped: {e}")

    def _stack_compliance(self):
        """Flag code that imports frameworks not present in the agreed stack."""
        ts = getattr(self, "tech_stack", {}) or {}
        chosen = ts.get("chosen") or {}
        if not chosen:
            return []
        import re
        allowed_fw = set(str(x).lower() for x in (chosen.get("frameworks") or []))
        forbidden = []
        for base in ("src", "apps", "app", "backend", "server"):
            root = os.path.join(self.project_dir, base)
            if not os.path.isdir(root):
                continue
            for dp, _d, fs in os.walk(root):
                for fn in fs:
                    if not fn.endswith(".py"):
                        continue
                    try:
                        with open(os.path.join(dp, fn), "r", encoding="utf-8", errors="ignore") as f:
                            t = f.read()
                    except Exception:
                        continue
                    for fw in ("fastapi", "flask", "django", "starlette", "tornado"):
                        if fw in allowed_fw:
                            continue
                        if re.search(r"\b(import|from)\s+" + fw + r"\b", t):
                            forbidden.append({"file": os.path.relpath(os.path.join(dp, fn), self.project_dir),
                                              "framework": fw})
        return forbidden

    def _feature_status_map(self) -> Dict[str, str]:
        """Delegates to core/orchestrator/checkpoint (1A.11)."""
        completed = self.execution.stage_executions if self.execution else {}
        return self.checkpoints.feature_status_map(completed)

    def _write_stage_checkpoints(self, stage_id, stage_executions):
        """Delegates to core/orchestrator/checkpoint (1A.11)."""
        self.checkpoints.write_stage(stage_id, stage_executions, self.execution)

    
    def check_stop_conditions(self, stage_id: str) -> tuple:
        """Check if pipeline should stop based on conditions."""
        metrics = {
            "retries": self.iteration_count,
            "tokens": self.execution.total_tokens if self.execution else 0,
            "cost_usd": self.execution.total_cost if self.execution else 0,
            "duration_seconds": 0,
            "failures": sum(
                1 for execs in (self.execution.stage_executions or {}).values()
                for e in execs if e.status == "failed"
            ) if self.execution else 0,
        }
        
        # Duration must be THIS STAGE's elapsed time (not total pipeline time), and
        # human-wait (interactive prompts / approvals) must not count as work time.
        started_iso = getattr(self, "_stage_started_at", "") or (
            self.execution.started_at if self.execution else "")
        if started_iso:
            try:
                started = datetime.fromisoformat(started_iso)
                dur = (datetime.now() - started).total_seconds()
                dur -= float(getattr(self, "_stage_human_wait_seconds", 0.0) or 0.0)
                metrics["duration_seconds"] = max(0.0, dur)
            except (ValueError, TypeError):
                pass
        
        return self.stop_conditions.check_conditions(
            self.project,
            hash(stage_id) % 100,
            metrics
        )
    
    def stop(self):
        """Request pipeline stop."""
        self._stop_requested = True
        self._write_control("stop")
    
    def pause(self):
        """Request pipeline pause."""
        self._pause_requested = True
        self._write_control("pause")
    
    def resume(self):
        """Resume paused pipeline."""
        self._pause_requested = False
        self._write_control("resume")

    def _write_control(self, action: str):
        """Signal the running pipeline (cross-process) via a control file."""
        try:
            with open(self.control_file, "w", encoding="utf-8") as f:
                json.dump({"action": action, "updated_at": datetime.now().isoformat()}, f)
        except Exception:
            pass

    def _read_control(self) -> Dict:
        try:
            if os.path.exists(self.control_file):
                with open(self.control_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _agent_control_op(self, agent_id: str) -> str:
        """Per-agent control op from control.json: pause|resume|stop|cancel (BI-0046)."""
        try:
            ops = (self._read_control() or {}).get("agents") or {}
            return str(ops.get(agent_id, "") or "").lower()
        except Exception:
            return ""

    def _clear_agent_control(self, agent_id: str):
        try:
            data = self._read_control() or {}
            ops = data.get("agents") or {}
            if agent_id in ops:
                ops.pop(agent_id, None)
                data["agents"] = ops
                data["updated_at"] = datetime.now().isoformat()
                with open(self.control_file, "w", encoding="utf-8") as f:
                    json.dump(data, f)
        except Exception:
            pass

    def _set_agent_control(self, agent_id: str, op: str):
        """Write a per-agent control op (used by the dashboard/API)."""
        try:
            data = self._read_control() or {}
            ops = data.get("agents") or {}
            if op:
                ops[agent_id] = op
            else:
                ops.pop(agent_id, None)
            data["agents"] = ops
            data["updated_at"] = datetime.now().isoformat()
            with open(self.control_file, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass

    def _reset_control(self):
        try:
            with open(self.control_file, "w", encoding="utf-8") as f:
                json.dump({"action": "run", "updated_at": datetime.now().isoformat()}, f)
        except Exception:
            pass

    def _write_run_scope(self, only_stages: Optional[List[str]] = None,
                         only_agents: Optional[List[str]] = None):
        """Persist a selective run scope so a (re)launched process honors it.

        Stamped + marked selective + bound to this process's run id so a stale scope
        from a previous/crashed run cannot silently restrict a later run.
        """
        try:
            with open(self.run_scope_file, "w", encoding="utf-8") as f:
                json.dump({
                    "selective": True,
                    "run_id": getattr(self, "run_id", "") or "",
                    "created_at": datetime.now().isoformat(),
                    "only_stages": list(only_stages or []),
                    "only_agents": list(only_agents or []),
                }, f, indent=2)
        except Exception:
            pass

    def _load_run_scope(self):
        """Apply a persisted run scope ONLY if it is selective, fresh, and unclaimed."""
        try:
            if not os.path.exists(self.run_scope_file):
                return
            with open(self.run_scope_file, "r", encoding="utf-8") as f:
                scope = json.load(f) or {}
            if not scope.get("selective"):
                self._clear_run_scope()
                return
            # Staleness guard: ignore (and drop) scopes older than RUN_SCOPE_MAX_AGE_H.
            max_age_h = float(os.getenv("RUN_SCOPE_MAX_AGE_H", "6"))
            created = scope.get("created_at", "")
            try:
                age_h = (datetime.now() - datetime.fromisoformat(created)).total_seconds() / 3600
            except Exception:
                age_h = 0.0
            if max_age_h > 0 and age_h > max_age_h:
                print(f"  [SCOPE] ignoring stale run-scope ({age_h:.1f}h old)")
                self._clear_run_scope()
                return
            if scope.get("only_stages"):
                self.only_stages = set(scope["only_stages"])
            if scope.get("only_agents"):
                self.only_agents = set(scope["only_agents"])
            print(f"  [SCOPE] only_stages={sorted(self.only_stages or [])} "
                  f"only_agents={sorted(self.only_agents or [])}")
        except Exception:
            pass

    def _clear_run_scope(self):
        try:
            if os.path.exists(self.run_scope_file):
                os.remove(self.run_scope_file)
        except Exception:
            pass

    def _show_progress(self, stage_id: str, agent_id: str, status: str):
        """Print the E2E progress banner at an agent start/end (BI-0027)."""
        try:
            from core import progress as _progress
            print("\n" + _progress.agent_banner(self.project_dir, stage_id, agent_id, status))
        except Exception:
            pass

    def _write_discovery_output(self, panel, refined_md: str = "") -> str:
        """Write artifacts/0a/discovery-output.md and derive its extra formats (BI-0144).

        Deterministic render from the saved panel; safe to call more than once (early with
        the answers, then refreshed once the refined text exists).
        """
        from core import discovery_panel as _dp
        md = _dp.render_output(panel, refined_md=refined_md)
        adir = _sp.stage_dir(self.project_dir, "0a", create=True)
        os.makedirs(adir, exist_ok=True)
        out_md = os.path.join(adir, "discovery-output.md")
        with open(out_md, "w", encoding="utf-8") as fh:
            fh.write(md)
        try:
            from core import artifact_formats as _af
            fmts = _af.formats_for(self.project, "discovery", "0a", kind="docs", content=md)
            _af.emit(self.project, out_md, fmts, content=md, agent_id="discovery")
        except Exception as fe:
            print(f"  [Discovery] format derive skipped: {fe}")
        return out_md

    def _run_design_augmentations(self, stage_id: str):
        """Wire the design-phase modules into their stages (BI-0028 / BI-0030).

        discovery questions (0a) -> product design spec (1a) -> dashboard archetype (1/2)
        -> design tokens (1c). Each writes a real artifact and is idempotent.
        """
        try:
            import json as _json
            pj = self.project_dir
            os.makedirs(os.path.join(pj, "docs"), exist_ok=True)
            idea = ""
            try:
                with open(os.path.join(pj, "project.json"), encoding="utf-8") as f:
                    idea = (_json.load(f) or {}).get("idea", "") or ""
            except Exception:
                pass

            if stage_id == "0a":
                from core import discovery_panel as _dp
                from core.discovery_engine import run_discovery, synthesize_refined_idea
                ideation = ""
                try:
                    with open(os.path.join(_sp.find_stage_dir(pj, "0"), "ideation-output.md"),
                              encoding="utf-8", errors="ignore") as _fh:
                        ideation = _fh.read()
                except Exception:
                    ideation = ""
                auto = False
                try:
                    from core.human_proxy import is_auto
                    auto = is_auto(self.project_dir)
                except Exception:
                    auto = False

                _panel_model = os.getenv("PIPELINE_PANEL_MODEL", "mimo-v2.6-flash")
                def _llm(prompt, agent_id):
                    try:
                        text, _meta = self._call_llm(prompt, agent_id, "0a", pin_model=_panel_model)
                        return text or ""
                    except Exception:
                        return ""

                # On (re)run: KEEP prior questions+answers, EXTEND the panel with any
                # newly-added agents (so their questions get asked), and ask only the
                # unanswered. Prior answers are shown for context (not silently reused).
                prior = _dp.load_panel(self.project_dir) or {}
                _dcfg = _dp.load_config(project=self.project)
                prior_agents = {g.get("agent_id") or g.get("id") for g in (prior.get("agents") or [])}
                missing = [a for a in _dcfg.get("agents", []) if a not in prior_agents]
                if prior and missing:
                    _sub = dict(_dcfg); _sub["agents"] = missing
                    _prior_qs = [q.get("question") for q in _dp.all_questions(prior) if q.get("question")]
                    add = _dp.build_panel(idea, self.project, ideation,
                                          llm_call=None if auto else _llm, config=_sub,
                                          already_asked=_prior_qs)
                    prior.setdefault("agents", []).extend(add.get("agents") or [])
                    panel = prior
                    print(f"  [Discovery] panel EXTENDED with {len(missing)} new agent(s): "
                          f"{', '.join(missing)}")
                elif prior:
                    panel = prior
                    print("  [Discovery] reusing prior panel (config adds no new agents)")
                else:
                    panel = _dp.build_panel(idea, self.project, ideation,
                                            llm_call=None if auto else _llm)
                # Re-analyze: refresh recommendations from the current context (may change).
                # OPT-IN (default off) - it is a large LLM call over all questions and can
                # stall discovery; set PIPELINE_REANALYZE=1 to enable.
                if prior and not auto and str(os.getenv("PIPELINE_REANALYZE", "0")).lower() in ("1", "true", "yes"):
                    try:
                        panel = _dp.reanalyze_recommendations(panel, idea, ideation, _llm)
                        _ch = (panel.get("reanalysis") or {}).get("changed", 0)
                        print(f"  [Discovery] re-analyzed recommendations; {_ch} changed vs prior")
                    except Exception as _re2:
                        print(f"  [Discovery] re-analysis skipped: {_re2}")
                _prev = [(q.get("question"), q.get("answer")) for q in _dp.all_questions(panel)
                         if (q.get("answer") or "").strip()]
                if _prev:
                    print(f"  [Discovery] previous answers carried forward ({len(_prev)}):")
                    for _q, _a in _prev[:8]:
                        print(f"    [prev] {' '.join((_q or '').split())[:72]} => {' '.join((_a or '').split())[:72]}")
                try:
                    panel = _dp.dedupe_questions(panel)
                    _dm = (panel.get("dedupe") or {}).get("merged", 0)
                    if _dm:
                        print(f"  [Discovery] deduped {_dm} near-duplicate question(s)")
                except Exception as _de:
                    print(f"  [Discovery] dedupe skipped: {_de}")
                answers = self._ask_panel(panel, auto=auto)
                _dp.record_answers(panel, answers)
                # BI-0037: second round - sharpen vague/overridden answers.
                try:
                    _fups = _dp.needs_followup(panel)
                    if _fups:
                        panel = _dp.build_round2(panel, llm_call=None if auto else _llm)
                        _ans2 = self._ask_panel(panel, auto=auto, only_round=2)
                        _dp.record_answers(panel, _ans2)
                        print(f"  [Discovery] round-2 follow-up: {len(_fups)} vague/overridden "
                              f"answer(s) sharpened")
                except Exception as _r2:
                    print(f"  [Discovery] round-2 skipped: {_r2}")
                _dp.recount(panel)   # totals must reflect the CURRENT (possibly extended) panel
                _dp.save_panel(self.project_dir, panel)
                print(f"  [Discovery] 360 panel: {panel['totals']['questions']} questions "
                      f"from {panel['totals']['agents']} agents; "
                      f"{panel['totals'].get('answered', 0)} answered")

                # BI-0144 hardening: write the canonical artifact as soon as the answers are
                # final, so a later synthesis failure cannot lose it (rerun cleanup removes the
                # previous one first). It is refreshed below once the refined text exists.
                try:
                    self._write_discovery_output(panel)
                    print("  [Discovery] artifact -> artifacts/0a/discovery-output.md")
                except Exception as _ae:
                    print(f"  [Discovery] artifact write failed: {_ae}")

                refined = ""
                try:
                    dis_answers = _dp.to_discovery_answers(panel)
                    run_discovery(idea, self.project, products_dir=self.products_dir,
                                  answers=dis_answers)
                    refined = synthesize_refined_idea(idea, dis_answers)
                    self._discovery_refined = refined
                    for rel in ("docs/idea-refined.md", "docs/product-plan.md"):
                        fp = os.path.join(pj, rel)
                        os.makedirs(os.path.dirname(fp), exist_ok=True)
                        with open(fp, "w", encoding="utf-8") as f:
                            f.write(refined)
                    with open(os.path.join(pj, "discovery-questions.json"),
                              "w", encoding="utf-8") as f:
                        _json.dump({"project": self.project,
                                    "total": panel["totals"]["questions"],
                                    "answered": panel["totals"].get("answered", 0),
                                    "questions": [{"agent": q.get("source_agent"),
                                                   "perspective": q.get("source_agent"),
                                                   "question": q.get("question"),
                                                   "recommendation": q.get("recommendation", ""),
                                                   "answer": q.get("answer", "")}
                                                  for q in _dp.all_questions(panel)]},
                                   f, indent=2, ensure_ascii=False)
                    print("  [Discovery] -> discovery-panel.json + docs/idea-refined.md")
                    # Refresh the artifact with the refined text (best-effort).
                    self._write_discovery_output(panel, refined_md=refined)
                except Exception as _se:
                    print(f"  [Discovery] synthesis step failed: {_se}")
            elif stage_id == "1a":
                from core.product_design_spec import (create_spec_from_artifacts, save_spec,
                                                      render_markdown)
                arts = {}
                _ideation_fp = os.path.join(_sp.find_stage_dir(pj, "0"), "ideation-output.md")
                for key, relp in (("ideation", _ideation_fp),
                                  ("discovery", "docs/domain-analysis.md"),
                                  ("design", "docs/design.md"),
                                  ("requirements", "docs/requirements.md"),
                                  ("architecture", "docs/architecture.md")):
                    fp = os.path.join(pj, relp)
                    if os.path.exists(fp):
                        with open(fp, encoding="utf-8", errors="ignore") as fh:
                            arts[key] = fh.read()
                spec = create_spec_from_artifacts(self.project, arts)
                print(f"  [DesignSpec] {save_spec(pj, spec)}")
                # Canonical stage artifact the gate references (same fix class as BI-0144):
                # artifacts/1a/product-design-spec-output.md (+ derived formats).
                try:
                    _md = render_markdown(spec)
                    _adir = _sp.stage_dir(pj, "1a", create=True)
                    os.makedirs(_adir, exist_ok=True)
                    _out = os.path.join(_adir, "product-design-spec-output.md")
                    with open(_out, "w", encoding="utf-8") as _fh:
                        _fh.write(_md)
                    try:
                        from core import artifact_formats as _af
                        _fmts = _af.formats_for(self.project, "product-design-spec", "1a",
                                                kind="spec", content=_md)
                        _af.emit(self.project, _out, _fmts, content=_md,
                                 agent_id="product-design-spec")
                    except Exception as _fe:
                        print(f"  [DesignSpec] format derive skipped: {_fe}")
                    print("  [DesignSpec] artifact -> artifacts/1a/product-design-spec-output.md")
                except Exception as _ae:
                    print(f"  [DesignSpec] artifact write failed: {_ae}")
            elif stage_id == "1c":
                from core.design_tokens import get_default_tokens, save_tokens
                print(f"  [DesignTokens] {save_tokens(pj, get_default_tokens(self.project))}")
            elif stage_id in ("1", "2"):
                from core.dashboard_archetypes import select_archetype, generate_archetype_report
                aid = select_archetype((idea or self.project)[:300], "product owner")
                report = generate_archetype_report(aid, self.project)
                with open(os.path.join(pj, "docs", "dashboard-archetype.md"),
                          "w", encoding="utf-8") as f:
                    f.write(report)
                print(f"  [Archetype] {aid} -> docs/dashboard-archetype.md")
        except Exception as e:
            print(f"  [Design:{stage_id}] {e}")

    def _run_model_fit_preflight(self):
        """Probe the selected tier's models vs agent requirements; report + apply (BI-0076).

        Default behaviour: apply the recommended model substitutions automatically if
        the human does not answer within the (short) window.
        """
        try:
            from core import model_fit
        except Exception:
            return
        try:
            cfg_all = self.model_router.load_tier_config() or {}
            prof = self.model_router.active_profile() or {}
            merged = {
                "provider": prof.get("provider") or cfg_all.get("provider", ""),
                "api_endpoint": prof.get("api_endpoint") or cfg_all.get("api_endpoint", ""),
                "models": {**(cfg_all.get("models") or {}), **(prof.get("models") or {})},
                "agents": prof.get("agents") or cfg_all.get("agents") or {},
            }
        except Exception as e:
            print(f"  [ModelFit] skipped: {e}")
            return

        def _probe(model, provider, endpoint, max_tokens):
            import time as _t
            t0 = _t.time()
            try:
                text, _meta = self.llm._call_llm_single(
                    "Reply with exactly this sentence and nothing else: "
                    "The quick brown fox jumps over the lazy dog.",
                    model, provider, endpoint,
                    session_id=f"fit-{model}", agent_id="model_probe", stage_id="preflight",
                    max_output_tokens=max_tokens, fast_fail=True)
            except Exception as e:
                return {"ok": False, "content_len": 0, "error": str(e)}
            txt = (text or "").strip()
            return {"ok": bool(txt), "content_len": len(txt),
                    "latency_ms": int((_t.time() - t0) * 1000),
                    "error": "" if txt else "empty content"}

        try:
            report = model_fit.run(merged, _probe)
        except Exception as e:
            print(f"  [ModelFit] report failed: {e}")
            return
        model_fit.save_report(self.project_dir, report)
        # Auto tier recommendation: best-fit agent->model from the model catalog (+ reasons).
        # Runs on the preflight path; logs not-good assignments but does NOT change them.
        try:
            from core import tier_builder as _tb
            _tr = ""
            try:
                _tr = (self.model_router.active_profile() or {}).get("name", "")
            except Exception:
                _tr = ""
            _recos = (_tb.build(tier=_tr).get("recommendations") or {})
            _notgood = [a for a, v in _recos.items() if not v.get("fit")]
            print(f"  [TierFit] {len(_recos)} agent(s) evaluated vs model catalog; "
                  f"{len(_notgood)} not-good" + (f": {_notgood[:6]}" if _notgood else ""))
        except Exception:
            pass
        # Multi-modal capability detection (BI-0170): which modalities the project needs, which
        # models accept them as input, and which media-OUT modalities still need a generator.
        try:
            from core import modality as _mod
            _idea = ""
            try:
                import json as _json
                _pj = os.path.join(self.project_dir, "project.json")
                _idea = (_json.load(open(_pj, encoding="utf-8")) or {}).get("idea", "")
                if not _idea:
                    for _c in ("idea.md", "idea.txt", "project-brief.md"):
                        _p = os.path.join(self.project_dir, _c)
                        if os.path.exists(_p):
                            _idea = open(_p, encoding="utf-8", errors="ignore").read()[:4000]
                            break
            except Exception:
                _idea = ""
            _caps = _mod.capabilities_for_project(_idea)
            _need = _caps.get("generators_needed") or []
            print(f"  [Modality] {_caps.get('modalities')}; generators needed: {_need or 'none'}")
        except Exception:
            pass
        s = report.get("summary", {})
        print(f"  [ModelFit] tier model/agent fit: {s.get('ok', 0)} ok, "
              f"{s.get('at_risk', 0)} at-risk, {s.get('incompatible', 0)} incompatible")
        for e in report.get("entries", []):
            if e["status"] != model_fit.STATUS_OK:
                print(f"    - {e['agent']}: {e['model']} -> {e['status']} ({e['reason']}); "
                      f"recommended: {e['recommended_action'].get('kind')} "
                      f"{e['recommended_action'].get('model')}")
        if s.get("healthy"):
            report = model_fit.apply_state(report, "keep")
            model_fit.save_report(self.project_dir, report)
            return

        # Ask (short window); default = apply the recommendation.
        answer = ""
        try:
            from core import interactive
            if interactive.enabled():
                answer = interactive.ask(
                    "Model-fit: apply the recommended model substitutions? "
                    "(answer 'keep' to keep as-is; blank = apply recommendation)",
                    default="", project_dir=self.project_dir, products_dir=self.products_dir,
                    timeout=float(os.getenv("MODEL_FIT_TIMEOUT", "300"))) or ""
        except Exception:
            pass
        report = model_fit.apply_state(report, answer)
        model_fit.save_report(self.project_dir, report)

        applied = report.get("applied") or {}
        self._model_fit_overrides = {}
        for agent_id, ch in applied.items():
            if ch.get("source") == "recommended" and ch.get("model"):
                self._model_fit_overrides[agent_id] = {"model": ch["model"]}
        if self._model_fit_overrides:
            print(f"  [ModelFit] applied substitutions for: {sorted(self._model_fit_overrides)}")
        else:
            print("  [ModelFit] no substitutions applied")

    def _ask_panel(self, panel, auto: bool = False, only_round: int = 0) -> dict:
        """Collect panel answers in ONE review file (BI-0141), not question-by-question.

        Writes every askable question (id / question / recommendation / current answer)
        to ``products/<project>/discovery-review.md``, prompts the human ONCE to review
        and edit it, then parses the answers back. A blank answer keeps the recommendation;
        the sentinel ``accept`` accepts it. Set ``PIPELINE_PANEL_ONE_BY_ONE=1`` to fall back
        to the legacy per-question loop.
        """
        try:
            from core import interactive
        except Exception:
            return {}
        if auto or not interactive.enabled():
            return {}
        from core import discovery_panel as _dp

        if str(os.getenv("PIPELINE_PANEL_ONE_BY_ONE", "0")).lower() in ("1", "true", "yes"):
            return self._ask_panel_one_by_one(panel, only_round=only_round)

        qs = _dp._askable(panel, only_round)
        if not qs:
            return {}
        review_path = os.path.join(self.project_dir, "discovery-review.md")
        try:
            _dp.emit_review_file(panel, review_path, only_round=only_round)
        except Exception as e:
            print(f"  [Discovery] review-file write failed: {e}")
            return {}
        print(f"  [Discovery] review file -> {review_path} ({len(qs)} question(s)); "
              f"edit the ANSWER blocks, or press Enter to keep current answers")
        _w0 = time.time()
        try:
            interactive.ask(
                f"Discovery review: edit '{os.path.basename(review_path)}' "
                f"(id/question/recommendation/answer for all {len(qs)} question(s)) in one place, "
                f"then press Enter to load your answers (Enter with no edits keeps current answers).",
                default="", project_dir=self.project_dir,
                products_dir=self.products_dir)
        finally:
            # Discovery/HIL answering is human time, not stage work time.
            self._stage_human_wait_seconds = float(
                getattr(self, "_stage_human_wait_seconds", 0.0)) + (time.time() - _w0)
        parsed = _dp.parse_review_file(review_path)
        valid = {q.get("id") for q in qs}
        return {k: v for k, v in parsed.items() if k in valid}

    def _ask_panel_one_by_one(self, panel, only_round: int = 0) -> dict:
        """Legacy per-question prompt loop (behind PIPELINE_PANEL_ONE_BY_ONE=1).

        EVERY question is asked (old and new): a prior answer is shown as the default
        (Enter keeps it), a recommendation is shown for new ones.
        """
        try:
            from core import interactive
        except Exception:
            return {}
        from core import discovery_panel as _dp
        answers = {}
        _w0 = time.time()
        try:
            for q in _dp.all_questions(panel):
                if q.get("skip"):          # near-duplicate merged by dedupe_questions
                    continue
                if only_round and int(q.get("round", 1)) != only_round:
                    continue
                rec = q.get("recommendation") or ""
                prev = (q.get("answer") or "").strip()
                prompt = f"[{q.get('source_agent')}] {q.get('question')}"
                if rec:
                    prompt += f"\n  recommended answer: {rec}"
                if prev:
                    prompt += f"\n  previous answer (Enter keeps it): {prev}"
                val = interactive.ask(prompt, default=prev, project_dir=self.project_dir,
                                      products_dir=self.products_dir)
                answers[q["id"]] = str(val) if (val not in (None, "")) else prev
        finally:
            # Discovery/HIL answering is human time, not stage work time.
            self._stage_human_wait_seconds = float(
                getattr(self, "_stage_human_wait_seconds", 0.0)) + (time.time() - _w0)
        return answers

    # ── live per-agent status (so the dashboard sees an agent while it runs) ──
    def _live_set(self, agent_id: str, stage_id: str, status: str = "running"):
        try:
            live = self._live_get()
            live[f"{stage_id}:{agent_id}"] = {
                "agent_id": agent_id, "stage": stage_id, "status": status,
                "at": datetime.now().isoformat(),
            }
            with open(self.live_file, "w", encoding="utf-8") as f:
                json.dump(live, f, indent=2)
        except Exception:
            pass

    def _live_clear(self, agent_id: str, stage_id: str):
        try:
            live = self._live_get()
            live.pop(f"{stage_id}:{agent_id}", None)
            with open(self.live_file, "w", encoding="utf-8") as f:
                json.dump(live, f, indent=2)
        except Exception:
            pass

    def _live_get(self) -> Dict:
        try:
            if os.path.exists(self.live_file):
                with open(self.live_file, "r", encoding="utf-8") as f:
                    return json.load(f) or {}
        except Exception:
            pass
        return {}
    

    def execute_pipeline(self) -> bool:
        try:
            from core.banner import print_banner
            print_banner(f"project={self.project} | stages={len(getattr(self.dag_executor, 'states', {}) or {})}")
        except Exception:
            pass
        """Execute the full pipeline with orchestrator controls:
        Time management, HITL approval, checkpoint/resume, parallel execution,
        budget enforcement, stop conditions, and self-monitoring."""
        if not self.dag_executor or not self.execution:
            print("[Orchestrator] No pipeline loaded")
            return False

        # Bypass guard: a project may only be executed while holding its run lock, so
        # every entry point goes through core.run_entry.begin_run (single instance +
        # run-id stamping + resume reconciliation). PIPELINE_ALLOW_UNGUARDED=1 overrides.
        if str(os.getenv("PIPELINE_ALLOW_UNGUARDED", "0")).lower() not in ("1", "true", "yes"):
            try:
                from core.lock_manager import LockManager
                _lm = LockManager(getattr(self, "products_dir", "products"))
                _info = _lm.get_lock_info(self.project)
                if _info is None:
                    print("[Orchestrator] Refused: no run lock held. Start via core.run_entry."
                          "begin_run (or scripts/run_pipeline.py). "
                          "Set PIPELINE_ALLOW_UNGUARDED=1 to override.")
                    return False
            except Exception as _ge:
                print(f"[Orchestrator] lock check skipped: {_ge}")

        try:
            from core.banner import banner as _banner
            print(_banner(f"project={self.project} | "
                          f"mode={'auto-approve' if self.auto_approve else 'interactive (HITL)'}"))
        except Exception:
            print(f"\n{'='*70}")
            print(f"ORCHESTRATOR: {self.project}")
            print(f"{'='*70}")
        print(f"Mode: {'auto-approve' if self.auto_approve else 'interactive (HITL)'}")
        print(f"Max time: {self.max_total_time}s | Parallel: {self.max_parallel_stages if self.parallel_enabled else 1}")
        
        # Initialize time tracking
        self.pipeline_start_time = time.time()
        self._reset_control()
        self._load_run_scope()
        self._write_project_agents_md()
        self._idle_loops = 0
        self.execution.phase = PipelinePhase.PLANNING
        self.execution.started_at = datetime.now().isoformat()
        if self.journal:
            try:
                self.journal.start(self.execution.pipeline_id)
            except Exception:
                pass
        self.quality_metrics.started_at = self.execution.started_at
        
        # Check for checkpoint to resume
        checkpoint = self._load_checkpoint()
        if checkpoint:
            print(f"[Orchestrator] Resuming from checkpoint: {checkpoint.get('saved_at', 'unknown')}")
            self.iteration_count = checkpoint.get("current_iteration", 0)
            self._restore_from_checkpoint(checkpoint)
            if not checkpoint.get("pipeline_complete"):
                # Interrupted/incomplete run: fresh iteration budget so the loop resumes
                # (completed stages are skipped via the restored DAG states).
                self.iteration_count = 0
        else:
            self.iteration_count = 0

        # Preflight: reconcile the selected tier's models with agent requirements
        # (probe + callout + apply recommended substitution). BI-0076.
        try:
            self._run_model_fit_preflight()
        except Exception as e:
            print(f"[ModelFit] preflight skipped: {e}")

        while self.iteration_count < self.max_iterations:
            self.iteration_count += 1

            # Cross-process control (stop/pause/resume via control.json)
            ctrl = (self._read_control().get("action") or "").lower()
            if ctrl == "stop":
                self._stop_requested = True
            elif ctrl == "resume":
                self._pause_requested = False
            elif ctrl == "pause":
                self._pause_requested = True

            # Check pause (re-read control so resume works while paused)
            while self._pause_requested and not self._stop_requested:
                time.sleep(1)
                c2 = (self._read_control().get("action") or "").lower()
                if c2 in ("resume", "stop"):
                    self._pause_requested = False
                    if c2 == "stop":
                        self._stop_requested = True
                    break
            
            # Check stop
            if self._stop_requested:
                print("[Orchestrator] Stop requested")
                self.execution.phase = PipelinePhase.FAILED
                self.execution.error = "Stop requested by user"
                self._log_decision("stop", "pipeline stopped", "user request")
                self._notify("human_required", "Pipeline stopped", "Stop requested by user", priority="high")
                break
            
            # Check time budget
            should_continue, time_reason = self._check_time_budget()
            if not should_continue:
                print(f"[Orchestrator] TIME BUDGET EXCEEDED: {time_reason}")
                self._log_decision("time_exceeded", time_reason, "dynamic timeout")
                self.execution.phase = PipelinePhase.COMPLETION
                self.execution.error = f"Time budget: {time_reason}"
                self._notify("budget_warning", "Time budget exceeded", time_reason, priority="high")
                break
            
            # Check budget conservation mode
            budget_total = self.budget_manager.get_total_usage()
            budget_used_percent = budget_total.get("used_percent", 0.0)
            self.conservation_state = apply_conservation_actions(self.conservation_state, budget_used_percent)
            
            if self.conservation_state.mode == "emergency":
                print(f"[Orchestrator] EMERGENCY MODE - Budget at {budget_used_percent:.1f}%")
                self._log_decision("emergency", f"budget at {budget_used_percent:.1f}%", "conservation mode")
                self._notify("budget_warning", "Emergency budget mode",
                             f"budget at {budget_used_percent:.1f}%", priority="critical")
                break
            
            # Get ready stages
            ready_stages = self.dag_executor.get_ready_stages()

            # "Run only selected" scope: restrict to the requested stages.
            if getattr(self, "only_stages", None):
                ready_stages = [s for s in ready_stages if s in self.only_stages]

            if not ready_stages:
                progress = self.dag_executor.get_progress()
                # Only-scope finished?
                if getattr(self, "only_stages", None):
                    terminal = {"completed", "failed", "skipped"}
                    if all(self.dag_executor.states[s].status.value in terminal
                           for s in self.only_stages if s in self.dag_executor.states):
                        print(f"[Orchestrator] Selected stage(s) finished: {sorted(self.only_stages)}")
                        break
                if progress["completed"] == progress["total"]:
                    print("[Orchestrator] All stages completed")
                    self._notify("pipeline_complete", "Pipeline completed",
                                 f"{self.project}: all stages completed")
                    break
                elif progress["failed"] > 0:
                    self.execution.phase = PipelinePhase.FAILED
                    self.execution.error = f"{progress['failed']} stages failed"
                    self._notify("agent_error", "Pipeline failed",
                                 f"{progress['failed']} stage(s) failed", priority="high")
                    break
                else:
                    # Nothing runnable and not complete = blocked (deps unmet). Avoid spinning.
                    self._idle_loops = getattr(self, "_idle_loops", 0) + 1
                    if self._idle_loops > 2:
                        blocked = [s for s in self.dag_executor.states
                                   if self.dag_executor.states[s].status.value in ("pending", "blocked", "stale")]
                        print(f"[Orchestrator] No runnable stages (blocked: {blocked}); stopping")
                        self._notify("human_required", "Pipeline blocked",
                                     f"Stages awaiting dependencies: {blocked}", priority="high")
                        # A blocked/incomplete run is NOT a completion.
                        self.execution.phase = PipelinePhase.FAILED
                        self.execution.error = f"Blocked (dependencies unmet): {blocked}"
                        break
                    continue
            
            # Execute ready stages (parallel if enabled and all are parallel-safe)
            parallel_ready = [s for s in ready_stages if self._stage_is_parallel_safe(s)]
            if (self.parallel_enabled and len(ready_stages) > 1
                    and len(parallel_ready) == len(ready_stages)):
                # Run independent stages in parallel
                self._execute_stages_parallel(ready_stages)
            else:
                # Run stages sequentially
                for stage_id in ready_stages:
                    self._execute_stage_sequential(stage_id)
            
            # Save checkpoint after each iteration
            self._save_checkpoint()
            
            if self.execution.phase == PipelinePhase.FAILED:
                break
        
        # Finalize execution. Only a genuinely completed run is marked complete;
        # a stopped/failed run must NOT look "complete" (else `continue` skips it).
        if self.execution.phase != PipelinePhase.FAILED:
            self.execution.completed_at = datetime.now().isoformat()
            self.quality_metrics.completed_at = self.execution.completed_at
            self.execution.phase = PipelinePhase.COMPLETION
        
        # Log final time stats
        total_duration = time.time() - self.pipeline_start_time
        self._log_decision("pipeline_complete", f"total duration: {total_duration:.1f}s", "final")
        
        # Collect all artifacts
        for stage_id, executions in self.execution.stage_executions.items():
            for execution in executions:
                self.execution.artifacts_generated.extend(execution.artifacts)
        
        # Get memory stats
        self.execution.memory_stats = self.memory.get_stats()
        
        # Calculate quality metrics
        self._calculate_quality_metrics()
        
        # Validate project state files against schemas (PART 6)
        try:
            self._schema_validation = self._validate_state_schemas()
        except Exception:
            self._schema_validation = {}
        # Generate final report
        self._generate_final_report()
        # Persist the knowledge graph if enabled (BI-0054: was in-memory only).
        try:
            if getattr(self, "knowledge_graph", None):
                self.knowledge_graph.save()
        except Exception:
            pass
        # Persist final state (so pipeline_complete/completed_at are written).
        try:
            self._save_checkpoint()
        except Exception:
            pass
        # BI-0184: item/amend runs enforce the repo quality gate; e2e runs skip it.
        try:
            from core import run_quality_gate as _qg
            _mode = ("item" if (getattr(self, "only_stages", None)
                                or getattr(self, "only_agents", None)) else "e2e")
            _qg.gate_if_item_run(self.project_dir, _mode)
        except Exception as _qe:
            print(f"  [QualityGate] skipped: {_qe}")
        # Selective run scope is one-shot
        self._clear_run_scope()

        # Finalize live journal / project state
        if self.journal:
            try:
                self.journal.finish(self.execution.phase.value)
                self.journal.write_status(self.execution)
            except Exception:
                pass
        
        # Save issue lists
        self._save_issues()
        
        # Save quality metrics
        save_quality_metrics(self.quality_metrics, self.products_dir)
        
        # Extract cross-project learning
        try:
            build_learning_index(self.products_dir)
        except Exception:
            pass
        
        # Print summary
        self._print_summary()
        
        return self.execution.phase == PipelinePhase.COMPLETION
    
    
    def _calculate_quality_metrics(self):
        """Calculate quality metrics from pipeline execution."""
        if not self.execution:
            return
        
        # Calculate basic metrics
        total_cost = self.execution.total_cost
        total_tokens = self.execution.total_tokens
        
        # Calculate quality score based on compliance and issues
        total_agents = sum(len(execs) for execs in self.execution.stage_executions.values())
        passed_agents = sum(
            1 for execs in self.execution.stage_executions.values()
            for e in execs if e.compliance_passed
        )
        compliance_rate = (passed_agents / total_agents * 100) if total_agents > 0 else 0
        
        # Count issues
        critical_issues = self.security_issues.critical_count + self.nfr_issues.critical_count + self.test_issues.critical_count
        high_issues = self.security_issues.high_count + self.nfr_issues.high_count + self.test_issues.high_count
        
        # Calculate quality score (0-100)
        quality_score = compliance_rate
        quality_score -= critical_issues * 10  # -10 per critical issue
        quality_score -= high_issues * 5  # -5 per high issue
        quality_score = max(0, min(100, quality_score))
        
        # Update quality metrics
        self.quality_metrics.total_tokens = total_tokens
        self.quality_metrics.total_cost = total_cost
        self.quality_metrics.input_tokens_per_product = total_tokens
        self.quality_metrics.output_tokens_per_product = total_tokens // 2
        self.quality_metrics.cost_per_product = total_cost
        self.quality_metrics.quality_score = quality_score
        self.quality_metrics.design_quality = compliance_rate
        self.quality_metrics.code_quality = compliance_rate
        self.quality_metrics.test_coverage = compliance_rate
        self.quality_metrics.security_score = max(0, 100 - critical_issues * 20 - high_issues * 10)
        self.quality_metrics.nfr_compliance = compliance_rate
        self.quality_metrics.budget_utilization = (total_cost / 100.0) * 100  # Assuming $100 budget
    
    def _save_issues(self):
        """Save all issue lists to files, then fold them into the defect store (U2/B3)."""
        try:
            save_issue_list(self.security_issues, self.products_dir)
            save_issue_list(self.nfr_issues, self.products_dir)
            save_issue_list(self.test_issues, self.products_dir)
        except Exception as e:
            print(f"[PipelineExecutor] Error saving issues: {e}")
        try:
            from core.defect_loop import route_stage_issues
            for kind, issues in (("security", self.security_issues),
                                 ("nfr", self.nfr_issues),
                                 ("tests", self.test_issues)):
                # IssueList is a wrapper; route its underlying items.
                items = getattr(issues, "issues", issues) or []
                route_stage_issues(self.project, kind, items)
        except Exception as e:
            print(f"[PipelineExecutor] issue->defect routing skipped: {e}")
    
    def _generate_final_report(self):
        """Delegates to core/orchestrator/reporting (1A.11)."""
        self._reporter().generate_final_report()

    def _reporter(self):
        from core.orchestrator.reporting import Reporter
        return Reporter(
            self.execution, self.project_dir,
            pipeline_start_time=self.pipeline_start_time,
            iteration_count=self.iteration_count,
            stage_timings=self.stage_timings,
            agent_timings=self.agent_timings,
            delegations=self.delegations,
            conservation_state=self.conservation_state,
            quality_metrics=self.quality_metrics,
            security_issues=self.security_issues,
            nfr_issues=self.nfr_issues,
            test_issues=self.test_issues,
            budget_manager=self.budget_manager,
            audit_log=self.audit_log,
            cost_kpi=(self.cost_kpi.calculate_cps(project=self.project)
                      if getattr(self, "cost_kpi", None) else None),
            feature_health=(self.feature_tracker.health()
                            if getattr(self, "feature_tracker", None) else None),
            nfr_coverage=self._nfr_coverage(),
            schema_validation=getattr(self, "_schema_validation", None),
            post_deploy=getattr(self, "_post_deploy", None),
        )

    def _print_summary(self):
        """Delegates to core/orchestrator/reporting (1A.11)."""
        self._reporter().print_summary()

    def get_status(self) -> Dict:
        """Standardized phase/stage/agent status (see core/orchestrator/status.py)."""
        if not self.execution:
            return {"status": "no_pipeline_loaded"}
        from core.orchestrator.status import build_report
        agent_deps = {}
        stage_agents = {}
        try:
            for sid, s in (self.pipeline_def.get("stages", {}) or {}).items():
                ad = s.get("agent_dependencies")
                if ad:
                    agent_deps[sid] = ad
                flow = s.get("ideal_flow")
                if flow:
                    stage_agents[sid] = list(flow)
        except Exception:
            pass
        report = build_report(self.dag_executor, self.execution, agent_deps, stage_agents)
        # Merge live (in-flight) agents so the dashboard sees them as running.
        try:
            live = self._live_get()
            for key, info in live.items():
                sid = info.get("stage", "")
                aid = info.get("agent_id", "")
                st = report["stages"].get(sid)
                if not st:
                    continue
                found = False
                for a in st.get("agents", []):
                    if a.get("agent_id") == aid:
                        a["status"] = "running"
                        found = True
                if not found:
                    st.setdefault("agents", []).append(
                        {"agent_id": aid, "status": "running", "model": "", "provider": "",
                         "tokens": 0, "compliance_passed": False, "unmet_dependencies": [],
                         "error": "", "started_at": info.get("at", ""), "completed_at": ""})
        except Exception:
            pass
        report.update({
            "pipeline_id": self.execution.pipeline_id,
            "project": self.execution.project,
            "progress": self.dag_executor.get_progress() if self.dag_executor else {},
            "memory_stats": self.memory.get_stats(),
        })
        return report


# Convenience function
def execute_pipeline(project: str, pipeline_file: str, products_dir: str = "products") -> bool:
    """Execute a pipeline for a project."""
    executor = PipelineExecutor(products_dir=products_dir, project=project)
    
    if not executor.load_pipeline(pipeline_file):
        return False
    
    return executor.execute_pipeline()


if __name__ == "__main__":
    # Test the executor
    import argparse
    
    parser = argparse.ArgumentParser(description="Pipeline Execution Engine")
    parser.add_argument("--project", default="test-pipeline", help="Project name")
    parser.add_argument("--pipeline", default="pipeline-definition.json", help="Pipeline definition file")
    parser.add_argument("--products-dir", default="products", help="Products directory")
    
    args = parser.parse_args()
    
    success = execute_pipeline(args.project, args.pipeline, args.products_dir)
    sys.exit(0 if success else 1)
