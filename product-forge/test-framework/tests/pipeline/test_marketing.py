"""Tests for Marketing Generator"""
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
            {"name": "Feature 2", "description": "Second feature"}
        ]
    }


class TestMarketingGenerator:
    def test_create_generator(self, temp_products_dir):
        from core.marketing import MarketingGenerator
        gen = MarketingGenerator(temp_products_dir)
        assert gen.products_dir == Path(temp_products_dir)

    def test_generate_gtm_strategy(self, temp_products_dir, sample_product_data):
        from core.marketing import MarketingGenerator
        gen = MarketingGenerator(temp_products_dir)
        gtm = gen._generate_gtm_strategy(sample_product_data)
        assert "Test Product" in gtm
        assert "Go-to-Market" in gtm
        assert "Target Market" in gtm

    def test_generate_positioning(self, temp_products_dir, sample_product_data):
        from core.marketing import MarketingGenerator
        gen = MarketingGenerator(temp_products_dir)
        positioning = gen._generate_positioning(sample_product_data)
        assert "Test Product" in positioning
        assert "Positioning" in positioning

    def test_generate_content_calendar(self, temp_products_dir, sample_product_data):
        from core.marketing import MarketingGenerator
        gen = MarketingGenerator(temp_products_dir)
        calendar = gen._generate_content_calendar(sample_product_data)
        assert "Test Product" in calendar
        assert "Content Calendar" in calendar

    def test_generate_campaign_plan(self, temp_products_dir, sample_product_data):
        from core.marketing import MarketingGenerator
        gen = MarketingGenerator(temp_products_dir)
        campaign = gen._generate_campaign_plan(sample_product_data)
        assert "Test Product" in campaign
        assert "Campaign" in campaign

    def test_generate_social_media(self, temp_products_dir, sample_product_data):
        from core.marketing import MarketingGenerator
        gen = MarketingGenerator(temp_products_dir)
        social = gen._generate_social_media(sample_product_data)
        assert "Test Product" in social
        assert "Social Media" in social
        assert "Twitter" in social

    def test_generate_pr_strategy(self, temp_products_dir, sample_product_data):
        from core.marketing import MarketingGenerator
        gen = MarketingGenerator(temp_products_dir)
        pr = gen._generate_pr_strategy(sample_product_data)
        assert "Test Product" in pr
        assert "PR" in pr

    def test_generate_partnerships(self, temp_products_dir, sample_product_data):
        from core.marketing import MarketingGenerator
        gen = MarketingGenerator(temp_products_dir)
        partnerships = gen._generate_partnerships(sample_product_data)
        assert "Test Product" in partnerships
        assert "Partnership" in partnerships

    def test_generate_analytics(self, temp_products_dir):
        from core.marketing import MarketingGenerator
        gen = MarketingGenerator(temp_products_dir)
        analytics = gen._generate_analytics()
        assert "Analytics" in analytics
        assert "KPI" in analytics or "Metrics" in analytics

    def test_generate_marketing_package(self, temp_products_dir, sample_product_data):
        from core.marketing import MarketingGenerator
        gen = MarketingGenerator(temp_products_dir)
        results = gen.generate_marketing_package("test-product", sample_product_data)
        assert "files" in results
        assert "gtm_strategy" in results["files"]
        assert "positioning" in results["files"]
        assert "content_calendar" in results["files"]
        assert "campaign_plan" in results["files"]
        assert "social_media" in results["files"]
        assert "pr_strategy" in results["files"]
        assert "partnerships" in results["files"]
        assert "analytics" in results["files"]
        # Verify files were created
        for file_path in results["files"].values():
            assert Path(file_path).exists()
