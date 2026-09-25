"""Tests for Customer Onboarding"""
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
        ],
        "architecture": {
            "tech_stack": ["Python", "FastAPI", "PostgreSQL"]
        },
        "api": {
            "endpoints": ["/api/v1/items", "/api/v1/users"]
        }
    }


class TestOnboardingGenerator:
    def test_create_generator(self, temp_products_dir):
        from core.customer_onboarding import OnboardingGenerator
        gen = OnboardingGenerator(temp_products_dir)
        assert gen.products_dir == Path(temp_products_dir)

    def test_generate_welcome_email(self, temp_products_dir, sample_product_data):
        from core.customer_onboarding import OnboardingGenerator
        gen = OnboardingGenerator(temp_products_dir)
        email = gen._generate_welcome_email(sample_product_data, None)
        assert "Test Product" in email
        assert "Welcome" in email

    def test_generate_setup_checklist(self, temp_products_dir, sample_product_data):
        from core.customer_onboarding import OnboardingGenerator
        gen = OnboardingGenerator(temp_products_dir)
        checklist = gen._generate_setup_checklist(sample_product_data)
        assert "Test Product" in checklist
        assert "Setup Checklist" in checklist

    def test_generate_installation_guide(self, temp_products_dir, sample_product_data):
        from core.customer_onboarding import OnboardingGenerator
        gen = OnboardingGenerator(temp_products_dir)
        guide = gen._generate_installation_guide(sample_product_data)
        assert "Test Product" in guide
        assert "Installation" in guide
        assert "pip install" in guide

    def test_generate_first_run_wizard(self, temp_products_dir, sample_product_data):
        from core.customer_onboarding import OnboardingGenerator
        gen = OnboardingGenerator(temp_products_dir)
        wizard = gen._generate_first_run_wizard(sample_product_data)
        assert "Test Product" in wizard
        assert "First-Run" in wizard

    def test_generate_quick_wins(self, temp_products_dir, sample_product_data):
        from core.customer_onboarding import OnboardingGenerator
        gen = OnboardingGenerator(temp_products_dir)
        wins = gen._generate_quick_wins(sample_product_data)
        assert "Test Product" in wins
        assert "Quick Wins" in wins

    def test_generate_user_manual(self, temp_products_dir, sample_product_data):
        from core.customer_onboarding import OnboardingGenerator
        gen = OnboardingGenerator(temp_products_dir)
        manual = gen._generate_user_manual(sample_product_data)
        assert "Test Product" in manual
        assert "User Manual" in manual
        assert "Feature 1" in manual

    def test_generate_faq(self, temp_products_dir, sample_product_data):
        from core.customer_onboarding import OnboardingGenerator
        gen = OnboardingGenerator(temp_products_dir)
        faq = gen._generate_faq(sample_product_data)
        assert "Test Product" in faq
        assert "Frequently Asked" in faq

    def test_generate_troubleshooting(self, temp_products_dir, sample_product_data):
        from core.customer_onboarding import OnboardingGenerator
        gen = OnboardingGenerator(temp_products_dir)
        ts = gen._generate_troubleshooting(sample_product_data)
        assert "Test Product" in ts
        assert "Troubleshooting" in ts

    def test_generate_support_resources(self, temp_products_dir, sample_product_data):
        from core.customer_onboarding import OnboardingGenerator
        gen = OnboardingGenerator(temp_products_dir)
        support = gen._generate_support_resources(sample_product_data)
        assert "Test Product" in support
        assert "Support" in support

    def test_generate_success_metrics(self, temp_products_dir):
        from core.customer_onboarding import OnboardingGenerator
        gen = OnboardingGenerator(temp_products_dir)
        metrics = gen._generate_success_metrics()
        assert "Success Metrics" in metrics
        assert "NPS" in metrics

    def test_generate_communication_plan(self, temp_products_dir):
        from core.customer_onboarding import OnboardingGenerator
        gen = OnboardingGenerator(temp_products_dir)
        plan = gen._generate_communication_plan()
        assert "Communication Plan" in plan
        assert "Day 1" in plan

    def test_generate_onboarding_package(self, temp_products_dir, sample_product_data):
        from core.customer_onboarding import OnboardingGenerator
        gen = OnboardingGenerator(temp_products_dir)
        results = gen.generate_onboarding_package("test-product", sample_product_data)
        assert "files" in results
        assert "welcome_email" in results["files"]
        assert "setup_checklist" in results["files"]
        assert "installation_guide" in results["files"]
        assert "first_run_wizard" in results["files"]
        assert "quick_wins" in results["files"]
        assert "user_manual" in results["files"]
        assert "faq" in results["files"]
        assert "troubleshooting" in results["files"]
        assert "support_resources" in results["files"]
        assert "success_metrics" in results["files"]
        assert "communication_plan" in results["files"]
        # Verify files were created
        for file_path in results["files"].values():
            assert Path(file_path).exists()
