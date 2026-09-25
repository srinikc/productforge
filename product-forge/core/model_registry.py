"""
Model Capability Registry - Phase 1.1

Capability-based model registry with skill-based selection, fallback chains,
and automatic tier-based selection.

Phase 1.1 (CRITICAL): Model Capability Registry - the foundation for intelligent
model selection across all agent operations.

Cost data source: OpenCode Go pricing page (https://opencode.ai/docs/go/),
fetched 2026-09-22. Go is a $10/mo subscription with per-model monthly limits
(5h=20%, wk=50%, mo=100%). DeepSeek models are peak/off-peak (peak 01-04 &
06-10 UTC Mon-Fri); the cost_per_1k_* fields below store the OFF-PEAK rate.
Provider openrouter rates fetched 2026-09-22.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field, asdict
from enum import Enum


class ModelTier(str, Enum):
    """Cost/quality tiers for model selection."""
    PREMIUM = "premium"          # Best quality, highest cost
    RECOMMENDED = "recommended"  # Good balance
    HYBRID = "hybrid"            # Mix of premium + cheap
    CHEAP = "cheap"              # Budget optimized
    OPENCODE_GO_CHEAP = "opencode-go-cheap"  # OpenCode Go budget tier
    OPENCODE_GO_REC = "opencode-go-rec"       # OpenCode Go recommended tier
    ZENFREE = "zenfree"          # OpenCode Zen free
    OROUTERFREE = "orouterfree"  # OpenRouter free
    EDUCATION = "education"      # Free education tier


@dataclass
class ModelCapability:
    """A specific capability that a model can perform."""
    name: str                      # e.g., "code_generation"
    description: str
    quality_score: float           # 0.0-1.0
    examples: list[str] = field(default_factory=list)


@dataclass
class ModelProfile:
    """Complete profile of a model."""
    name: str
    provider: str
    tier: str
    cost_per_1k_input: float
    cost_per_1k_output: float
    context_window: int
    quality_score: float
    speed_score: float             # 0.0-1.0
    capabilities: list[str]        # e.g., ["code", "analysis", "vision"]
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    use_cases: list[str] = field(default_factory=list)
    enabled: bool = True
    rate_limit_rpm: int = 0        # Requests per minute (0 = unlimited)
    rate_limit_tpm: int = 0        # Tokens per minute


class ModelCapabilityRegistry:
    """
    Registry for model capabilities with intelligent selection.
    
    Phase 1.1: Enables capability-based model selection, fallback chains,
    and cost-aware routing.
    """
    
    REGISTRY_FILE = "model_registry.json"
    
    DEFAULT_MODELS = [
        # Premium tier
        ModelProfile(
            name="gpt-4-turbo",
            provider="openai",
            tier=ModelTier.PREMIUM.value,
            cost_per_1k_input=0.01,
            cost_per_1k_output=0.03,
            context_window=128000,
            quality_score=0.95,
            speed_score=0.70,
            capabilities=["code", "analysis", "reasoning", "vision", "long_context"],
            strengths=["High quality code", "Long context", "Versatile"],
            weaknesses=["Expensive"],
            use_cases=["Complex code", "Architecture", "Long documents"],
        ),
        ModelProfile(
            name="claude-3-opus",
            provider="anthropic",
            tier=ModelTier.PREMIUM.value,
            cost_per_1k_input=0.015,
            cost_per_1k_output=0.075,
            context_window=200000,
            quality_score=0.97,
            speed_score=0.55,
            capabilities=["code", "analysis", "reasoning", "long_context", "writing"],
            strengths=["Highest quality", "Longest context", "Excellent reasoning"],
            weaknesses=["Slowest", "Most expensive"],
            use_cases=["Architecture", "Complex reasoning", "Critical analysis"],
        ),
        # Recommended tier
        ModelProfile(
            name="gpt-4o",
            provider="openai",
            tier=ModelTier.RECOMMENDED.value,
            cost_per_1k_input=0.005,
            cost_per_1k_output=0.015,
            context_window=128000,
            quality_score=0.90,
            speed_score=0.85,
            capabilities=["code", "analysis", "reasoning", "vision"],
            strengths=["Fast", "High quality", "Multimodal"],
            weaknesses=["Newer, less battle-tested"],
            use_cases=["Code generation", "Analysis", "General tasks"],
        ),
        ModelProfile(
            name="claude-3-sonnet",
            provider="anthropic",
            tier=ModelTier.RECOMMENDED.value,
            cost_per_1k_input=0.003,
            cost_per_1k_output=0.015,
            context_window=200000,
            quality_score=0.88,
            speed_score=0.75,
            capabilities=["code", "analysis", "reasoning", "long_context", "writing"],
            strengths=["Long context", "Good code", "Fast for tier"],
            weaknesses=["Cost"],
            use_cases=["Code review", "Documentation", "Analysis"],
        ),
        # Cheap tier
        ModelProfile(
            name="gpt-3.5-turbo",
            provider="openai",
            tier=ModelTier.CHEAP.value,
            cost_per_1k_input=0.0005,
            cost_per_1k_output=0.0015,
            context_window=16000,
            quality_score=0.75,
            speed_score=0.95,
            capabilities=["code", "analysis", "chat"],
            strengths=["Very fast", "Very cheap", "Reliable"],
            weaknesses=["Shorter context", "Lower quality"],
            use_cases=["Simple tasks", "High volume", "Validation"],
        ),
        ModelProfile(
            name="claude-3-haiku",
            provider="anthropic",
            tier=ModelTier.CHEAP.value,
            cost_per_1k_input=0.00025,
            cost_per_1k_output=0.00125,
            context_window=200000,
            quality_score=0.78,
            speed_score=0.92,
            capabilities=["code", "analysis", "chat", "long_context"],
            strengths=["Very fast", "Cheap", "Long context"],
            weaknesses=["Lower quality than sonnet"],
            use_cases=["High volume", "Validation", "Quick analysis"],
        ),
        # Free tier
        ModelProfile(
            name="mimo",
            provider="opencode-zen",
            tier=ModelTier.ZENFREE.value,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            context_window=32000,
            quality_score=0.70,
            speed_score=0.80,
            capabilities=["code", "chat", "analysis"],
            strengths=["Free", "Fast", "Decent quality"],
            weaknesses=["Rate limited", "Lower quality"],
            use_cases=["Free tier", "Testing", "Non-critical tasks"],
            rate_limit_rpm=60,
        ),
        ModelProfile(
            name="gemini-flash",
            provider="openrouter",
            tier=ModelTier.OROUTERFREE.value,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            context_window=32000,
            quality_score=0.72,
            speed_score=0.85,
            capabilities=["code", "analysis", "vision"],
            strengths=["Free", "Fast", "Multimodal"],
            weaknesses=["Rate limited"],
            use_cases=["Free tier", "Testing"],
            rate_limit_rpm=20,
        ),
        # OpenCode Go - Cheap Tier
        ModelProfile(
            name="mimo-v2.5",
            provider="opencode-go",
            tier=ModelTier.OPENCODE_GO_CHEAP.value,
            cost_per_1k_input=0.00014,
            cost_per_1k_output=0.00028,
            context_window=1000000,
            quality_score=0.75,
            speed_score=0.90,
            capabilities=["code", "analysis", "chat"],
            strengths=["Very cheap", "Fast", "Good analysis"],
            weaknesses=["Lower quality than premium"],
            use_cases=["High volume", "Simple tasks", "Analysis"],
        ),
        ModelProfile(
            name="deepseek-v4-flash",
            provider="opencode-go",
            tier=ModelTier.OPENCODE_GO_CHEAP.value,
            cost_per_1k_input=0.00015,
            cost_per_1k_output=0.0006,
            context_window=1000000,
            quality_score=0.78,
            speed_score=0.88,
            capabilities=["code", "analysis", "reasoning"],
            strengths=["Fast", "Good code", "Cheap"],
            weaknesses=["Lower quality than pro"],
            use_cases=["General tasks", "Code generation", "Analysis"],
        ),
        ModelProfile(
            name="qwen3.8-flash",
            provider="opencode-go",
            tier=ModelTier.OPENCODE_GO_CHEAP.value,
            cost_per_1k_input=0.00015,
            cost_per_1k_output=0.00047,
            context_window=1000000,
            quality_score=0.76,
            speed_score=0.92,
            capabilities=["code", "analysis", "reasoning"],
            strengths=["Very fast", "Cheap", "Good code"],
            weaknesses=["Lower quality"],
            use_cases=["Fast tasks", "Code generation"],
        ),
        ModelProfile(
            name="mimo-v2.5-pro",
            provider="opencode-go",
            tier=ModelTier.OPENCODE_GO_CHEAP.value,
            cost_per_1k_input=0.00043,
            cost_per_1k_output=0.00087,
            context_window=1000000,
            quality_score=0.80,
            speed_score=0.85,
            capabilities=["code", "analysis", "reasoning"],
            strengths=["Better than v2.5", "Good planning"],
            weaknesses=["More expensive than v2.5"],
            use_cases=["Planning", "Architecture", "Complex analysis"],
        ),
        ModelProfile(
            name="minimax-m3",
            provider="opencode-go",
            tier=ModelTier.OPENCODE_GO_CHEAP.value,
            cost_per_1k_input=0.00030,
            cost_per_1k_output=0.00120,
            context_window=1000000,
            quality_score=0.77,
            speed_score=0.87,
            capabilities=["code", "analysis", "writing"],
            strengths=["Good code", "Good writing", "Cheap"],
            weaknesses=["Less known"],
            use_cases=["Code generation", "Documentation"],
        ),
        ModelProfile(
            name="hy3",
            provider="opencode-go",
            tier=ModelTier.OPENCODE_GO_CHEAP.value,
            cost_per_1k_input=0.00014,
            cost_per_1k_output=0.00058,
            context_window=256000,
            quality_score=0.74,
            speed_score=0.89,
            capabilities=["code", "analysis"],
            strengths=["Very cheap", "Fast"],
            weaknesses=["Smaller context"],
            use_cases=["High volume", "Simple tasks"],
        ),
        # OpenCode Go - Recommended Tier
        ModelProfile(
            name="gpt-5.6-luna",
            provider="opencode-go",
            tier=ModelTier.OPENCODE_GO_REC.value,
            cost_per_1k_input=0.00020,
            cost_per_1k_output=0.00120,
            context_window=1050000,
            quality_score=0.88,
            speed_score=0.82,
            capabilities=["code", "analysis", "reasoning", "writing"],
            strengths=["Best reasoning", "Good code", "Long context"],
            weaknesses=["More expensive"],
            use_cases=["Complex reasoning", "Architecture", "Documentation"],
        ),
        ModelProfile(
            name="deepseek-v4-pro",
            provider="opencode-go",
            tier=ModelTier.OPENCODE_GO_REC.value,
            cost_per_1k_input=0.00066,
            cost_per_1k_output=0.00198,
            context_window=1000000,
            quality_score=0.85,
            speed_score=0.80,
            capabilities=["code", "analysis", "reasoning"],
            strengths=["Strong code", "Good analysis"],
            weaknesses=["More expensive"],
            use_cases=["Code review", "Architecture", "Complex tasks"],
        ),
        ModelProfile(
            name="kimi-k2.7-code",
            provider="opencode-go",
            tier=ModelTier.OPENCODE_GO_REC.value,
            cost_per_1k_input=0.00095,
            cost_per_1k_output=0.00400,
            context_window=262144,
            quality_score=0.90,
            speed_score=0.78,
            capabilities=["code", "analysis", "reasoning"],
            strengths=["Best code generation", "Strong reasoning"],
            weaknesses=["Most expensive in tier"],
            use_cases=["Code generation", "Complex implementation"],
        ),
        ModelProfile(
            name="qwen3.7-plus",
            provider="opencode-go",
            tier=ModelTier.OPENCODE_GO_REC.value,
            cost_per_1k_input=0.00040,
            cost_per_1k_output=0.00160,
            context_window=1000000,
            quality_score=0.83,
            speed_score=0.84,
            capabilities=["code", "analysis", "reasoning", "writing"],
            strengths=["Good general", "Long context"],
            weaknesses=["Less specialized"],
            use_cases=["General tasks", "Analysis", "Documentation"],
        ),
        ModelProfile(
            name="qwen3.6-plus",
            provider="opencode-go",
            tier=ModelTier.OPENCODE_GO_REC.value,
            cost_per_1k_input=0.00050,
            cost_per_1k_output=0.00300,
            context_window=1000000,
            quality_score=0.82,
            speed_score=0.83,
            capabilities=["code", "analysis", "reasoning"],
            strengths=["Good quality", "Long context"],
            weaknesses=["More expensive than 3.7-plus"],
            use_cases=["General tasks", "Analysis"],
        ),
        ModelProfile(
            name="qwen3.8-max",
            provider="opencode-go",
            tier=ModelTier.OPENCODE_GO_REC.value,
            cost_per_1k_input=0.00200,
            cost_per_1k_output=0.00600,
            context_window=1000000,
            quality_score=0.87,
            speed_score=0.80,
            capabilities=["code", "analysis", "reasoning", "writing"],
            strengths=["Best quality in tier", "Long context"],
            weaknesses=["Most expensive"],
            use_cases=["Complex tasks", "Architecture", "Critical analysis"],
        ),
        ModelProfile(
            name="grok-4.5",
            provider="opencode-go",
            tier=ModelTier.OPENCODE_GO_REC.value,
            cost_per_1k_input=0.00200,
            cost_per_1k_output=0.00600,
            context_window=500000,
            quality_score=0.89,
            speed_score=0.79,
            capabilities=["code", "analysis", "reasoning", "vision"],
            strengths=["Best reasoning", "Multimodal"],
            weaknesses=["Most expensive", "Smaller context"],
            use_cases=["Complex reasoning", "Vision tasks"],
        ),
        # --- provider-specific models (OpenCode Go / OpenRouter) ---
        ModelProfile(
            name="mimo-v2.6-flash",
            provider="opencode-go",
            tier=ModelTier.OPENCODE_GO_CHEAP.value,
            cost_per_1k_input=0.00014,
            cost_per_1k_output=0.00028,
            context_window=1000000,
            quality_score=0.76,
            speed_score=0.92,
            capabilities=["code", "analysis", "chat"],
            strengths=["OpenCode Go subscription rate"],
            weaknesses=["Monthly subscription limits"],
            use_cases=["General tasks", "Code generation", "Analysis"],
        ),
        ModelProfile(
            name="mimo-v2.6-pro",
            provider="opencode-go",
            tier=ModelTier.OPENCODE_GO_REC.value,
            cost_per_1k_input=0.000435,
            cost_per_1k_output=0.00087,
            context_window=1000000,
            quality_score=0.82,
            speed_score=0.84,
            capabilities=["code", "analysis", "reasoning"],
            strengths=["OpenCode Go subscription rate"],
            weaknesses=["Monthly subscription limits"],
            use_cases=["General tasks", "Code generation", "Analysis"],
        ),
        ModelProfile(
            name="deepseek-v4.1-flash",
            provider="opencode-go",
            tier=ModelTier.OPENCODE_GO_CHEAP.value,
            cost_per_1k_input=0.00015,
            cost_per_1k_output=0.0006,
            context_window=1000000,
            quality_score=0.79,
            speed_score=0.89,
            capabilities=["code", "analysis", "reasoning"],
            strengths=["OpenCode Go subscription rate"],
            weaknesses=["Monthly subscription limits"],
            use_cases=["General tasks", "Code generation", "Analysis"],
        ),
        ModelProfile(
            name="deepseek-v4-flash-vision-exp",
            provider="opencode-go",
            tier=ModelTier.OPENCODE_GO_CHEAP.value,
            cost_per_1k_input=0.00015,
            cost_per_1k_output=0.0006,
            context_window=1000000,
            quality_score=0.78,
            speed_score=0.86,
            capabilities=["code", "analysis", "vision"],
            strengths=["OpenCode Go subscription rate"],
            weaknesses=["Monthly subscription limits"],
            use_cases=["General tasks", "Code generation", "Analysis"],
        ),
        ModelProfile(
            name="minimax-m2.7",
            provider="opencode-go",
            tier=ModelTier.OPENCODE_GO_CHEAP.value,
            cost_per_1k_input=0.0003,
            cost_per_1k_output=0.0012,
            context_window=1000000,
            quality_score=0.8,
            speed_score=0.86,
            capabilities=["code", "analysis"],
            strengths=["OpenCode Go subscription rate"],
            weaknesses=["Monthly subscription limits"],
            use_cases=["General tasks", "Code generation", "Analysis"],
        ),
        ModelProfile(
            name="minimax-m2.5",
            provider="opencode-go",
            tier=ModelTier.OPENCODE_GO_CHEAP.value,
            cost_per_1k_input=0.0003,
            cost_per_1k_output=0.0012,
            context_window=1000000,
            quality_score=0.78,
            speed_score=0.88,
            capabilities=["code", "analysis"],
            strengths=["OpenCode Go subscription rate"],
            weaknesses=["Monthly subscription limits"],
            use_cases=["General tasks", "Code generation", "Analysis"],
        ),
        ModelProfile(
            name="glm-5.3-flash",
            provider="opencode-go",
            tier=ModelTier.OPENCODE_GO_CHEAP.value,
            cost_per_1k_input=0.00015,
            cost_per_1k_output=0.0005,
            context_window=1000000,
            quality_score=0.77,
            speed_score=0.9,
            capabilities=["code", "analysis"],
            strengths=["OpenCode Go subscription rate"],
            weaknesses=["Monthly subscription limits"],
            use_cases=["General tasks", "Code generation", "Analysis"],
        ),
        ModelProfile(
            name="glm-5.3",
            provider="opencode-go",
            tier=ModelTier.OPENCODE_GO_REC.value,
            cost_per_1k_input=0.0014,
            cost_per_1k_output=0.0044,
            context_window=1000000,
            quality_score=0.88,
            speed_score=0.8,
            capabilities=["code", "analysis", "reasoning"],
            strengths=["OpenCode Go subscription rate"],
            weaknesses=["Monthly subscription limits"],
            use_cases=["General tasks", "Code generation", "Analysis"],
        ),
        ModelProfile(
            name="glm-5.2",
            provider="opencode-go",
            tier=ModelTier.OPENCODE_GO_REC.value,
            cost_per_1k_input=0.0014,
            cost_per_1k_output=0.0044,
            context_window=128000,
            quality_score=0.85,
            speed_score=0.85,
            capabilities=["code", "analysis"],
            strengths=["OpenCode Go subscription rate"],
            weaknesses=["Monthly subscription limits"],
            use_cases=["General tasks", "Code generation", "Analysis"],
        ),
        ModelProfile(
            name="glm-5.1",
            provider="opencode-go",
            tier=ModelTier.OPENCODE_GO_REC.value,
            cost_per_1k_input=0.0014,
            cost_per_1k_output=0.0044,
            context_window=128000,
            quality_score=0.84,
            speed_score=0.85,
            capabilities=["code", "analysis"],
            strengths=["OpenCode Go subscription rate"],
            weaknesses=["Monthly subscription limits"],
            use_cases=["General tasks", "Code generation", "Analysis"],
        ),
        ModelProfile(
            name="kimi-k2.6",
            provider="opencode-go",
            tier=ModelTier.OPENCODE_GO_CHEAP.value,
            cost_per_1k_input=0.00095,
            cost_per_1k_output=0.004,
            context_window=128000,
            quality_score=0.82,
            speed_score=0.9,
            capabilities=["code", "analysis"],
            strengths=["OpenCode Go subscription rate"],
            weaknesses=["Monthly subscription limits"],
            use_cases=["General tasks", "Code generation", "Analysis"],
        ),
        ModelProfile(
            name="kimi-k3",
            provider="opencode-go",
            tier=ModelTier.OPENCODE_GO_REC.value,
            cost_per_1k_input=0.003,
            cost_per_1k_output=0.015,
            context_window=262144,
            quality_score=0.92,
            speed_score=0.75,
            capabilities=["code", "analysis", "reasoning"],
            strengths=["OpenCode Go subscription rate"],
            weaknesses=["Monthly subscription limits"],
            use_cases=["General tasks", "Code generation", "Analysis"],
        ),
        ModelProfile(
            name="qwen3.7-max",
            provider="opencode-go",
            tier=ModelTier.OPENCODE_GO_REC.value,
            cost_per_1k_input=0.0025,
            cost_per_1k_output=0.0075,
            context_window=1000000,
            quality_score=0.88,
            speed_score=0.78,
            capabilities=["code", "analysis", "reasoning"],
            strengths=["OpenCode Go subscription rate"],
            weaknesses=["Monthly subscription limits"],
            use_cases=["General tasks", "Code generation", "Analysis"],
        ),
        ModelProfile(
            name="longcat-2.0",
            provider="opencode-go",
            tier=ModelTier.OPENCODE_GO_CHEAP.value,
            cost_per_1k_input=0.0003,
            cost_per_1k_output=0.0012,
            context_window=1000000,
            quality_score=0.8,
            speed_score=0.85,
            capabilities=["code", "analysis"],
            strengths=["OpenCode Go subscription rate"],
            weaknesses=["Monthly subscription limits"],
            use_cases=["General tasks", "Code generation", "Analysis"],
        ),
        ModelProfile(
            name="muse-spark-1.3-contributor",
            provider="opencode-go",
            tier=ModelTier.OPENCODE_GO_CHEAP.value,
            cost_per_1k_input=0.0001,
            cost_per_1k_output=0.0002,
            context_window=1000000,
            quality_score=0.72,
            speed_score=0.88,
            capabilities=["code", "analysis"],
            strengths=["OpenCode Go subscription rate"],
            weaknesses=["Monthly subscription limits"],
            use_cases=["General tasks", "Code generation", "Analysis"],
        ),
        ModelProfile(
            name="muse-spark-1.2-contributor",
            provider="opencode-go",
            tier=ModelTier.OPENCODE_GO_CHEAP.value,
            cost_per_1k_input=0.0001,
            cost_per_1k_output=0.0002,
            context_window=1000000,
            quality_score=0.7,
            speed_score=0.88,
            capabilities=["code", "analysis"],
            strengths=["OpenCode Go subscription rate"],
            weaknesses=["Monthly subscription limits"],
            use_cases=["General tasks", "Code generation", "Analysis"],
        ),
        ModelProfile(
            name="xiaomi/mimo-v2.5",
            provider="openrouter",
            tier=ModelTier.CHEAP.value,
            cost_per_1k_input=0.00014,
            cost_per_1k_output=0.00028,
            context_window=1000000,
            quality_score=0.75,
            speed_score=0.9,
            capabilities=["code", "analysis", "chat"],
            strengths=["OpenRouter subscription rate"],
            weaknesses=["Pay-per-token"],
            use_cases=["General tasks", "Code generation", "Analysis"],
        ),
        ModelProfile(
            name="xiaomi/mimo-v2.6-flash",
            provider="openrouter",
            tier=ModelTier.CHEAP.value,
            cost_per_1k_input=0.00014,
            cost_per_1k_output=0.00028,
            context_window=1000000,
            quality_score=0.76,
            speed_score=0.92,
            capabilities=["code", "analysis", "chat"],
            strengths=["OpenRouter subscription rate"],
            weaknesses=["Pay-per-token"],
            use_cases=["General tasks", "Code generation", "Analysis"],
        ),
        ModelProfile(
            name="deepseek/deepseek-v4-flash",
            provider="openrouter",
            tier=ModelTier.CHEAP.value,
            cost_per_1k_input=8.8606e-05,
            cost_per_1k_output=0.000177212,
            context_window=1000000,
            quality_score=0.78,
            speed_score=0.88,
            capabilities=["code", "analysis", "reasoning"],
            strengths=["OpenRouter subscription rate"],
            weaknesses=["Pay-per-token"],
            use_cases=["General tasks", "Code generation", "Analysis"],
        ),
        ModelProfile(
            name="deepseek/deepseek-v4.1-flash",
            provider="openrouter",
            tier=ModelTier.CHEAP.value,
            cost_per_1k_input=0.00015,
            cost_per_1k_output=0.0006,
            context_window=1000000,
            quality_score=0.79,
            speed_score=0.89,
            capabilities=["code", "analysis", "reasoning"],
            strengths=["OpenRouter subscription rate"],
            weaknesses=["Pay-per-token"],
            use_cases=["General tasks", "Code generation", "Analysis"],
        ),
    ]
    
    # Fallback chains by capability
    FALLBACK_CHAINS = {
        "code": ["gpt-4-turbo", "claude-3-opus", "gpt-4o", "claude-3-sonnet", "gpt-3.5-turbo", "claude-3-haiku"],
        "architecture": ["claude-3-opus", "gpt-4-turbo", "claude-3-sonnet", "gpt-4o"],
        "review": ["gpt-4-turbo", "claude-3-opus", "gpt-4o", "claude-3-sonnet"],
        "validation": ["gpt-3.5-turbo", "claude-3-haiku", "mimo", "gemini-flash"],
        "documentation": ["claude-3-sonnet", "gpt-4o", "gpt-3.5-turbo"],
        "analysis": ["claude-3-opus", "gpt-4-turbo", "claude-3-sonnet", "gpt-4o"],
        "long_context": ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku", "gpt-4-turbo"],
        # OpenCode Go - Cheap fallback chains
        "opencode-go-cheap": {
            "code": ["kimi-k2.7-code", "deepseek-v4-pro", "minimax-m3", "mimo-v2.5"],
            "analysis": ["mimo-v2.5", "deepseek-v4-flash", "qwen3.8-flash"],
            "reasoning": ["mimo-v2.5-pro", "deepseek-v4-flash", "mimo-v2.5"],
            "writing": ["minimax-m3", "mimo-v2.5", "deepseek-v4-flash"],
        },
        # OpenCode Go - Recommended fallback chains
        "opencode-go-rec": {
            "code": ["kimi-k2.7-code", "deepseek-v4-pro", "minimax-m3"],
            "analysis": ["gpt-5.6-luna", "qwen3.7-plus", "deepseek-v4-pro"],
            "reasoning": ["gpt-5.6-luna", "qwen3.8-max", "grok-4.5"],
            "writing": ["gpt-5.6-luna", "qwen3.7-plus", "qwen3.6-plus"],
        },
    }
    
    def __init__(self, products_dir: str = "products"):
        self.products_dir = Path(products_dir)
        self.registry_file = self.products_dir / ".pipeline" / self.REGISTRY_FILE
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        
        if not self.registry_file.exists():
            self._initialize()
        
        self.models: dict[str, ModelProfile] = self._load()
    
    def _initialize(self) -> None:
        """Initialize registry with default models."""
        data = {
            "models": [asdict(m) for m in self.DEFAULT_MODELS],
            "fallback_chains": self.FALLBACK_CHAINS,
            "created_at": datetime.utcnow().isoformat(),
        }
        self.registry_file.write_text(json.dumps(data, indent=2, default=str))
    
    def _load(self) -> dict[str, ModelProfile]:
        """Load models from registry."""
        try:
            data = json.loads(self.registry_file.read_text())
            models = {}
            for m in data.get("models", []):
                models[m["name"]] = ModelProfile(**m)
            return models
        except (json.JSONDecodeError, OSError, TypeError):
            self._initialize()
            return {m.name: m for m in self.DEFAULT_MODELS}
    
    def _save(self) -> None:
        """Save models to registry."""
        data = {
            "models": [asdict(m) for m in self.models.values()],
            "fallback_chains": self.FALLBACK_CHAINS,
            "updated_at": datetime.utcnow().isoformat(),
        }
        self.registry_file.write_text(json.dumps(data, indent=2, default=str))
    
    def get_model(self, name: str) -> Optional[ModelProfile]:
        """Get a model by name."""
        return self.models.get(name)
    
    def list_models(
        self,
        tier: Optional[str] = None,
        capability: Optional[str] = None,
        enabled_only: bool = True,
    ) -> list[ModelProfile]:
        """List models, optionally filtered."""
        models = list(self.models.values())
        
        if tier:
            models = [m for m in models if m.tier == tier]
        if capability:
            models = [m for m in models if capability in m.capabilities]
        if enabled_only:
            models = [m for m in models if m.enabled]
        
        return models
    
    def find_best_model(
        self,
        capability: str,
        tier: Optional[str] = None,
        max_cost: Optional[float] = None,
        min_quality: float = 0.0,
    ) -> Optional[ModelProfile]:
        """Find the best model for a capability within constraints."""
        candidates = self.list_models(capability=capability)
        
        if tier:
            # Filter by tier (premium > recommended > cheap > free)
            tier_order = [
                ModelTier.PREMIUM.value,
                ModelTier.RECOMMENDED.value,
                ModelTier.CHEAP.value,
                ModelTier.ZENFREE.value,
                ModelTier.OROUTERFREE.value,
                ModelTier.EDUCATION.value,
            ]
            if tier in tier_order:
                tier_index = tier_order.index(tier)
                # Allow this tier and lower
                candidates = [m for m in candidates if m.tier in tier_order[tier_index:]]
            else:
                candidates = [m for m in candidates if m.tier == tier]
        
        if max_cost is not None:
            candidates = [m for m in candidates if m.cost_per_1k_input <= max_cost]
        
        candidates = [m for m in candidates if m.quality_score >= min_quality]
        
        if not candidates:
            return None
        
        # Sort by quality desc, then cost asc
        candidates.sort(key=lambda m: (-m.quality_score, m.cost_per_1k_input))
        return candidates[0]
    
    def get_fallback_chain(self, capability: str) -> list[ModelProfile]:
        """Get the fallback chain for a capability."""
        chain = self.FALLBACK_CHAINS.get(capability, [])
        result = []
        for name in chain:
            model = self.get_model(name)
            if model and model.enabled:
                result.append(model)
        return result
    
    def select_with_fallback(
        self,
        capability: str,
        preferred: Optional[str] = None,
        tier: Optional[str] = None,
    ) -> Optional[ModelProfile]:
        """Select a model with automatic fallback."""
        if preferred and preferred in self.models:
            model = self.models[preferred]
            if model.enabled and capability in model.capabilities:
                return model
        
        # Try best match in tier
        best = self.find_best_model(capability, tier=tier)
        if best:
            return best
        
        # Fallback chain
        chain = self.get_fallback_chain(capability)
        return chain[0] if chain else None
    
    def add_model(self, model: ModelProfile) -> None:
        """Add or update a model."""
        self.models[model.name] = model
        self._save()
    
    def disable_model(self, name: str) -> bool:
        """Disable a model."""
        if name in self.models:
            self.models[name].enabled = False
            self._save()
            return True
        return False
    
    def enable_model(self, name: str) -> bool:
        """Enable a model."""
        if name in self.models:
            self.models[name].enabled = True
            self._save()
            return True
        return False
    
    def get_summary(self) -> dict:
        """Get registry summary."""
        by_tier: dict[str, int] = {}
        by_capability: dict[str, int] = {}
        
        for model in self.models.values():
            by_tier[model.tier] = by_tier.get(model.tier, 0) + 1
            for cap in model.capabilities:
                by_capability[cap] = by_capability.get(cap, 0) + 1
        
        return {
            "total_models": len(self.models),
            "enabled": sum(1 for m in self.models.values() if m.enabled),
            "disabled": sum(1 for m in self.models.values() if not m.enabled),
            "by_tier": by_tier,
            "by_capability": by_capability,
            "fallback_chains": list(self.FALLBACK_CHAINS.keys()),
        }
