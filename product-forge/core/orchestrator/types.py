"""Core orchestration types (extracted from pipeline_executor - 1A.11)."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class PipelinePhase(Enum):
    """Pipeline execution phases."""
    INIT = "init"
    PLANNING = "planning"
    EXECUTION = "execution"
    PAUSED = "paused"  # Waiting for human approval
    VERIFICATION = "verification"
    COMPLETION = "completion"
    FAILED = "failed"


@dataclass
class AgentExecution:
    """Result of executing a single agent."""
    agent_id: str
    stage_id: str
    status: str  # pending, running, completed, failed
    started_at: str = ""
    completed_at: str = ""
    artifacts: List[str] = field(default_factory=list)
    knowledge_used: List[str] = field(default_factory=list)
    reasoning_used: str = ""
    compliance_passed: bool = False
    compliance_report: Dict = field(default_factory=dict)
    error: str = ""
    tokens_used: int = 0
    cost: float = 0.0
    # Detailed token usage per agent
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0
    selected_model: str = ""
    selected_provider: str = ""
    model_cost_per_1k_input: float = 0.0
    model_cost_per_1k_output: float = 0.0
    context_tokens: int = 0
    # Audit fields
    model_context_window: int = 0
    prompt_chars: int = 0
    output_chars: int = 0
    artifacts_used: List[Dict] = field(default_factory=list)
    chunking_used: bool = False
    chunks_count: int = 0
    cache_hit: bool = False
    duration_ms: int = 0
    # Telemetry / health
    finish_reason: str = ""
    truncated: bool = False
    retries: int = 0
    compaction_used: bool = False
    compaction_saved_chars: int = 0
    continuations: int = 0


@dataclass
class PipelineExecution:
    """Full pipeline execution state."""
    pipeline_id: str
    project: str
    pipeline_file: str
    phase: PipelinePhase
    started_at: str
    completed_at: str = ""
    stage_executions: Dict[str, List[AgentExecution]] = field(default_factory=dict)
    current_stage: str = ""
    artifacts_generated: List[str] = field(default_factory=list)
    compliance_summary: Dict = field(default_factory=dict)
    memory_stats: Dict = field(default_factory=dict)
    total_tokens: int = 0
    total_cost: float = 0.0
    error: str = ""
