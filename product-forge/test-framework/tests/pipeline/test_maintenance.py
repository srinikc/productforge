"""Tests for Maintenance Manager"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest


class TestMaintenanceManager:
    def test_create_manager(self):
        from core.maintenance import MaintenanceManager
        mgr = MaintenanceManager()
        assert mgr is not None
        assert len(mgr.issues) == 0
        assert len(mgr.patches) == 0

    def test_report_issue(self):
        from core.maintenance import MaintenanceManager, Issue
        mgr = MaintenanceManager()
        issue = Issue(
            id="ISS-001",
            title="Test issue",
            description="Test description",
            severity="high",
            status="open",
            type="bug",
            created_at="2026-01-01T00:00:00",
            reporter="test_user"
        )
        mgr.report_issue(issue)
        assert len(mgr.issues) == 1

    def test_get_issue(self):
        from core.maintenance import MaintenanceManager, Issue
        mgr = MaintenanceManager()
        issue = Issue(
            id="ISS-001",
            title="Test issue",
            description="Test description",
            severity="high",
            status="open",
            type="bug",
            created_at="2026-01-01T00:00:00",
            reporter="test"
        )
        mgr.report_issue(issue)
        retrieved = mgr.get_issue("ISS-001")
        assert retrieved is not None
        assert retrieved.id == "ISS-001"

    def test_update_issue(self):
        from core.maintenance import MaintenanceManager, Issue
        mgr = MaintenanceManager()
        issue = Issue(
            id="ISS-001",
            title="Test issue",
            description="Test description",
            severity="high",
            status="open",
            type="bug",
            created_at="2026-01-01T00:00:00",
            reporter="test"
        )
        mgr.report_issue(issue)
        mgr.update_issue("ISS-001", status="resolved", assignee="dev1")
        updated = mgr.get_issue("ISS-001")
        assert updated.status == "resolved"
        assert updated.assignee == "dev1"

    def test_list_issues(self):
        from core.maintenance import MaintenanceManager, Issue
        mgr = MaintenanceManager()
        for i in range(3):
            issue = Issue(
                id=f"ISS-{i:03d}",
                title=f"Issue {i}",
                description="Test",
                severity="high" if i < 2 else "low",
                status="open" if i < 2 else "resolved",
                type="bug",
                created_at="2026-01-01T00:00:00",
                reporter="test"
            )
            mgr.report_issue(issue)
        all_issues = mgr.list_issues()
        assert len(all_issues) == 3
        open_issues = mgr.list_issues(status="open")
        assert len(open_issues) == 2
        high_severity = mgr.list_issues(severity="high")
        assert len(high_severity) == 2

    def test_apply_patch(self):
        from core.maintenance import MaintenanceManager, Patch
        mgr = MaintenanceManager()
        patch = Patch(
            id="P-001",
            version="1.0.1",
            type="security",
            description="Security fix",
            created_at="2026-01-01T00:00:00"
        )
        mgr.apply_patch(patch)
        assert len(mgr.patches) == 1
        assert mgr.patches[0].applied_at is not None

    def test_get_patches(self):
        from core.maintenance import MaintenanceManager, Patch
        mgr = MaintenanceManager()
        for i in range(3):
            patch = Patch(
                id=f"P-{i:03d}",
                version="1.0.1",
                type="security" if i < 2 else "bugfix",
                description="Test",
                created_at="2026-01-01T00:00:00"
            )
            mgr.apply_patch(patch)
        all_patches = mgr.get_patches()
        assert len(all_patches) == 3
        security_patches = mgr.get_patches(patch_type="security")
        assert len(security_patches) == 2

    def test_run_health_check_healthy(self):
        from core.maintenance import MaintenanceManager
        mgr = MaintenanceManager()
        check = mgr.run_health_check()
        assert check.status == "healthy"
        assert "api" in check.checks
        assert check.checks["api"] == "healthy"
        assert check.metrics["cpu_usage"] > 0

    def test_run_health_check_degraded(self):
        from core.maintenance import MaintenanceManager, Issue
        mgr = MaintenanceManager()
        issue = Issue(
            id="ISS-001",
            title="Minor issue",
            description="Test",
            severity="low",
            status="open",
            type="bug",
            created_at="2026-01-01T00:00:00",
            reporter="test"
        )
        mgr.report_issue(issue)
        check = mgr.run_health_check()
        assert check.status == "degraded"
        assert len(check.alerts) > 0

    def test_run_health_check_unhealthy(self):
        from core.maintenance import MaintenanceManager, Issue
        mgr = MaintenanceManager()
        issue = Issue(
            id="ISS-001",
            title="Critical issue",
            description="Test",
            severity="critical",
            status="open",
            type="bug",
            created_at="2026-01-01T00:00:00",
            reporter="test"
        )
        mgr.report_issue(issue)
        check = mgr.run_health_check()
        assert check.status == "unhealthy"
        assert any("critical" in a.lower() for a in check.alerts)

    def test_generate_maintenance_report(self):
        from core.maintenance import MaintenanceManager, Issue, Patch
        mgr = MaintenanceManager()
        issue = Issue(
            id="ISS-001",
            title="Test",
            description="Test",
            severity="high",
            status="open",
            type="bug",
            created_at="2026-01-01T00:00:00",
            reporter="test"
        )
        mgr.report_issue(issue)
        patch = Patch(
            id="P-001",
            version="1.0.1",
            type="security",
            description="Test",
            created_at="2026-01-01T00:00:00"
        )
        mgr.apply_patch(patch)
        mgr.run_health_check()
        report = mgr.generate_maintenance_report()
        assert "Maintenance" in report
        assert "Health" in report
        assert "Issue" in report
        assert "Patch" in report
