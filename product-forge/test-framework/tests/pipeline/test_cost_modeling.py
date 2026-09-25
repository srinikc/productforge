"""Tests for Cost Modeling"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest


class TestCostModeler:
    def test_create_modeler(self):
        from core.cost_modeling import CostModeler
        modeler = CostModeler()
        assert modeler is not None
        assert "aws" in modeler.pricing_data
        assert "gcp" in modeler.pricing_data
        assert "azure" in modeler.pricing_data

    def test_estimate_compute_cost(self):
        from core.cost_modeling import CostModeler
        modeler = CostModeler()
        estimate = modeler.estimate_compute_cost("aws", "t3.micro", 1, 730)
        assert estimate.service == "compute"
        assert estimate.provider == "aws"
        assert estimate.instance_type == "t3.micro"
        assert estimate.quantity == 1
        assert estimate.monthly_cost > 0
        assert estimate.annual_cost == estimate.monthly_cost * 12

    def test_estimate_storage_cost(self):
        from core.cost_modeling import CostModeler
        modeler = CostModeler()
        estimate = modeler.estimate_storage_cost("aws", "gp2", 100)
        assert estimate.service == "storage"
        assert estimate.provider == "aws"
        assert estimate.instance_type == "gp2"
        assert estimate.quantity == 100
        assert estimate.monthly_cost > 0

    def test_estimate_database_cost(self):
        from core.cost_modeling import CostModeler
        modeler = CostModeler()
        estimate = modeler.estimate_database_cost("aws", "rds_t3_micro", 1, 730)
        assert estimate.service == "database"
        assert estimate.provider == "aws"
        assert estimate.instance_type == "rds_t3_micro"
        assert estimate.monthly_cost > 0

    def test_estimate_networking_cost(self):
        from core.cost_modeling import CostModeler
        modeler = CostModeler()
        estimate = modeler.estimate_networking_cost("aws", 100)
        assert estimate.service == "networking"
        assert estimate.provider == "aws"
        assert estimate.quantity == 100
        assert estimate.monthly_cost > 0

    def test_estimate_product_costs_small(self):
        from core.cost_modeling import CostModeler
        modeler = CostModeler()
        cost = modeler.estimate_product_costs("web_app", "small")
        assert len(cost.compute) > 0
        assert len(cost.storage) > 0
        assert len(cost.database) > 0
        assert len(cost.networking) > 0
        assert cost.total_monthly > 0
        assert cost.total_annual == cost.total_monthly * 12

    def test_estimate_product_costs_medium(self):
        from core.cost_modeling import CostModeler
        modeler = CostModeler()
        cost = modeler.estimate_product_costs("web_app", "medium")
        assert cost.total_monthly > 0
        assert cost.total_annual == cost.total_monthly * 12

    def test_estimate_product_costs_large(self):
        from core.cost_modeling import CostModeler
        modeler = CostModeler()
        cost = modeler.estimate_product_costs("web_app", "large")
        assert cost.total_monthly > 0
        assert cost.total_annual == cost.total_monthly * 12

    def test_estimate_product_costs_grows_with_scale(self):
        from core.cost_modeling import CostModeler
        modeler = CostModeler()
        small = modeler.estimate_product_costs("web_app", "small")
        medium = modeler.estimate_product_costs("web_app", "medium")
        large = modeler.estimate_product_costs("web_app", "large")
        assert small.total_monthly < medium.total_monthly < large.total_monthly

    def test_generate_cost_report(self):
        from core.cost_modeling import CostModeler
        modeler = CostModeler()
        cost = modeler.estimate_product_costs("web_app", "small")
        report = modeler.generate_cost_report("Test Product", cost)
        assert "Test Product" in report
        assert "Cost Analysis" in report
        assert "Monthly" in report or "monthly" in report
        assert "Annual" in report or "annual" in report
        assert "Optimization" in report
