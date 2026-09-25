"""
Product Forge Core Module
Multi-project orchestration, locking, state management, security,
version control, release management, logging, skills registry,
presentation generation, customer onboarding, marketing,
cost modeling, change registry, maintenance, FinOps,
domain research, BYOT integration, video generation,
product ingestion, model recommendation, product analyzer,
workflow documentation, PDF generation, agent memory system,
knowledge routing, knowledge compilation, skill contracts,
agent runtime, DAG execution, reasoning skills, pipeline engine,
discovery engine, dashboard archetypes, budget conservation,
quality metrics, and issue tracking
"""

__version__ = "3.0.0"
__author__ = "Product Forge Team"
__product_name__ = "Product Forge"
__product_tagline__ = "Multi-Agent Multi-Project System"

# Infrastructure
from .lock_manager import LockManager
from .state_machine import StateMachine, ProjectState
from .write_safety import WriteSafety
from .queue_manager import QueueManager
from .budget_tracker import BudgetTracker
from .git_manager import GitManager
from .product_plan import ProductPlan
from .traceability import TraceabilityMatrix
from .agent_ledger import AgentLedger
from .version_manager import VersionManager, VersionManifest
from .release_manager import ReleaseManager, ArtifactDescriptor, DeployTicket, ResourceFootprint
from .logging_manager import ProductLogger, PipelineLogger
from .cross_review import CrossReviewManager, ReviewRequest, ReviewFeedback
from .skills_registry import SkillsRegistry, Skill, MCPServer, ModelRecommendation
from .presentation_generator import PresentationGenerator, VideoGenerator, MarketingGenerator, PresentationConfig, Slide
from .customer_onboarding import OnboardingGenerator
from .cost_modeling import CostModeler, CloudCostEstimate, InfrastructureCost
from .change_registry import ChangeRegistry, ChangeRequest, ImpactAnalysis
from .maintenance import MaintenanceManager, Issue, Patch, HealthCheck
from .finops import FinOpsManager, CostItem, Budget, OptimizationRecommendation
from .domain_research import DomainResearchEngine, DomainTrend, BestPractice, ResearchSource
from .byot_integration import BYOTIntegrationManager, CustomModel, CustomMCPServer, CustomTool
from .video_generation import VideoGenerationEngine, VideoScene, VideoConfig
from .product_ingestion import ProductIngester, IngestionSource, IngestionResult
from .model_recommendation import ModelRecommendationEngine, ModelSpec, TaskRequirements
from .product_analyzer import (
    ProductAnalyzer, AnalysisReport, StructureAnalysis, CodeQualityMetrics,
    TestCoverageAnalysis, SecurityFinding, GapAnalysis, AgentWorkItem,
    Recommendation, UserQuestion
)
from .workflow_docs import WorkflowDocumentationGenerator, WorkflowStep, AgentWorkflow
from .pdf_generator import PDFGenerator

# Core AI/Agent modules
from .knowledge_router import KnowledgeRouter
from .agent_memory import AgentMemory, MemoryType, MemoryEntry, MemoryQuery, CompiledKnowledge, create_agent_memory
from .knowledge_compiler import KnowledgeCompiler, Concept, Relationship, CompiledKnowledge as CompiledKnowledgeKB
from .skill_contracts import SkillContractRegistry, SkillContract, SkillInput, SkillOutput
from .agent_runtime import AgentRuntime, AgentState, AgentContext, ExecutionResult
from .dag_executor import DAGExecutor, StageDefinition, StageState, StageType, StageStatus
from .reasoning_skills import ReasoningSkills, ReasoningOutput
from .context_manager import build_context_package, get_contract, check_budget as ctx_check_budget
from .squad_manager import SquadManager, Squad, AgentCapability
from .artifact_store import ArtifactMeta, StageArtifacts, ProjectArtifacts, scan_project_artifacts, get_artifact_summary, create_or_update_artifact
from .design_critic import CritiqueResult, critique_design, critique_to_dict
from .visual_qa import QAResult, run_visual_qa, qa_to_dict
from .forge_constitution import Constitution, get_default_constitution, check_quality_gate, constitution_to_dict
from .design_tokens import DesignTokenSet, get_default_tokens, tokens_to_css_custom_properties, tokens_to_dict, save_tokens
from .product_design_spec import DesignSpec, create_spec_from_artifacts, spec_to_dict, save_spec, load_spec
from .forced_convergence import ConvergenceState, check_convergence, force_complete_stage, skip_stage, auto_resolve, convergence_to_dict
from .cross_project_learning import LearningState, ProjectInsight, ProjectSummary, build_learning_index, get_relevant_insights, suggest_for_project, learning_to_dict
from .model_registry import ModelCapabilityRegistry
from .circuit_breaker import CircuitBreakerRegistry

# Newly added modules
from .discovery_engine import run_discovery, discovery_to_dict, DiscoveryResult, DiscoveryQuestion, DiscoveryAnswer
from .dashboard_archetypes import select_archetype, get_archetype, archetype_to_dict, list_archetypes, generate_archetype_report
from .budget_conservation import create_conservation_state, apply_conservation_actions, should_skip_agent, conservation_state_to_dict, ConservationState
from .quality_metrics import QualityMetrics, calculate_quality_score, save_quality_metrics, load_quality_metrics, generate_quality_report
from .issue_tracker import create_issue_list, add_issue, save_issue_list, load_issue_list, generate_issue_report, prioritize_issues, Issue, IssueList

__all__ = [
    # Infrastructure
    "LockManager",
    "StateMachine",
    "ProjectState",
    "WriteSafety",
    "QueueManager",
    "BudgetTracker",
    "GitManager",
    "ProductPlan",
    "TraceabilityMatrix",
    "AgentLedger",
    "VersionManager",
    "VersionManifest",
    "ReleaseManager",
    "ArtifactDescriptor",
    "DeployTicket",
    "ResourceFootprint",
    "ProductLogger",
    "PipelineLogger",
    "CrossReviewManager",
    "ReviewRequest",
    "ReviewFeedback",
    "SkillsRegistry",
    "Skill",
    "MCPServer",
    "ModelRecommendation",
    "PresentationGenerator",
    "VideoGenerator",
    "MarketingGenerator",
    "PresentationConfig",
    "Slide",
    "OnboardingGenerator",
    "CostModeler",
    "CloudCostEstimate",
    "InfrastructureCost",
    "ChangeRegistry",
    "ChangeRequest",
    "ImpactAnalysis",
    "MaintenanceManager",
    "Issue",
    "Patch",
    "HealthCheck",
    "FinOpsManager",
    "CostItem",
    "Budget",
    "OptimizationRecommendation",
    "DomainResearchEngine",
    "DomainTrend",
    "BestPractice",
    "ResearchSource",
    "BYOTIntegrationManager",
    "CustomModel",
    "CustomMCPServer",
    "CustomTool",
    "VideoGenerationEngine",
    "VideoScene",
    "VideoConfig",
    "ProductIngester",
    "IngestionSource",
    "IngestionResult",
    "ModelRecommendationEngine",
    "ModelSpec",
    "TaskRequirements",
    "ProductAnalyzer",
    "AnalysisReport",
    "StructureAnalysis",
    "CodeQualityMetrics",
    "TestCoverageAnalysis",
    "SecurityFinding",
    "GapAnalysis",
    "AgentWorkItem",
    "Recommendation",
    "UserQuestion",
    "WorkflowDocumentationGenerator",
    "WorkflowStep",
    "AgentWorkflow",
    "PDFGenerator",
    # Core AI/Agent modules
    "KnowledgeRouter",
    "AgentMemory",
    "MemoryType",
    "MemoryEntry",
    "MemoryQuery",
    "CompiledKnowledge",
    "create_agent_memory",
    "KnowledgeCompiler",
    "Concept",
    "Relationship",
    "CompiledKnowledgeKB",
    "SkillContractRegistry",
    "SkillContract",
    "SkillInput",
    "SkillOutput",
    "AgentRuntime",
    "AgentState",
    "AgentContext",
    "ExecutionResult",
    "DAGExecutor",
    "StageDefinition",
    "StageState",
    "StageType",
    "StageStatus",
    "ReasoningSkills",
    "ReasoningOutput",
    "ArtifactMeta", "StageArtifacts", "ProjectArtifacts", "scan_project_artifacts", "get_artifact_summary", "create_or_update_artifact",
    "CritiqueResult", "critique_design", "critique_to_dict",
    "QAResult", "run_visual_qa", "qa_to_dict",
    "Constitution", "get_default_constitution", "check_quality_gate", "constitution_to_dict",
    "DesignTokenSet", "get_default_tokens", "tokens_to_css_custom_properties", "tokens_to_dict", "save_tokens",
    "DesignSpec", "create_spec_from_artifacts", "spec_to_dict", "save_spec", "load_spec",
    "ConvergenceState", "check_convergence", "force_complete_stage", "skip_stage", "auto_resolve", "convergence_to_dict",
    "LearningState", "ProjectInsight", "ProjectSummary", "build_learning_index", "get_relevant_insights", "suggest_for_project", "learning_to_dict",
    "ModelRegistry", "select_model_for_agent",
    "CircuitBreakerRegistry",
    # Newly added modules
    "run_discovery", "discovery_to_dict", "DiscoveryResult", "DiscoveryQuestion", "DiscoveryAnswer",
    "select_archetype", "get_archetype", "archetype_to_dict", "list_archetypes", "generate_archetype_report",
    "create_conservation_state", "apply_conservation_actions", "should_skip_agent", "conservation_state_to_dict", "ConservationState",
    "QualityMetrics", "calculate_quality_score", "save_quality_metrics", "load_quality_metrics", "generate_quality_report",
    "create_issue_list", "add_issue", "save_issue_list", "load_issue_list", "generate_issue_report", "prioritize_issues", "Issue", "IssueList",
]
