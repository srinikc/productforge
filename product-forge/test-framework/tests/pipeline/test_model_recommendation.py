"""Tests for Model Recommendation Engine"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest


class TestModelRecommendationEngine:
    def test_create_engine(self):
        from core.model_recommendation import ModelRecommendationEngine
        engine = ModelRecommendationEngine()
        assert engine is not None
        assert len(engine.models) > 0

    def test_find_models_by_capability_text(self):
        from core.model_recommendation import ModelRecommendationEngine
        engine = ModelRecommendationEngine()
        text_models = engine.find_models_by_capability("text")
        assert len(text_models) > 0
        assert all("text" in m.capabilities for m in text_models)

    def test_find_models_by_capability_code(self):
        from core.model_recommendation import ModelRecommendationEngine
        engine = ModelRecommendationEngine()
        code_models = engine.find_models_by_capability("code")
        assert len(code_models) > 0

    def test_find_models_by_capability_image(self):
        from core.model_recommendation import ModelRecommendationEngine
        engine = ModelRecommendationEngine()
        image_models = engine.find_models_by_capability("image")
        assert len(image_models) > 0
        assert any("dall" in m.name.lower() for m in image_models)

    def test_recommend_model_basic(self):
        from core.model_recommendation import ModelRecommendationEngine, TaskRequirements
        engine = ModelRecommendationEngine()
        requirements = TaskRequirements(
            task_type="text_generation",
            expected_output_size=1000,
            quality_priority=0.5,
            cost_priority=0.5,
            speed_priority=0.5
        )
        rec = engine.recommend_model(requirements)
        assert rec is not None
        assert rec.model is not None
        assert rec.score >= 0
        assert rec.score <= 1

    def test_recommend_model_quality_focused(self):
        from core.model_recommendation import ModelRecommendationEngine, TaskRequirements
        engine = ModelRecommendationEngine()
        requirements = TaskRequirements(
            task_type="complex_analysis",
            expected_output_size=5000,
            quality_priority=1.0,
            cost_priority=0.0,
            speed_priority=0.0,
            min_quality=0.90
        )
        rec = engine.recommend_model(requirements)
        assert rec.model.quality_score >= 0.85

    def test_recommend_model_cost_focused(self):
        from core.model_recommendation import ModelRecommendationEngine, TaskRequirements
        engine = ModelRecommendationEngine()
        requirements = TaskRequirements(
            task_type="simple_task",
            expected_output_size=500,
            quality_priority=0.2,
            cost_priority=1.0,
            speed_priority=0.2,
            max_cost=0.001
        )
        rec = engine.recommend_model(requirements)
        # Should prefer a free or very cheap model
        assert rec.estimated_cost <= 0.001 or rec.model.cost_per_1k_tokens == 0

    def test_recommend_model_speed_focused(self):
        from core.model_recommendation import ModelRecommendationEngine, TaskRequirements
        engine = ModelRecommendationEngine()
        requirements = TaskRequirements(
            task_type="chat",
            expected_output_size=500,
            quality_priority=0.3,
            cost_priority=0.3,
            speed_priority=1.0
        )
        rec = engine.recommend_model(requirements)
        # Should prefer a fast model
        assert rec.model.speed_tokens_per_sec >= 60

    def test_recommend_multiple(self):
        from core.model_recommendation import ModelRecommendationEngine, TaskRequirements
        engine = ModelRecommendationEngine()
        requirements = TaskRequirements(
            task_type="text_generation",
            expected_output_size=1000,
            quality_priority=0.5,
            cost_priority=0.5,
            speed_priority=0.5
        )
        recs = engine.recommend_multiple(requirements, count=3)
        assert len(recs) == 3
        # Should be sorted by score descending
        for i in range(len(recs) - 1):
            assert recs[i].score >= recs[i + 1].score

    def test_recommend_with_capability_filter(self):
        from core.model_recommendation import ModelRecommendationEngine, TaskRequirements
        engine = ModelRecommendationEngine()
        requirements = TaskRequirements(
            task_type="code_generation",
            expected_output_size=2000,
            quality_priority=0.5,
            cost_priority=0.5,
            speed_priority=0.5,
            capabilities_required=["code"]
        )
        rec = engine.recommend_model(requirements)
        assert "code" in rec.model.capabilities

    def test_recommend_with_context_requirement(self):
        from core.model_recommendation import ModelRecommendationEngine, TaskRequirements
        engine = ModelRecommendationEngine()
        requirements = TaskRequirements(
            task_type="long_document",
            expected_output_size=50000,
            quality_priority=0.7,
            cost_priority=0.3,
            speed_priority=0.3
        )
        rec = engine.recommend_model(requirements)
        # Should have sufficient context
        assert rec.model.context_window >= requirements.expected_output_size or rec.model.context_window >= 50000

    def test_generate_recommendation_report(self):
        from core.model_recommendation import ModelRecommendationEngine, TaskRequirements
        engine = ModelRecommendationEngine()
        requirements = TaskRequirements(
            task_type="text_generation",
            expected_output_size=1000,
            quality_priority=0.5,
            cost_priority=0.5,
            speed_priority=0.5
        )
        report = engine.generate_recommendation_report(requirements)
        assert "Model Recommendation" in report
        assert "Top Recommendations" in report
        assert "Score" in report

    def test_model_spec_dataclass(self):
        from core.model_recommendation import ModelSpec
        spec = ModelSpec(
            name="test-model",
            provider="test",
            capabilities=["text"],
            context_window=4096,
            cost_per_1k_tokens=0.001,
            speed_tokens_per_sec=50,
            quality_score=0.8
        )
        assert spec.name == "test-model"
        assert spec.context_window == 4096
