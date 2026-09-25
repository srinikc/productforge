"""
Security Issue Tracker
Track and manage security issues with severity and priority
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class SecurityIssue:
    """Security issue"""
    issue_id: str
    title: str
    severity: str  # critical, high, medium, low, info
    priority: str  # p0, p1, p2, p3
    owasp_category: Optional[str]
    cwe: Optional[str]
    cvss: Optional[str]
    file: Optional[str]
    line: Optional[int]
    description: str
    recommendation: str
    fix_effort: str  # low, medium, high
    fix_now: bool
    track_later: bool
    compliance_impact: List[str]
    status: str  # open, in_progress, fixed, deferred, accepted
    decision: Optional[str]  # fix_now, track_later, accept_risk
    created_at: str
    updated_at: str
    resolved_at: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SecurityIssueTracker:
    """
    Security issue tracker.
    
    Tracks security issues with severity, priority, and fix decisions.
    """
    
    def __init__(self, products_dir: str = "products"):
        """
        Initialize issue tracker.
        
        Args:
            products_dir: Path to products directory
        """
        self.products_dir = Path(products_dir)
    
    def _get_issues_path(self, project: str) -> Path:
        """Get issues file path for project"""
        return self.products_dir / project / "security" / "security-issues.json"
    
    def _load_issues(self, project: str) -> List[Dict[str, Any]]:
        """Load issues for a project"""
        issues_path = self._get_issues_path(project)
        if issues_path.exists():
            with open(issues_path, 'r') as f:
                return json.load(f)
        return []
    
    def _save_issues(self, project: str, issues: List[Dict[str, Any]]):
        """Save issues for a project"""
        issues_path = self._get_issues_path(project)
        issues_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Atomic write
        temp_path = issues_path.with_suffix('.tmp')
        try:
            with open(temp_path, 'w') as f:
                json.dump(issues, f, indent=2)
            temp_path.replace(issues_path)
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise Exception(f"Failed to save issues: {e}")
    
    def add_issue(
        self,
        project: str,
        title: str,
        severity: str,
        description: str,
        recommendation: str,
        file: Optional[str] = None,
        line: Optional[int] = None,
        owasp_category: Optional[str] = None,
        cwe: Optional[str] = None,
        cvss: Optional[str] = None,
        fix_effort: str = "medium",
        compliance_impact: Optional[List[str]] = None
    ) -> SecurityIssue:
        """
        Add a new security issue.
        
        Args:
            project: Project name
            title: Issue title
            severity: Issue severity
            description: Issue description
            recommendation: Fix recommendation
            file: Affected file
            line: Affected line
            owasp_category: OWASP category
            cwe: CWE identifier
            cvss: CVSS score
            fix_effort: Fix effort (low/medium/high)
            compliance_impact: Affected compliance regulations
            
        Returns:
            Created SecurityIssue
        """
        issues = self._load_issues(project)
        
        # Generate issue ID
        issue_id = f"SEC-{len(issues) + 1:03d}"
        
        # Determine priority based on severity
        priority = self._severity_to_priority(severity)
        
        # Determine fix decision
        fix_now = severity in ["critical", "high"]
        track_later = severity in ["medium", "low", "info"]
        
        now = datetime.now().isoformat()
        
        issue = SecurityIssue(
            issue_id=issue_id,
            title=title,
            severity=severity,
            priority=priority,
            owasp_category=owasp_category,
            cwe=cwe,
            cvss=cvss,
            file=file,
            line=line,
            description=description,
            recommendation=recommendation,
            fix_effort=fix_effort,
            fix_now=fix_now,
            track_later=track_later,
            compliance_impact=compliance_impact or [],
            status="open",
            decision=None,
            created_at=now,
            updated_at=now,
            resolved_at=None
        )
        
        issues.append(issue.to_dict())
        self._save_issues(project, issues)
        
        return issue
    
    def update_issue(
        self,
        project: str,
        issue_id: str,
        status: Optional[str] = None,
        decision: Optional[str] = None
    ) -> Optional[SecurityIssue]:
        """
        Update an existing security issue.
        
        Args:
            project: Project name
            issue_id: Issue ID
            status: New status
            decision: User decision
            
        Returns:
            Updated SecurityIssue or None
        """
        issues = self._load_issues(project)
        
        for i, issue_data in enumerate(issues):
            if issue_data.get("issue_id") == issue_id:
                if status:
                    issues[i]["status"] = status
                if decision:
                    issues[i]["decision"] = decision
                    if decision == "fix_now":
                        issues[i]["fix_now"] = True
                        issues[i]["track_later"] = False
                    elif decision == "track_later":
                        issues[i]["fix_now"] = False
                        issues[i]["track_later"] = True
                    elif decision == "accept_risk":
                        issues[i]["status"] = "accepted"
                
                issues[i]["updated_at"] = datetime.now().isoformat()
                if status in ["fixed", "accepted"]:
                    issues[i]["resolved_at"] = datetime.now().isoformat()
                
                self._save_issues(project, issues)
                return SecurityIssue(**issues[i])
        
        return None
    
    def get_issues(
        self,
        project: str,
        status: Optional[str] = None,
        severity: Optional[str] = None
    ) -> List[SecurityIssue]:
        """
        Get issues for a project.
        
        Args:
            project: Project name
            status: Filter by status
            severity: Filter by severity
            
        Returns:
            List of SecurityIssue
        """
        issues = self._load_issues(project)
        
        filtered = []
        for issue_data in issues:
            if status and issue_data.get("status") != status:
                continue
            if severity and issue_data.get("severity") != severity:
                continue
            filtered.append(SecurityIssue(**issue_data))
        
        return filtered
    
    def get_open_issues(self, project: str) -> List[SecurityIssue]:
        """Get all open issues for a project"""
        return self.get_issues(project, status="open")
    
    def get_fix_now_issues(self, project: str) -> List[SecurityIssue]:
        """Get issues that should be fixed now"""
        issues = self.get_issues(project, status="open")
        return [i for i in issues if i.fix_now]
    
    def get_track_later_issues(self, project: str) -> List[SecurityIssue]:
        """Get issues that can be tracked for later"""
        issues = self.get_issues(project, status="open")
        return [i for i in issues if i.track_later]
    
    def get_summary(self, project: str) -> Dict[str, Any]:
        """
        Get issue summary for a project.
        
        Args:
            project: Project name
            
        Returns:
            Issue summary
        """
        issues = self._load_issues(project)
        
        summary = {
            "total": len(issues),
            "by_status": {},
            "by_severity": {},
            "by_priority": {},
            "fix_now": 0,
            "track_later": 0
        }
        
        for issue_data in issues:
            status = issue_data.get("status", "unknown")
            severity = issue_data.get("severity", "unknown")
            priority = issue_data.get("priority", "unknown")
            
            summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
            summary["by_severity"][severity] = summary["by_severity"].get(severity, 0) + 1
            summary["by_priority"][priority] = summary["by_priority"].get(priority, 0) + 1
            
            if issue_data.get("fix_now"):
                summary["fix_now"] += 1
            if issue_data.get("track_later"):
                summary["track_later"] += 1
        
        return summary
    
    def _severity_to_priority(self, severity: str) -> str:
        """Convert severity to priority"""
        mapping = {
            "critical": "p0",
            "high": "p1",
            "medium": "p2",
            "low": "p3",
            "info": "p3"
        }
        return mapping.get(severity, "p3")
    
    def generate_markdown_report(self, project: str, output_path: str) -> str:
        """
        Generate markdown report of all issues.
        
        Args:
            project: Project name
            output_path: Path to output file
            
        Returns:
            Generated report
        """
        issues = self._load_issues(project)
        summary = self.get_summary(project)
        
        report = f"""# Security Issues Report

## Project: {project}

## Summary

| Metric | Value |
|--------|-------|
| Total Issues | {summary['total']} |
| Fix Now | {summary['fix_now']} |
| Track Later | {summary['track_later']} |

### By Status

"""
        
        for status, count in summary.get("by_status", {}).items():
            report += f"- **{status}**: {count}\n"
        
        report += "\n### By Severity\n\n"
        
        for severity, count in summary.get("by_severity", {}).items():
            report += f"- **{severity}**: {count}\n"
        
        report += "\n## Issues\n\n"
        
        for issue_data in issues:
            issue = SecurityIssue(**issue_data)
            report += f"""### {issue.issue_id}: {issue.title}

- **Severity**: {issue.severity}
- **Priority**: {issue.priority}
- **Status**: {issue.status}
- **Decision**: {issue.decision or "Pending"}
- **File**: {issue.file or "N/A"}:{issue.line or "N/A"}

**Description**: {issue.description}

**Recommendation**: {issue.recommendation}

---
"""
        
        # Write report
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(report)
        
        return report
