"""
Security System Tests
Tests for security analysis, threat modeling, and compliance
"""

import pytest
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from security.core.threat_modeler import ThreatModeler, ThreatCategory
from security.core.compliance_checker import ComplianceChecker
from security.core.issue_tracker import SecurityIssueTracker, SecurityIssue
from security.core.reporter import SecurityReporter


class TestThreatModeler:
    """Test suite for ThreatModeler"""
    
    def test_threat_categories(self):
        """Test all STRIDE categories exist"""
        categories = [
            ThreatCategory.SPOOFING,
            ThreatCategory.TAMPERING,
            ThreatCategory.REPUDIATION,
            ThreatCategory.INFORMATION_DISCLOSURE,
            ThreatCategory.DENIAL_OF_SERVICE,
            ThreatCategory.ELEVATION_OF_PRIVILEGE
        ]
        
        assert len(categories) == 6
    
    def test_threat_pattern_loading(self):
        """Test threat patterns are loaded"""
        modeler = ThreatModeler()
        
        assert len(modeler.threat_patterns) == 6
        assert ThreatCategory.SPOOFING.value in modeler.threat_patterns
        assert ThreatCategory.TAMPERING.value in modeler.threat_patterns
    
    def test_risk_calculation(self):
        """Test risk level calculation"""
        modeler = ThreatModeler()
        
        # Critical severity, high likelihood
        risk = modeler._calculate_risk("critical", "high")
        assert risk == "critical"
        
        # High severity, medium likelihood
        risk = modeler._calculate_risk("high", "medium")
        assert risk == "high"
        
        # Low severity, low likelihood
        risk = modeler._calculate_risk("low", "low")
        assert risk == "low"


class TestComplianceChecker:
    """Test suite for ComplianceChecker"""
    
    def test_compliance_config_loading(self, security_config_dir):
        """Test compliance config loading"""
        checker = ComplianceChecker(str(security_config_dir))
        
        assert checker.config is not None
        assert "domains" in checker.config
    
    def test_domain_compliance(self, security_config_dir):
        """Test domain-specific compliance"""
        checker = ComplianceChecker(str(security_config_dir))
        
        # Finance domain should have PCI-DSS
        finance_domain = checker.config.get("domains", {}).get("finance", {})
        regulations = finance_domain.get("regulations", [])
        
        reg_names = [r.get("name") for r in regulations]
        assert "PCI-DSS" in reg_names


class TestSecurityIssueTracker:
    """Test suite for SecurityIssueTracker"""
    
    def test_add_issue(self, temp_products_dir, sample_project):
        """Test adding security issue"""
        tracker = SecurityIssueTracker(str(temp_products_dir))
        
        issue = tracker.add_issue(
            project=sample_project,
            title="SQL Injection in login",
            severity="critical",
            description="User input directly interpolated into SQL query",
            recommendation="Use parameterized queries",
            file="src/auth/login.py",
            line=42,
            owasp_category="A05",
            cwe="CWE-89",
            cvss="9.8"
        )
        
        assert issue is not None
        assert issue.issue_id == "SEC-001"
        assert issue.severity == "critical"
        assert issue.priority == "p0"
    
    def test_get_issues(self, temp_products_dir, sample_project):
        """Test getting issues"""
        tracker = SecurityIssueTracker(str(temp_products_dir))
        
        # Add issues
        tracker.add_issue(
            project=sample_project,
            title="Issue 1",
            severity="critical",
            description="Test",
            recommendation="Fix"
        )
        tracker.add_issue(
            project=sample_project,
            title="Issue 2",
            severity="medium",
            description="Test",
            recommendation="Fix"
        )
        
        # Get all issues
        issues = tracker.get_issues(sample_project)
        assert len(issues) == 2
        
        # Get by severity
        critical_issues = tracker.get_issues(sample_project, severity="critical")
        assert len(critical_issues) == 1
    
    def test_update_issue(self, temp_products_dir, sample_project):
        """Test updating issue"""
        tracker = SecurityIssueTracker(str(temp_products_dir))
        
        # Add issue
        issue = tracker.add_issue(
            project=sample_project,
            title="Test Issue",
            severity="high",
            description="Test",
            recommendation="Fix"
        )
        
        # Update issue
        updated = tracker.update_issue(
            sample_project,
            issue.issue_id,
            status="fixed",
            decision="fix_now"
        )
        
        assert updated is not None
        assert updated.status == "fixed"
        assert updated.decision == "fix_now"
        assert updated.resolved_at is not None
    
    def test_get_open_issues(self, temp_products_dir, sample_project):
        """Test getting open issues"""
        tracker = SecurityIssueTracker(str(temp_products_dir))
        
        # Add issues with different statuses
        issue1 = tracker.add_issue(
            project=sample_project,
            title="Open Issue",
            severity="high",
            description="Test",
            recommendation="Fix"
        )
        tracker.update_issue(sample_project, issue1.issue_id, status="fixed")
        
        tracker.add_issue(
            project=sample_project,
            title="Another Open Issue",
            severity="medium",
            description="Test",
            recommendation="Fix"
        )
        
        # Get open issues
        open_issues = tracker.get_open_issues(sample_project)
        assert len(open_issues) == 1
    
    def test_get_fix_now_issues(self, temp_products_dir, sample_project):
        """Test getting issues that should be fixed now"""
        tracker = SecurityIssueTracker(str(temp_products_dir))
        
        # Add critical issue (should be fix_now)
        tracker.add_issue(
            project=sample_project,
            title="Critical Issue",
            severity="critical",
            description="Test",
            recommendation="Fix"
        )
        
        # Add low issue (should be track_later)
        tracker.add_issue(
            project=sample_project,
            title="Low Issue",
            severity="low",
            description="Test",
            recommendation="Fix"
        )
        
        # Get fix now issues
        fix_now = tracker.get_fix_now_issues(sample_project)
        assert len(fix_now) == 1
        assert fix_now[0].severity == "critical"
    
    def test_get_summary(self, temp_products_dir, sample_project):
        """Test getting issue summary"""
        tracker = SecurityIssueTracker(str(temp_products_dir))
        
        # Add issues
        tracker.add_issue(
            project=sample_project,
            title="Critical Issue",
            severity="critical",
            description="Test",
            recommendation="Fix"
        )
        tracker.add_issue(
            project=sample_project,
            title="Medium Issue",
            severity="medium",
            description="Test",
            recommendation="Fix"
        )
        
        summary = tracker.get_summary(sample_project)
        
        assert summary["total"] == 2
        assert summary["by_severity"]["critical"] == 1
        assert summary["by_severity"]["medium"] == 1
        assert summary["fix_now"] == 1
        assert summary["track_later"] == 1
    
    def test_severity_to_priority(self):
        """Test severity to priority conversion"""
        tracker = SecurityIssueTracker()
        
        assert tracker._severity_to_priority("critical") == "p0"
        assert tracker._severity_to_priority("high") == "p1"
        assert tracker._severity_to_priority("medium") == "p2"
        assert tracker._severity_to_priority("low") == "p3"
        assert tracker._severity_to_priority("info") == "p3"


class TestSecurityIssue:
    """Test suite for SecurityIssue dataclass"""
    
    def test_issue_creation(self):
        """Test SecurityIssue creation"""
        issue = SecurityIssue(
            issue_id="SEC-001",
            title="Test Issue",
            severity="high",
            priority="p1",
            owasp_category="A05",
            cwe="CWE-89",
            cvss="7.5",
            file="test.py",
            line=10,
            description="Test description",
            recommendation="Test recommendation",
            fix_effort="medium",
            fix_now=True,
            track_later=False,
            compliance_impact=["PCI-DSS"],
            status="open",
            decision=None,
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
            resolved_at=None
        )
        
        assert issue.issue_id == "SEC-001"
        assert issue.severity == "high"
        assert issue.fix_now is True
    
    def test_issue_serialization(self):
        """Test SecurityIssue serialization"""
        issue = SecurityIssue(
            issue_id="SEC-001",
            title="Test Issue",
            severity="high",
            priority="p1",
            owasp_category=None,
            cwe=None,
            cvss=None,
            file=None,
            line=None,
            description="Test",
            recommendation="Fix",
            fix_effort="medium",
            fix_now=True,
            track_later=False,
            compliance_impact=[],
            status="open",
            decision=None,
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
            resolved_at=None
        )
        
        data = issue.to_dict()
        assert data["issue_id"] == "SEC-001"
        assert data["severity"] == "high"
