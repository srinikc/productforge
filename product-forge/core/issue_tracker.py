"""Issue Tracker - Structured issue tracking for security, NFR, and test issues.

Provides:
- Security issues with severity, fix recommendations, CWE
- NFR issues with current/target values
- Test issues with fix recommendations
- Fix loop: issues → human prioritize → route to agent → fix → re-test
"""
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path


@dataclass
class Issue:
    """A structured issue."""
    id: str
    title: str
    description: str
    severity: str  # critical, high, medium, low
    category: str  # security, nfr, test, code, design
    file: str = ""
    line: int = 0
    fix_recommendation: str = ""
    fix_effort: str = "medium"  # small, medium, large
    status: str = "open"  # open, in-progress, fixed, accepted, deferred
    assigned_to: str = ""
    cwe: str = ""  # for security issues
    current_value: str = ""  # for NFR issues
    target_value: str = ""  # for NFR issues
    test_type: str = ""  # for test issues (unit, integration, e2e)
    created_at: str = ""
    updated_at: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "category": self.category,
            "file": self.file,
            "line": self.line,
            "fix_recommendation": self.fix_recommendation,
            "fix_effort": self.fix_effort,
            "status": self.status,
            "assigned_to": self.assigned_to,
            "cwe": self.cwe,
            "current_value": self.current_value,
            "target_value": self.target_value,
            "test_type": self.test_type,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class IssueList:
    """A list of issues with metadata."""
    project: str
    stage: str
    agent: str
    issues: List[Issue] = field(default_factory=list)
    total_count: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    created_at: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "project": self.project,
            "stage": self.stage,
            "agent": self.agent,
            "issues": [i.to_dict() for i in self.issues],
            "total_count": self.total_count,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "medium_count": self.medium_count,
            "low_count": self.low_count,
            "created_at": self.created_at,
        }


def create_issue(issue_id: str, title: str, description: str, severity: str, 
                 category: str, **kwargs) -> Issue:
    """Create a new issue."""
    return Issue(
        id=issue_id,
        title=title,
        description=description,
        severity=severity,
        category=category,
        file=kwargs.get("file", ""),
        line=kwargs.get("line", 0),
        fix_recommendation=kwargs.get("fix_recommendation", ""),
        fix_effort=kwargs.get("fix_effort", "medium"),
        status="open",
        assigned_to=kwargs.get("assigned_to", ""),
        cwe=kwargs.get("cwe", ""),
        current_value=kwargs.get("current_value", ""),
        target_value=kwargs.get("target_value", ""),
        test_type=kwargs.get("test_type", ""),
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
    )


def create_issue_list(project: str, stage: str, agent: str) -> IssueList:
    """Create a new issue list."""
    return IssueList(
        project=project,
        stage=stage,
        agent=agent,
        created_at=datetime.now().isoformat(),
    )


def add_issue(issue_list: IssueList, issue: Issue) -> IssueList:
    """Add an issue to a list and update counts."""
    issue_list.issues.append(issue)
    issue_list.total_count = len(issue_list.issues)
    
    if issue.severity == "critical":
        issue_list.critical_count += 1
    elif issue.severity == "high":
        issue_list.high_count += 1
    elif issue.severity == "medium":
        issue_list.medium_count += 1
    elif issue.severity == "low":
        issue_list.low_count += 1
    
    return issue_list


def get_issues_by_severity(issue_list: IssueList, severity: str) -> List[Issue]:
    """Get issues filtered by severity."""
    return [i for i in issue_list.issues if i.severity == severity]


def get_issues_by_status(issue_list: IssueList, status: str) -> List[Issue]:
    """Get issues filtered by status."""
    return [i for i in issue_list.issues if i.status == status]


def get_fixable_issues(issue_list: IssueList) -> List[Issue]:
    """Get issues that can be fixed (open, not deferred)."""
    return [i for i in issue_list.issues if i.status == "open" and i.fix_recommendation]


def prioritize_issues(issue_list: IssueList) -> List[Issue]:
    """Prioritize issues by severity and fix effort."""
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    effort_order = {"small": 0, "medium": 1, "large": 2}
    
    sorted_issues = sorted(
        issue_list.issues,
        key=lambda i: (severity_order.get(i.severity, 4), effort_order.get(i.fix_effort, 2))
    )
    
    return sorted_issues


def save_issue_list(issue_list: IssueList, products_dir: str = "products") -> str:
    """Save issue list to file."""
    project_dir = os.path.join(products_dir, issue_list.project)
    os.makedirs(project_dir, exist_ok=True)
    
    issues_dir = os.path.join(project_dir, "issues")
    os.makedirs(issues_dir, exist_ok=True)
    
    filename = f"{issue_list.stage}-{issue_list.agent}-issues.json"
    filepath = os.path.join(issues_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(issue_list.to_dict(), f, indent=2, ensure_ascii=False)
    
    return filepath


def load_issue_list(project: str, stage: str, agent: str, products_dir: str = "products") -> Optional[IssueList]:
    """Load issue list from file."""
    filepath = os.path.join(products_dir, project, "issues", f"{stage}-{agent}-issues.json")
    
    if not os.path.exists(filepath):
        return None
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    issue_list = IssueList(
        project=data.get("project", project),
        stage=data.get("stage", stage),
        agent=data.get("agent", agent),
        created_at=data.get("created_at", ""),
    )
    
    for issue_data in data.get("issues", []):
        issue = Issue(
            id=issue_data.get("id", ""),
            title=issue_data.get("title", ""),
            description=issue_data.get("description", ""),
            severity=issue_data.get("severity", "medium"),
            category=issue_data.get("category", ""),
            file=issue_data.get("file", ""),
            line=issue_data.get("line", 0),
            fix_recommendation=issue_data.get("fix_recommendation", ""),
            fix_effort=issue_data.get("fix_effort", "medium"),
            status=issue_data.get("status", "open"),
            assigned_to=issue_data.get("assigned_to", ""),
            cwe=issue_data.get("cwe", ""),
            current_value=issue_data.get("current_value", ""),
            target_value=issue_data.get("target_value", ""),
            test_type=issue_data.get("test_type", ""),
            created_at=issue_data.get("created_at", ""),
            updated_at=issue_data.get("updated_at", ""),
        )
        add_issue(issue_list, issue)
    
    return issue_list


def generate_issue_report(issue_list: IssueList) -> str:
    """Generate an issue report."""
    prioritized = prioritize_issues(issue_list)
    
    report = f"""# Issue Report: {issue_list.stage}/{issue_list.agent}

## Project: {issue_list.project}

## Summary
- **Total Issues:** {issue_list.total_count}
- **Critical:** {issue_list.critical_count}
- **High:** {issue_list.high_count}
- **Medium:** {issue_list.medium_count}
- **Low:** {issue_list.low_count}

## Prioritized Issues

| ID | Severity | Title | Fix Effort | Status |
|----|----------|-------|------------|--------|
"""
    
    for issue in prioritized:
        report += f"| {issue.id} | {issue.severity} | {issue.title} | {issue.fix_effort} | {issue.status} |\n"
    
    report += "\n## Detailed Issues\n\n"
    
    for issue in prioritized:
        report += f"### {issue.id}: {issue.title}\n\n"
        report += f"- **Severity:** {issue.severity}\n"
        report += f"- **Category:** {issue.category}\n"
        if issue.file:
            report += f"- **File:** {issue.file}:{issue.line}\n"
        if issue.fix_recommendation:
            report += f"- **Fix:** {issue.fix_recommendation}\n"
        if issue.cwe:
            report += f"- **CWE:** {issue.cwe}\n"
        if issue.current_value:
            report += f"- **Current:** {issue.current_value}\n"
        if issue.target_value:
            report += f"- **Target:** {issue.target_value}\n"
        report += "\n"
    
    return report


# Convenience functions for common issue types

def create_security_issue(issue_id: str, title: str, description: str, severity: str,
                          file: str = "", line: int = 0, cwe: str = "",
                          fix_recommendation: str = "", fix_effort: str = "medium") -> Issue:
    """Create a security issue."""
    return create_issue(
        issue_id=issue_id,
        title=title,
        description=description,
        severity=severity,
        category="security",
        file=file,
        line=line,
        cwe=cwe,
        fix_recommendation=fix_recommendation,
        fix_effort=fix_effort,
    )


def create_nfr_issue(issue_id: str, title: str, description: str, severity: str,
                     category: str, current_value: str = "", target_value: str = "",
                     fix_recommendation: str = "", fix_effort: str = "medium") -> Issue:
    """Create an NFR issue."""
    return create_issue(
        issue_id=issue_id,
        title=title,
        description=description,
        severity=severity,
        category=category,
        current_value=current_value,
        target_value=target_value,
        fix_recommendation=fix_recommendation,
        fix_effort=fix_effort,
    )


def create_test_issue(issue_id: str, title: str, description: str, severity: str,
                      test_type: str = "", file: str = "",
                      fix_recommendation: str = "", fix_effort: str = "medium") -> Issue:
    """Create a test issue."""
    return create_issue(
        issue_id=issue_id,
        title=title,
        description=description,
        severity=severity,
        category="test",
        test_type=test_type,
        file=file,
        fix_recommendation=fix_recommendation,
        fix_effort=fix_effort,
    )


if __name__ == "__main__":
    # Test issue tracker
    issue_list = create_issue_list("test-project", "security", "security")
    
    # Add some test issues
    add_issue(issue_list, create_security_issue(
        "SEC-001", "SQL Injection", "User input not sanitized in query",
        "critical", "api/users.py", 42, "CWE-89",
        "Use parameterized queries", "small"
    ))
    
    add_issue(issue_list, create_security_issue(
        "SEC-002", "Hardcoded Secret", "API key hardcoded in source",
        "high", "config.py", 10, "CWE-798",
        "Move to environment variable", "small"
    ))
    
    print(f"Issues: {issue_list.total_count}")
    print(f"Critical: {issue_list.critical_count}")
    print(f"High: {issue_list.high_count}")
    
    report = generate_issue_report(issue_list)
    print(f"\nReport generated ({len(report)} chars)")
