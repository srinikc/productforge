"""
Security Reporter
Generate security reports and summaries
"""

from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime


class SecurityReporter:
    """
    Security report generator.
    
    Generates various security reports and summaries.
    """
    
    def __init__(self):
        """Initialize security reporter"""
        pass
    
    def generate_security_architecture_report(
        self,
        architecture_content: str,
        findings: List[Dict[str, Any]],
        output_path: str
    ) -> str:
        """
        Generate security architecture report.
        
        Args:
            architecture_content: Architecture document content
            findings: Security findings
            output_path: Path to output file
            
        Returns:
            Generated report
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        report = f"""# Security Architecture Report

## Summary

| Metric | Value |
|--------|-------|
| Security Findings | {len(findings)} |

## Security Controls Analysis

### Identified Security Patterns

"""
        
        # Analyze architecture for security patterns
        security_patterns = {
            "Authentication": ["auth", "login", "session", "token"],
            "Authorization": ["rbac", "permission", "role", "access"],
            "Encryption": ["encrypt", "tls", "ssl", "https", "aes"],
            "Input Validation": ["validat", "sanitiz", "escape"],
            "Error Handling": ["error", "exception", "catch"],
            "Logging": ["log", "audit", "trail"]
        }
        
        for pattern_name, keywords in security_patterns.items():
            found = any(kw.lower() in architecture_content.lower() for kw in keywords)
            status = "Present" if found else "Missing"
            report += f"- **{pattern_name}**: {status}\n"
        
        report += "\n## Security Recommendations\n\n"
        
        for finding in findings:
            report += f"- [{finding.get('severity', 'medium').upper()}] {finding.get('description', 'No description')}\n"
        
        report += f"\n## Report Generated\n\n- **Timestamp**: {datetime.now().isoformat()}\n"
        
        # Write report
        with open(output_path, 'w') as f:
            f.write(report)
        
        return report
    
    def generate_vulnerability_report(
        self,
        project: str,
        findings: List[Dict[str, Any]],
        output_path: str
    ) -> str:
        """
        Generate vulnerability assessment report.
        
        Args:
            project: Project name
            findings: Security findings
            output_path: Path to output file
            
        Returns:
            Generated report
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Count by severity
        severity_counts = {}
        for finding in findings:
            severity = finding.get("severity", "info")
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        report = f"""# Vulnerability Assessment Report

## Project: {project}

## Summary

| Severity | Count |
|----------|-------|
| Critical | {severity_counts.get('critical', 0)} |
| High | {severity_counts.get('high', 0)} |
| Medium | {severity_counts.get('medium', 0)} |
| Low | {severity_counts.get('low', 0)} |
| Info | {severity_counts.get('info', 0)} |
| **Total** | **{len(findings)}** |

## Findings

| ID | Type | Severity | Description |
|----|------|----------|-------------|
"""
        
        for i, finding in enumerate(findings, 1):
            report += f"| VULN-{i:03d} | {finding.get('type', 'Unknown')} | {finding.get('severity', 'info')} | {finding.get('description', 'No description')} |\n"
        
        report += "\n## Recommendations\n\n"
        
        if severity_counts.get('critical', 0) > 0:
            report += "### Critical Priority\n"
            report += "- Address all critical vulnerabilities immediately\n"
            report += "- Consider pausing deployment until resolved\n\n"
        
        if severity_counts.get('high', 0) > 0:
            report += "### High Priority\n"
            report += "- Address high severity issues within 1-2 weeks\n"
            report += "- Include in next sprint planning\n\n"
        
        report += f"\n## Report Generated\n\n- **Timestamp**: {datetime.now().isoformat()}\n"
        
        # Write report
        with open(output_path, 'w') as f:
            f.write(report)
        
        return report
    
    def generate_summary(
        self,
        project: str,
        phase_results: List[Dict[str, Any]],
        output_path: str
    ) -> str:
        """
        Generate security summary report.
        
        Args:
            project: Project name
            phase_results: Results from all phases
            output_path: Path to output file
            
        Returns:
            Generated report
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Aggregate findings
        total_findings = 0
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        
        for phase in phase_results:
            total_findings += phase.get("findings_count", 0)
            for severity in severity_counts:
                severity_counts[severity] += phase.get(f"{severity}_count", 0)
        
        report = f"""# Security Summary Report

## Project: {project}

## Executive Summary

| Metric | Value |
|--------|-------|
| Total Phases Completed | {len(phase_results)} |
| Total Findings | {total_findings} |
| Critical Findings | {severity_counts['critical']} |
| High Findings | {severity_counts['high']} |
| Medium Findings | {severity_counts['medium']} |
| Low Findings | {severity_counts['low']} |
| Informational | {severity_counts['info']} |

## Risk Assessment

"""
        
        # Risk assessment
        if severity_counts['critical'] > 0:
            risk_level = "CRITICAL"
            risk_description = "Critical vulnerabilities detected. Immediate action required."
        elif severity_counts['high'] > 0:
            risk_level = "HIGH"
            risk_description = "High severity vulnerabilities detected. Action required within 1-2 weeks."
        elif severity_counts['medium'] > 0:
            risk_level = "MEDIUM"
            risk_description = "Medium severity vulnerabilities detected. Action recommended."
        else:
            risk_level = "LOW"
            risk_description = "No significant vulnerabilities detected."
        
        report += f"""| Risk Level | {risk_level} |
|------------|---------|
| Description | {risk_description} |

## Phase Results

| Phase | Status | Findings |
|-------|--------|----------|
"""
        
        for phase in phase_results:
            status = phase.get("status", "unknown")
            findings = phase.get("findings_count", 0)
            report += f"| {phase.get('phase', 'Unknown')} | {status} | {findings} |\n"
        
        report += f"\n## Report Generated\n\n- **Timestamp**: {datetime.now().isoformat()}\n"
        
        # Write report
        with open(output_path, 'w') as f:
            f.write(report)
        
        return report
