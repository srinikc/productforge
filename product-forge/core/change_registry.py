"""
Change Registry
Tracks changes, performs impact analysis, and manages change requests
"""
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field, asdict


@dataclass
class ChangeRequest:
    """A change request"""
    id: str
    title: str
    description: str
    type: str  # feature, bugfix, refactor, security, performance
    priority: str  # critical, high, medium, low
    status: str  # proposed, approved, in_progress, completed, rejected
    requester: str
    created_at: str
    files_affected: List[str] = field(default_factory=list)
    components_affected: List[str] = field(default_factory=list)
    estimated_effort: str = ""  # hours, days, weeks
    risk_level: str = "low"  # low, medium, high
    approved_by: Optional[str] = None
    completed_at: Optional[str] = None
    rollback_plan: str = ""


@dataclass
class ImpactAnalysis:
    """Impact analysis for a change"""
    change_id: str
    affected_files: List[str] = field(default_factory=list)
    affected_components: List[str] = field(default_factory=list)
    affected_features: List[str] = field(default_factory=list)
    affected_tests: List[str] = field(default_factory=list)
    affected_documentation: List[str] = field(default_factory=list)
    breaking_changes: List[str] = field(default_factory=list)
    risk_level: str = "low"
    estimated_effort: str = ""
    recommendations: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)


class ChangeRegistry:
    """Registry for tracking changes and impact analysis"""

    def __init__(self, products_dir: str = "products"):
        self.products_dir = Path(products_dir)
        self.changes: List[ChangeRequest] = []
        self.impact_cache: Dict[str, ImpactAnalysis] = {}

    def add_change(self, change: ChangeRequest):
        """Add a change request"""
        self.changes.append(change)

    def get_change(self, change_id: str) -> Optional[ChangeRequest]:
        """Get a change by ID"""
        for change in self.changes:
            if change.id == change_id:
                return change
        return None

    def update_change(self, change_id: str, **kwargs) -> Optional[ChangeRequest]:
        """Update a change"""
        change = self.get_change(change_id)
        if change:
            for key, value in kwargs.items():
                if hasattr(change, key):
                    setattr(change, key, value)
        return change

    def list_changes(self, status: Optional[str] = None,
                     priority: Optional[str] = None) -> List[ChangeRequest]:
        """List changes, optionally filtered"""
        results = self.changes
        if status:
            results = [c for c in results if c.status == status]
        if priority:
            results = [c for c in results if c.priority == priority]
        return results

    def analyze_impact(self, change: ChangeRequest) -> ImpactAnalysis:
        """Analyze the impact of a change"""
        analysis = ImpactAnalysis(change_id=change.id)

        # Determine affected areas based on change type and files
        analysis.affected_files = change.files_affected
        analysis.affected_components = change.components_affected

        # Analyze risk level
        analysis.risk_level = self._assess_risk(change)

        # Identify breaking changes
        analysis.breaking_changes = self._identify_breaking_changes(change)

        # Generate recommendations
        analysis.recommendations = self._generate_recommendations(change)

        # Cache the analysis
        self.impact_cache[change.id] = analysis

        return analysis

    def _assess_risk(self, change: ChangeRequest) -> str:
        """Assess risk level of a change"""
        risk_score = 0

        # High priority changes are higher risk
        if change.priority == "critical":
            risk_score += 3
        elif change.priority == "high":
            risk_score += 2
        elif change.priority == "medium":
            risk_score += 1

        # More files affected = higher risk
        if len(change.files_affected) > 20:
            risk_score += 3
        elif len(change.files_affected) > 10:
            risk_score += 2
        elif len(change.files_affected) > 5:
            risk_score += 1

        # Security changes are higher risk
        if change.type == "security":
            risk_score += 2

        # Determine risk level
        if risk_score >= 5:
            return "high"
        elif risk_score >= 3:
            return "medium"
        else:
            return "low"

    def _identify_breaking_changes(self, change: ChangeRequest) -> List[str]:
        """Identify potential breaking changes"""
        breaking = []

        # Check for API changes
        for file in change.files_affected:
            if "api" in file.lower() or "interface" in file.lower():
                breaking.append(f"Potential API change in {file}")

        # Check for database changes
        for file in change.files_affected:
            if "schema" in file.lower() or "migration" in file.lower():
                breaking.append(f"Database schema change in {file}")

        # Check for configuration changes
        for file in change.files_affected:
            if "config" in file.lower() or "settings" in file.lower():
                breaking.append(f"Configuration change in {file}")

        return breaking

    def _generate_recommendations(self, change: ChangeRequest) -> List[str]:
        """Generate recommendations for a change"""
        recommendations = []

        # High-risk changes need additional review
        if change.risk_level == "high":
            recommendations.append("Require additional code review")
            recommendations.append("Deploy to staging first")
            recommendations.append("Have rollback plan ready")

        # Security changes need special handling
        if change.type == "security":
            recommendations.append("Security review required")
            recommendations.append("Run security scans")
            recommendations.append("Test for vulnerabilities")

        # Large changes need phased rollout
        if len(change.files_affected) > 10:
            recommendations.append("Consider phased rollout")
            recommendations.append("Add feature flag for gradual deployment")

        # Database changes need migration plan
        for file in change.files_affected:
            if "migration" in file.lower() or "schema" in file.lower():
                recommendations.append("Create database migration plan")
                recommendations.append("Test rollback procedure")
                break

        return recommendations

    def generate_change_report(self) -> str:
        """Generate change report"""
        report = f"""# Change Registry Report

Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Summary

**Total Changes:** {len(self.changes)}

"""
        # Count by status
        by_status = {}
        for change in self.changes:
            by_status[change.status] = by_status.get(change.status, 0) + 1

        report += "### By Status\n\n"
        for status, count in sorted(by_status.items()):
            report += f"- **{status}:** {count}\n"

        # Count by priority
        by_priority = {}
        for change in self.changes:
            by_priority[change.priority] = by_priority.get(change.priority, 0) + 1

        report += "\n### By Priority\n\n"
        for priority, count in sorted(by_priority.items()):
            report += f"- **{priority}:** {count}\n"

        # Count by type
        by_type = {}
        for change in self.changes:
            by_type[change.type] = by_type.get(change.type, 0) + 1

        report += "\n### By Type\n\n"
        for change_type, count in sorted(by_type.items()):
            report += f"- **{change_type}:** {count}\n"

        # Recent changes
        report += "\n## Recent Changes\n\n"
        recent = sorted(self.changes, key=lambda c: c.created_at, reverse=True)[:10]
        for change in recent:
            report += f"### {change.id}: {change.title}\n\n"
            report += f"- **Type:** {change.type}\n"
            report += f"- **Priority:** {change.priority}\n"
            report += f"- **Status:** {change.status}\n"
            report += f"- **Risk Level:** {change.risk_level}\n"
            report += f"- **Created:** {change.created_at}\n"
            if change.estimated_effort:
                report += f"- **Estimated Effort:** {change.estimated_effort}\n"
            report += f"\n{change.description}\n\n"
            if change.files_affected:
                report += f"**Files Affected:** {len(change.files_affected)}\n\n"

        return report
