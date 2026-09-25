"""Tests for FinOps Manager"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest


class TestFinOpsManager:
    def test_create_manager(self):
        from core.finops import FinOpsManager
        mgr = FinOpsManager()
        assert mgr is not None
        assert len(mgr.cost_items) == 0
        assert len(mgr.budgets) == 0

    def test_add_cost_item(self):
        from core.finops import FinOpsManager, CostItem
        mgr = FinOpsManager()
        item = CostItem(
            service="EC2",
            resource="i-12345",
            cost=100.0,
            date="2026-01-01",
            tags={"environment": "prod"}
        )
        mgr.add_cost_item(item)
        assert len(mgr.cost_items) == 1

    def test_get_costs_by_service(self):
        from core.finops import FinOpsManager, CostItem
        mgr = FinOpsManager()
        for i in range(3):
            item = CostItem(
                service="EC2" if i < 2 else "S3",
                resource=f"res-{i}",
                cost=100.0,
                date="2026-01-01"
            )
            mgr.add_cost_item(item)
        costs = mgr.get_costs_by_service()
        assert costs["EC2"] == 200.0
        assert costs["S3"] == 100.0

    def test_get_costs_by_tag(self):
        from core.finops import FinOpsManager, CostItem
        mgr = FinOpsManager()
        for env in ["prod", "dev", "prod"]:
            item = CostItem(
                service="EC2",
                resource="res",
                cost=50.0,
                date="2026-01-01",
                tags={"environment": env}
            )
            mgr.add_cost_item(item)
        costs = mgr.get_costs_by_tag("environment")
        assert costs["prod"] == 100.0
        assert costs["dev"] == 50.0

    def test_create_budget(self):
        from core.finops import FinOpsManager, Budget
        mgr = FinOpsManager()
        budget = Budget(
            name="Monthly Budget",
            amount=1000.0,
            period="monthly",
            start_date="2026-01-01",
            end_date="2026-01-31"
        )
        mgr.create_budget(budget)
        assert len(mgr.budgets) == 1

    def test_budget_remaining(self):
        from core.finops import Budget
        budget = Budget(
            name="Test",
            amount=1000.0,
            period="monthly",
            start_date="2026-01-01",
            end_date="2026-01-31",
            spent=300.0
        )
        assert budget.remaining == 700.0
        assert budget.utilization == 30.0
        assert not budget.is_over_budget

    def test_budget_over_budget(self):
        from core.finops import Budget
        budget = Budget(
            name="Test",
            amount=1000.0,
            period="monthly",
            start_date="2026-01-01",
            end_date="2026-01-31",
            spent=1200.0
        )
        assert budget.is_over_budget
        assert budget.utilization == 120.0

    def test_update_budget_spend(self):
        from core.finops import FinOpsManager, Budget
        mgr = FinOpsManager()
        budget = Budget(
            name="Test",
            amount=1000.0,
            period="monthly",
            start_date="2026-01-01",
            end_date="2026-01-31"
        )
        mgr.create_budget(budget)
        mgr.update_budget_spend("Test", 250.0)
        assert mgr.budgets[0].spent == 250.0

    def test_get_budget_status(self):
        from core.finops import FinOpsManager, Budget
        mgr = FinOpsManager()
        budget = Budget(
            name="Test",
            amount=1000.0,
            period="monthly",
            start_date="2026-01-01",
            end_date="2026-01-31",
            spent=500.0
        )
        mgr.create_budget(budget)
        statuses = mgr.get_budget_status()
        assert len(statuses) == 1
        assert statuses[0]["name"] == "Test"
        assert statuses[0]["utilization"] == 50.0

    def test_generate_optimization_recommendations(self):
        from core.finops import FinOpsManager, CostItem
        mgr = FinOpsManager()
        for i in range(3):
            item = CostItem(
                service="EC2",
                resource=f"res-{i}",
                cost=500.0,
                date="2026-01-01"
            )
            mgr.add_cost_item(item)
        recommendations = mgr.generate_optimization_recommendations()
        assert len(recommendations) > 0
        assert any("Right-size" in r.title for r in recommendations)

    def test_optimization_recommendations_for_budget_alert(self):
        from core.finops import FinOpsManager, Budget
        mgr = FinOpsManager()
        budget = Budget(
            name="Test",
            amount=1000.0,
            period="monthly",
            start_date="2026-01-01",
            end_date="2026-01-31",
            spent=900.0
        )
        mgr.create_budget(budget)
        recommendations = mgr.generate_optimization_recommendations()
        assert any("Budget alert" in r.title for r in recommendations)

    def test_generate_finops_report(self):
        from core.finops import FinOpsManager, CostItem, Budget
        mgr = FinOpsManager()
        item = CostItem(
            service="EC2",
            resource="i-12345",
            cost=500.0,
            date="2026-01-01"
        )
        mgr.add_cost_item(item)
        budget = Budget(
            name="Test",
            amount=1000.0,
            period="monthly",
            start_date="2026-01-01",
            end_date="2026-01-31",
            spent=500.0
        )
        mgr.create_budget(budget)
        report = mgr.generate_finops_report()
        assert "FinOps" in report
        assert "Cost Summary" in report
        assert "Budget Status" in report
        assert "Optimization" in report
