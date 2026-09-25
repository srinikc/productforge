"""Tests for Presentation Generator"""
import sys
import json
import tempfile
from pathlib import Path
from datetime import datetime

# Add project root to path
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
        ],
        "getting_started": {
            "steps": ["Install package", "Configure settings", "Run application"]
        },
        "architecture": {
            "tech_stack": ["Python", "FastAPI", "PostgreSQL"]
        },
        "api": {
            "endpoints": ["/api/v1/items", "/api/v1/users"]
        },
        "deployment": {
            "options": ["Docker", "Kubernetes", "Bare Metal"]
        }
    }


class TestPresentationGenerator:
    def test_create_generator(self, temp_products_dir):
        from core.presentation_generator import PresentationGenerator
        gen = PresentationGenerator(temp_products_dir)
        assert gen.products_dir == Path(temp_products_dir)

    def test_generate_slides(self, temp_products_dir, sample_product_data):
        from core.presentation_generator import PresentationGenerator, PresentationConfig
        gen = PresentationGenerator(temp_products_dir)
        config = PresentationConfig(
            product_name="Test Product",
            version="1.0.0",
            tagline="Testing made easy"
        )
        slides = gen._generate_slides(config, sample_product_data)
        assert len(slides) >= 5
        assert slides[0].title == "Test Product"

    def test_generate_full_package(self, temp_products_dir, sample_product_data):
        from core.presentation_generator import PresentationGenerator, PresentationConfig
        gen = PresentationGenerator(temp_products_dir)
        config = PresentationConfig(
            product_name="Test Product",
            version="1.0.0",
            tagline="Testing made easy"
        )
        results = gen.generate_full_package(config, sample_product_data)
        assert "files" in results
        assert "markdown" in results["files"]

    def test_generate_markdown(self, temp_products_dir, sample_product_data):
        from core.presentation_generator import PresentationGenerator, PresentationConfig
        gen = PresentationGenerator(temp_products_dir)
        config = PresentationConfig(
            product_name="Test Product",
            version="1.0.0"
        )
        slides = gen._generate_slides(config, sample_product_data)
        md_path = gen._generate_markdown(config, slides, Path(temp_products_dir))
        assert md_path.exists()
        content = md_path.read_text(encoding="utf-8")
        assert "Test Product" in content

    def test_generate_html(self, temp_products_dir, sample_product_data):
        from core.presentation_generator import PresentationGenerator, PresentationConfig
        gen = PresentationGenerator(temp_products_dir)
        config = PresentationConfig(
            product_name="Test Product",
            version="1.0.0"
        )
        slides = gen._generate_slides(config, sample_product_data)
        html_path = gen._generate_html(config, slides, Path(temp_products_dir))
        assert html_path.exists()
        content = html_path.read_text(encoding="utf-8")
        assert "<html>" in content

    def test_presentation_config_defaults(self):
        from core.presentation_generator import PresentationConfig
        config = PresentationConfig(
            product_name="Test",
            version="1.0.0"
        )
        assert config.formats == ["pptx", "pdf", "html"]
        assert config.include_video is True
        assert config.include_marketing is True


class TestVideoGenerator:
    def test_create_generator(self, temp_products_dir):
        from core.presentation_generator import VideoGenerator
        gen = VideoGenerator(temp_products_dir)
        assert gen.products_dir == Path(temp_products_dir)

    def test_generate_script(self, temp_products_dir, sample_product_data):
        from core.presentation_generator import VideoGenerator
        gen = VideoGenerator(temp_products_dir)
        script = gen._generate_script(sample_product_data)
        assert "Test Product" in script
        assert "Feature Walkthrough" in script

    def test_generate_demo_video(self, temp_products_dir, sample_product_data):
        from core.presentation_generator import VideoGenerator
        gen = VideoGenerator(temp_products_dir)
        results = gen.generate_demo_video("test-product", sample_product_data)
        assert "script" in results
        assert "commands" in results
        assert Path(results["script"]).exists()

    def test_generate_ffmpeg_commands(self, temp_products_dir, sample_product_data):
        from core.presentation_generator import VideoGenerator
        gen = VideoGenerator(temp_products_dir)
        commands = gen._generate_ffmpeg_commands("test-product", sample_product_data, Path(temp_products_dir))
        assert len(commands) > 0
        assert any("ffmpeg" in cmd for cmd in commands)


class TestMarketingGenerator:
    def test_create_generator(self, temp_products_dir):
        from core.presentation_generator import MarketingGenerator
        gen = MarketingGenerator(temp_products_dir)
        assert gen.products_dir == Path(temp_products_dir)

    def test_generate_social_content(self, temp_products_dir, sample_product_data):
        from core.presentation_generator import MarketingGenerator
        gen = MarketingGenerator(temp_products_dir)
        content = gen._generate_social_content(sample_product_data)
        assert "Test Product" in content
        assert "Twitter" in content

    def test_generate_email_templates(self, temp_products_dir, sample_product_data):
        from core.presentation_generator import MarketingGenerator
        gen = MarketingGenerator(temp_products_dir)
        content = gen._generate_email_templates(sample_product_data)
        assert "Test Product" in content
        assert "Launch Announcement" in content

    def test_generate_landing_page(self, temp_products_dir, sample_product_data):
        from core.presentation_generator import MarketingGenerator
        gen = MarketingGenerator(temp_products_dir)
        content = gen._generate_landing_page(sample_product_data)
        assert "Test Product" in content
        assert "Pricing" in content

    def test_generate_blog_post(self, temp_products_dir, sample_product_data):
        from core.presentation_generator import MarketingGenerator
        gen = MarketingGenerator(temp_products_dir)
        content = gen._generate_blog_post(sample_product_data)
        assert "Test Product" in content
        assert "The Problem" in content

    def test_generate_marketing_package(self, temp_products_dir, sample_product_data):
        from core.presentation_generator import MarketingGenerator
        gen = MarketingGenerator(temp_products_dir)
        results = gen.generate_marketing_package("test-product", sample_product_data)
        assert "files" in results
        assert "social_media" in results["files"]
        assert "emails" in results["files"]
        assert "landing_page" in results["files"]
        assert "blog_post" in results["files"]
