"""Tests for Change Registry"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest


class TestChangeRegistry:
    def test_create_registry(self):
        from core.change_registry import ChangeRegistry
        registry = ChangeRegistry()
        assert registry is not None
        assert len(registry.changes) == 0

    def test_add_change(self):
        from core.change_registry import ChangeRegistry, ChangeRequest
        registry = ChangeRegistry()
        change = ChangeRequest(
            id="CHG-001",
            title="Test Change",
            description="Test description",
            type="feature",
            priority="high",
            status="proposed",
            requester="test_user",
            created_at="2026-01-01T00:00:00"
        )
        registry.add_change(change)
        assert len(registry.changes) == 1

    def test_get_change(self):
        from core.change_registry import ChangeRegistry, ChangeRequest
        registry = ChangeRegistry()
        change = ChangeRequest(
            id="CHG-001",
            title="Test Change",
            description="Test description",
            type="feature",
            priority="high",
            status="proposed",
            requester="test_user",
            created_at="2026-01-01T00:00:00"
        )
        registry.add_change(change)
        retrieved = registry.get_change("CHG-001")
        assert retrieved is not None
        assert retrieved.id == "CHG-001"
        assert retrieved.title == "Test Change"

    def test_update_change(self):
        from core.change_registry import ChangeRegistry, ChangeRequest
        registry = ChangeRegistry()
        change = ChangeRequest(
            id="CHG-001",
            title="Test Change",
            description="Test description",
            type="feature",
            priority="high",
            status="proposed",
            requester="test_user",
            created_at="2026-01-01T00:00:00"
        )
        registry.add_change(change)
        registry.update_change("CHG-001", status="approved", priority="critical")
        updated = registry.get_change("CHG-001")
        assert updated.status == "approved"
        assert updated.priority == "critical"

    def test_list_changes(self):
        from core.change_registry import ChangeRegistry, ChangeRequest
        registry = ChangeRegistry()
        for i in range(3):
            change = ChangeRequest(
                id=f"CHG-{i:03d}",
                title=f"Change {i}",
                description="Test",
                type="feature",
                priority="high" if i < 2 else "low",
                status="proposed",
                requester="test",
                created_at="2026-01-01T00:00:00"
            )
            registry.add_change(change)
        all_changes = registry.list_changes()
        assert len(all_changes) == 3

        high_priority = registry.list_changes(priority="high")
        assert len(high_priority) == 2

        proposed = registry.list_changes(status="proposed")
        assert len(proposed) == 3

    def test_analyze_impact_low_risk(self):
        from core.change_registry import ChangeRegistry, ChangeRequest
        registry = ChangeRegistry()
        change = ChangeRequest(
            id="CHG-001",
            title="Small change",
            description="Small change",
            type="feature",
            priority="low",
            status="proposed",
            requester="test",
            created_at="2026-01-01T00:00:00",
            files_affected=["file1.py"]
        )
        analysis = registry.analyze_impact(change)
        assert analysis.change_id == "CHG-001"
        assert analysis.risk_level == "low"

    def test_analyze_impact_high_risk(self):
        from core.change_registry import ChangeRegistry, ChangeRequest
        registry = ChangeRegistry()
        files = [f"file{i}.py" for i in range(30)]
        change = ChangeRequest(
            id="CHG-001",
            title="Large change",
            description="Large change",
            type="security",
            priority="critical",
            status="proposed",
            requester="test",
            created_at="2026-01-01T00:00:00",
            files_affected=files
        )
        analysis = registry.analyze_impact(change)
        assert analysis.risk_level == "high"
        assert len(analysis.recommendations) > 0

    def test_identify_breaking_changes_api(self):
        from core.change_registry import ChangeRegistry, ChangeRequest
        registry = ChangeRegistry()
        change = ChangeRequest(
            id="CHG-001",
            title="API change",
            description="API change",
            type="feature",
            priority="high",
            status="proposed",
            requester="test",
            created_at="2026-01-01T00:00:00",
            files_affected=["api/users.py", "api/auth.py"]
        )
        analysis = registry.analyze_impact(change)
        assert len(analysis.breaking_changes) > 0
        assert any("API" in bc for bc in analysis.breaking_changes)

    def test_identify_breaking_changes_db(self):
        from core.change_registry import ChangeRegistry, ChangeRequest
        registry = ChangeRegistry()
        change = ChangeRequest(
            id="CHG-001",
            title="DB change",
            description="DB change",
            type="feature",
            priority="high",
            status="proposed",
            requester="test",
            created_at="2026-01-01T00:00:00",
            files_affected=["schema/migration.py", "db/schema.py"]
        )
        analysis = registry.analyze_impact(change)
        assert len(analysis.breaking_changes) > 0
        assert any("Database" in bc for bc in analysis.breaking_changes)

    def test_security_recommendations(self):
        from core.change_registry import ChangeRegistry, ChangeRequest
        registry = ChangeRegistry()
        change = ChangeRequest(
            id="CHG-001",
            title="Security fix",
            description="Security fix",
            type="security",
            priority="critical",
            status="proposed",
            requester="test",
            created_at="2026-01-01T00:00:00"
        )
        analysis = registry.analyze_impact(change)
        assert any("Security review" in r for r in analysis.recommendations)

    def test_generate_change_report(self):
        from core.change_registry import ChangeRegistry, ChangeRequest
        registry = ChangeRegistry()
        for i in range(3):
            change = ChangeRequest(
                id=f"CHG-{i:03d}",
                title=f"Change {i}",
                description=f"Description {i}",
                type="feature",
                priority="high",
                status="proposed",
                requester="test",
                created_at="2026-01-01T00:00:00"
            )
            registry.add_change(change)
        report = registry.generate_change_report()
        assert "Change Registry" in report
        assert "Total Changes" in report
        assert "CHG-000" in report
