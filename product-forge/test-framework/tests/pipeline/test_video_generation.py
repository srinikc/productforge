"""Tests for Video Generation Engine"""
import sys
import tempfile
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest


@pytest.fixture
def temp_products_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_product_data():
    return {
        "name": "Test Product",
        "description": "A revolutionary test product",
        "tagline": "Testing made easy",
        "version": "1.0.0",
        "features": [
            {"name": "Feature 1", "description": "First feature"},
            {"name": "Feature 2", "description": "Second feature"},
            {"name": "Feature 3", "description": "Third feature"}
        ]
    }


class TestVideoGenerationEngine:
    def test_create_engine(self, temp_products_dir):
        from core.video_generation import VideoGenerationEngine
        engine = VideoGenerationEngine(temp_products_dir)
        assert engine is not None
        assert engine.products_dir == Path(temp_products_dir)

    def test_create_demo_script(self, temp_products_dir, sample_product_data):
        from core.video_generation import VideoGenerationEngine
        engine = VideoGenerationEngine(temp_products_dir)
        scenes = engine.create_demo_script(sample_product_data)
        assert len(scenes) >= 5
        assert scenes[0].id == "intro"
        assert any(s.id == "cta" for s in scenes)

    def test_demo_script_includes_features(self, temp_products_dir, sample_product_data):
        from core.video_generation import VideoGenerationEngine
        engine = VideoGenerationEngine(temp_products_dir)
        scenes = engine.create_demo_script(sample_product_data)
        feature_scenes = [s for s in scenes if s.id.startswith("feature-")]
        assert len(feature_scenes) == len(sample_product_data["features"])

    def test_generate_video_script_markdown(self, temp_products_dir, sample_product_data):
        from core.video_generation import VideoGenerationEngine
        engine = VideoGenerationEngine(temp_products_dir)
        scenes = engine.create_demo_script(sample_product_data)
        script = engine.generate_video_script_markdown(scenes, "Test Product")
        assert "Test Product" in script
        assert "Demo Video Script" in script
        assert "Scene" in script
        assert "ffmpeg" in script.lower() or "production" in script.lower()

    def test_generate_ffmpeg_commands(self, temp_products_dir, sample_product_data):
        from core.video_generation import VideoGenerationEngine
        engine = VideoGenerationEngine(temp_products_dir)
        scenes = engine.create_demo_script(sample_product_data)
        output_dir = Path(temp_products_dir) / "test" / "videos"
        output_dir.mkdir(parents=True, exist_ok=True)
        commands = engine.generate_ffmpeg_commands(scenes, output_dir)
        assert len(commands) > 0
        assert any("ffmpeg" in cmd for cmd in commands)
        assert any("mp4" in cmd for cmd in commands)

    def test_create_video_project(self, temp_products_dir, sample_product_data):
        from core.video_generation import VideoGenerationEngine
        engine = VideoGenerationEngine(temp_products_dir)
        result = engine.create_video_project("test-product", sample_product_data)
        assert "scenes" in result
        assert "duration_seconds" in result
        assert "script_path" in result
        assert "commands_path" in result
        assert result["scenes"] >= 5
        assert result["duration_seconds"] > 0
        assert Path(result["script_path"]).exists()
        assert Path(result["commands_path"]).exists()

    def test_video_scene_dataclass(self):
        from core.video_generation import VideoScene
        scene = VideoScene(
            id="test",
            title="Test Scene",
            description="Test description",
            duration_seconds=10
        )
        assert scene.id == "test"
        assert scene.duration_seconds == 10
        assert len(scene.actions) == 0
        assert len(scene.highlights) == 0

    def test_video_config_defaults(self):
        from core.video_generation import VideoConfig
        config = VideoConfig(title="Test Video")
        assert config.width == 1920
        assert config.height == 1080
        assert config.fps == 30
        assert config.output_format == "mp4"
