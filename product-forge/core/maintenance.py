"""
Maintenance
Handles monitoring, issue tracking, patch management, and health checks
"""
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field


@dataclass
class Issue:
    """Product issue/bug"""
    id: str
    title: str
    description: str
    severity: str  # critical, high, medium, low
    status: str  # open, in_progress, resolved, closed
    type: str  # bug, performance, security, ux
    created_at: str
    reporter: str
    assignee: Optional[str] = None
    resolved_at: Optional[str] = None
    affected_versions: List[str] = field(default_factory=list)
    root_cause: str = ""
    fix_description: str = ""


@dataclass
class Patch:
    """Product patch"""
    id: str
    version: str
    type: str  # security, bugfix, feature, performance
    description: str
    created_at: str
    applied_at: Optional[str] = None
    cve_id: Optional[str] = None
    files_changed: List[str] = field(default_factory=list)
    rollback_procedure: str = ""


@dataclass
class HealthCheck:
    """Health check result"""
    timestamp: str
    status: str  # healthy, degraded, unhealthy
    checks: Dict[str, str] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)
    alerts: List[str] = field(default_factory=list)


class MaintenanceManager:
    """Manages product maintenance, issues, patches, and health checks"""

    def __init__(self, products_dir: str = "products"):
        self.products_dir = Path(products_dir)
        self.issues: List[Issue] = []
        self.patches: List[Patch] = []
        self.health_history: List[HealthCheck] = []

    def report_issue(self, issue: Issue):
        """Report a new issue"""
        self.issues.append(issue)

    def get_issue(self, issue_id: str) -> Optional[Issue]:
        """Get an issue by ID"""
        for issue in self.issues:
            if issue.id == issue_id:
                return issue
        return None

    def update_issue(self, issue_id: str, **kwargs) -> Optional[Issue]:
        """Update an issue"""
        issue = self.get_issue(issue_id)
        if issue:
            for key, value in kwargs.items():
                if hasattr(issue, key):
                    setattr(issue, key, value)
        return issue

    def list_issues(self, status: Optional[str] = None,
                    severity: Optional[str] = None) -> List[Issue]:
        """List issues, optionally filtered"""
        results = self.issues
        if status:
            results = [i for i in results if i.status == status]
        if severity:
            results = [i for i in results if i.severity == severity]
        return results

    def apply_patch(self, patch: Patch):
        """Apply a patch"""
        patch.applied_at = datetime.now().isoformat()
        self.patches.append(patch)

    def get_patches(self, patch_type: Optional[str] = None) -> List[Patch]:
        """Get patches, optionally filtered by type"""
        if patch_type:
            return [p for p in self.patches if p.type == patch_type]
        return self.patches

    def run_health_check(self) -> HealthCheck:
        """Run a health check"""
        check = HealthCheck(
            timestamp=datetime.now().isoformat(),
            status="healthy"
        )

        # Simulate health checks
        check.checks = {
            "api": "healthy",
            "database": "healthy",
            "cache": "healthy",
            "storage": "healthy",
            "external_services": "healthy"
        }

        check.metrics = {
            "cpu_usage": 45.2,
            "memory_usage": 62.5,
            "disk_usage": 38.7,
            "response_time_ms": 120.5,
            "error_rate": 0.01
        }

        # Check for issues
        open_issues = self.list_issues(status="open")
        critical_issues = [i for i in open_issues if i.severity == "critical"]

        if critical_issues:
            check.status = "unhealthy"
            check.alerts.append(f"{len(critical_issues)} critical issues open")
        elif open_issues:
            check.status = "degraded"
            check.alerts.append(f"{len(open_issues)} issues open")

        self.health_history.append(check)
        return check

    def generate_maintenance_report(self) -> str:
        """Generate maintenance report"""
        report = f"""# Maintenance Report

Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Health Summary

"""

        if self.health_history:
            latest = self.health_history[-1]
            report += f"**Latest Status:** {latest.status.upper()}\n"
            report += f"**Last Check:** {latest.timestamp}\n\n"

            report += "### Metrics\n\n"
            for metric, value in latest.metrics.items():
                report += f"- **{metric}:** {value}\n"

            if latest.alerts:
                report += "\n### Alerts\n\n"
                for alert in latest.alerts:
                    report += f"- {alert}\n"

        report += f"\n## Issue Summary\n\n"
        report += f"**Total Issues:** {len(self.issues)}\n\n"

        by_status = {}
        for issue in self.issues:
            by_status[issue.status] = by_status.get(issue.status, 0) + 1

        report += "### By Status\n\n"
        for status, count in sorted(by_status.items()):
            report += f"- **{status}:** {count}\n"

        by_severity = {}
        for issue in self.issues:
            by_severity[issue.severity] = by_severity.get(issue.severity, 0) + 1

        report += "\n### By Severity\n\n"
        for severity, count in sorted(by_severity.items()):
            report += f"- **{severity}:** {count}\n"

        report += f"\n## Patch Summary\n\n"
        report += f"**Total Patches:** {len(self.patches)}\n\n"

        by_type = {}
        for patch in self.patches:
            by_type[patch.type] = by_type.get(patch.type, 0) + 1

        report += "### By Type\n\n"
        for patch_type, count in sorted(by_type.items()):
            report += f"- **{patch_type}:** {count}\n"

        return report
