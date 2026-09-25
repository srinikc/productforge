"""
Model Recommendation Engine
Recommends optimal AI models for specific tasks based on requirements
"""
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field


@dataclass
class ModelSpec:
    """Specification for an AI model"""
    name: str
    provider: str
    capabilities: List[str]  # text, code, image, audio, etc.
    context_window: int
    cost_per_1k_tokens: float
    speed_tokens_per_sec: int
    quality_score: float  # 0-1
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    use_cases: List[str] = field(default_factory=list)


@dataclass
class TaskRequirements:
    """Requirements for a task"""
    task_type: str  # text_generation, code_generation, image_generation, etc.
    expected_output_size: int  # tokens
    quality_priority: float  # 0-1
    cost_priority: float  # 0-1
    speed_priority: float  # 0-1
    max_cost: Optional[float] = None
    min_quality: Optional[float] = None
    capabilities_required: List[str] = field(default_factory=list)


@dataclass
class ModelRecommendation:
    """A model recommendation"""
    model: ModelSpec
    score: float  # 0-1
    reasoning: str
    estimated_cost: float
    meets_requirements: bool


class ModelRecommendationEngine:
    """Recommends optimal models for tasks"""

    def __init__(self):
        self.models = self._load_models()

    def _load_models(self) -> List[ModelSpec]:
        """Load model catalog"""
        return [
            ModelSpec(
                name="gpt-4-turbo",
                provider="openai",
                capabilities=["text", "code", "analysis"],
                context_window=128000,
                cost_per_1k_tokens=0.01,
                speed_tokens_per_sec=50,
                quality_score=0.95,
                strengths=["High quality", "Long context", "Versatile"],
                weaknesses=["Expensive", "Slower"],
                use_cases=["Complex analysis", "Code generation", "Long documents"]
            ),
            ModelSpec(
                name="gpt-3.5-turbo",
                provider="openai",
                capabilities=["text", "code"],
                context_window=16000,
                cost_per_1k_tokens=0.001,
                speed_tokens_per_sec=100,
                quality_score=0.80,
                strengths=["Fast", "Cheap", "Reliable"],
                weaknesses=["Lower quality", "Shorter context"],
                use_cases=["Chatbots", "Simple tasks", "High volume"]
            ),
            ModelSpec(
                name="claude-3-opus",
                provider="anthropic",
                capabilities=["text", "code", "analysis"],
                context_window=200000,
                cost_per_1k_tokens=0.015,
                speed_tokens_per_sec=40,
                quality_score=0.97,
                strengths=["Highest quality", "Longest context", "Nuanced"],
                weaknesses=["Expensive", "Slower"],
                use_cases=["Complex reasoning", "Long documents", "Research"]
            ),
            ModelSpec(
                name="claude-3-sonnet",
                provider="anthropic",
                capabilities=["text", "code"],
                context_window=200000,
                cost_per_1k_tokens=0.003,
                speed_tokens_per_sec=70,
                quality_score=0.88,
                strengths=["Balanced", "Long context", "Good quality"],
                weaknesses=["Not the cheapest"],
                use_cases=["General purpose", "Code review", "Documentation"]
            ),
            ModelSpec(
                name="mimo-v2.5-free",
                provider="custom",
                capabilities=["text", "code"],
                context_window=32000,
                cost_per_1k_tokens=0.0,
                speed_tokens_per_sec=60,
                quality_score=0.75,
                strengths=["Free", "Decent quality", "Fast"],
                weaknesses=["Quality limitations", "May have rate limits"],
                use_cases=["Development", "Testing", "Budget projects"]
            ),
            ModelSpec(
                name="hy3-free",
                provider="custom",
                capabilities=["text", "code", "analysis"],
                context_window=16000,
                cost_per_1k_tokens=0.0,
                speed_tokens_per_sec=80,
                quality_score=0.82,
                strengths=["Free", "Good for code", "Fast"],
                weaknesses=["Limited context"],
                use_cases=["Code generation", "Quick tasks"]
            ),
            ModelSpec(
                name="dall-e-3",
                provider="openai",
                capabilities=["image"],
                context_window=0,
                cost_per_1k_tokens=0.04,
                speed_tokens_per_sec=0,
                quality_score=0.90,
                strengths=["High quality images", "Creative"],
                weaknesses=["Expensive", "Slow"],
                use_cases=["Marketing visuals", "Product images"]
            ),
            ModelSpec(
                name="whisper",
                provider="openai",
                capabilities=["audio"],
                context_window=0,
                cost_per_1k_tokens=0.006,
                speed_tokens_per_sec=0,
                quality_score=0.92,
                strengths=["Accurate transcription", "Multilingual"],
                weaknesses=["Audio only"],
                use_cases=["Transcription", "Voice features"]
            )
        ]

    def find_models_by_capability(self, capability: str) -> List[ModelSpec]:
        """Find models with a specific capability"""
        return [m for m in self.models if capability in m.capabilities]

    def recommend_model(self, requirements: TaskRequirements) -> ModelRecommendation:
        """Recommend the best model for a task"""
        candidates = []

        for model in self.models:
            # Check capability match
            if requirements.capabilities_required:
                if not all(cap in model.capabilities for cap in requirements.capabilities_required):
                    continue

            # Check quality requirement
            if requirements.min_quality and model.quality_score < requirements.min_quality:
                continue

            # Calculate cost
            estimated_cost = (requirements.expected_output_size / 1000) * model.cost_per_1k_tokens

            # Check cost constraint
            if requirements.max_cost and estimated_cost > requirements.max_cost:
                continue

            # Calculate score
            score = self._calculate_score(model, requirements)

            # Determine if meets requirements
            meets_requirements = (
                model.quality_score >= (requirements.min_quality or 0) and
                (not requirements.max_cost or estimated_cost <= requirements.max_cost)
            )

            # Generate reasoning
            reasoning = self._generate_reasoning(model, requirements, estimated_cost)

            candidates.append(ModelRecommendation(
                model=model,
                score=score,
                reasoning=reasoning,
                estimated_cost=estimated_cost,
                meets_requirements=meets_requirements
            ))

        if not candidates:
            # Fallback: return best available
            best = max(self.models, key=lambda m: m.quality_score)
            return ModelRecommendation(
                model=best,
                score=0.5,
                reasoning="No perfect match found. Returning highest quality model.",
                estimated_cost=0.0,
                meets_requirements=False
            )

        # Return best candidate
        return max(candidates, key=lambda c: c.score)

    def recommend_multiple(self, requirements: TaskRequirements,
                           count: int = 3) -> List[ModelRecommendation]:
        """Recommend top N models"""
        candidates = []

        for model in self.models:
            if requirements.capabilities_required:
                if not all(cap in model.capabilities for cap in requirements.capabilities_required):
                    continue

            estimated_cost = (requirements.expected_output_size / 1000) * model.cost_per_1k_tokens
            score = self._calculate_score(model, requirements)
            reasoning = self._generate_reasoning(model, requirements, estimated_cost)

            meets = (
                model.quality_score >= (requirements.min_quality or 0) and
                (not requirements.max_cost or estimated_cost <= requirements.max_cost)
            )

            candidates.append(ModelRecommendation(
                model=model,
                score=score,
                reasoning=reasoning,
                estimated_cost=estimated_cost,
                meets_requirements=meets
            ))

        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates[:count]

    def _calculate_score(self, model: ModelSpec, requirements: TaskRequirements) -> float:
        """Calculate model score for requirements"""
        quality_score = model.quality_score * requirements.quality_priority

        # Cost score (lower cost = higher score)
        if model.cost_per_1k_tokens == 0:
            cost_score = 1.0 * requirements.cost_priority
        else:
            max_cost = 0.02  # Reference
            cost_score = max(0, 1.0 - (model.cost_per_1k_tokens / max_cost)) * requirements.cost_priority

        # Speed score (higher speed = higher score)
        max_speed = 150
        speed_score = min(1.0, model.speed_tokens_per_sec / max_speed) * requirements.speed_priority

        # Context score
        if requirements.expected_output_size <= model.context_window:
            context_score = 1.0
        else:
            context_score = 0.5

        # Weighted total
        total = (quality_score + cost_score + speed_score) / (
            requirements.quality_priority + requirements.cost_priority + requirements.speed_priority + 0.1
        )

        return total * context_score

    def _generate_reasoning(self, model: ModelSpec, requirements: TaskRequirements,
                           estimated_cost: float) -> str:
        """Generate reasoning for recommendation"""
        reasons = []

        if model.quality_score >= 0.90:
            reasons.append("High quality output")
        elif model.quality_score >= 0.80:
            reasons.append("Good quality output")

        if model.cost_per_1k_tokens == 0:
            reasons.append("Free to use")
        elif estimated_cost < 0.01:
            reasons.append(f"Very low cost (${estimated_cost:.4f})")
        elif estimated_cost < 0.10:
            reasons.append(f"Low cost (${estimated_cost:.4f})")

        if model.speed_tokens_per_sec >= 80:
            reasons.append("Fast response")
        elif model.speed_tokens_per_sec >= 50:
            reasons.append("Good speed")

        if model.context_window >= 100000:
            reasons.append("Long context support")

        if not reasons:
            reasons.append("Balanced choice for your requirements")

        return ". ".join(reasons) + "."

    def generate_recommendation_report(self, requirements: TaskRequirements) -> str:
        """Generate recommendation report"""
        report = f"""# Model Recommendation Report

Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Task Requirements

- **Task Type:** {requirements.task_type}
- **Expected Output Size:** {requirements.expected_output_size} tokens
- **Quality Priority:** {requirements.quality_priority * 100:.0f}%
- **Cost Priority:** {requirements.cost_priority * 100:.0f}%
- **Speed Priority:** {requirements.speed_priority * 100:.0f}%
"""
        if requirements.capabilities_required:
            report += f"- **Required Capabilities:** {', '.join(requirements.capabilities_required)}\n"
        if requirements.max_cost:
            report += f"- **Max Cost:** ${requirements.max_cost:.4f}\n"
        if requirements.min_quality:
            report += f"- **Min Quality:** {requirements.min_quality * 100:.0f}%\n"

        report += "\n## Top Recommendations\n\n"

        recommendations = self.recommend_multiple(requirements, count=5)
        for i, rec in enumerate(recommendations, 1):
            report += f"### {i}. {rec.model.name} (Score: {rec.score * 100:.1f}%)\n\n"
            report += f"**Provider:** {rec.model.provider}\n"
            report += f"**Quality:** {rec.model.quality_score * 100:.0f}%\n"
            report += f"**Cost:** ${rec.model.cost_per_1k_tokens:.4f} per 1K tokens\n"
            report += f"**Speed:** {rec.model.speed_tokens_per_sec} tokens/sec\n"
            report += f"**Context Window:** {rec.model.context_window:,}\n"
            report += f"**Estimated Cost:** ${rec.estimated_cost:.4f}\n"
            report += f"**Meets Requirements:** {'Yes' if rec.meets_requirements else 'No'}\n\n"
            report += f"**Reasoning:** {rec.reasoning}\n\n"
            if rec.model.strengths:
                report += f"**Strengths:** {', '.join(rec.model.strengths)}\n\n"
            report += "---\n\n"

        return report
