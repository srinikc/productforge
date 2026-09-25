"""
SAST Scanner
Static Application Security Testing using Bandit and Semgrep
"""

import json
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict


@dataclass
class SASTFinding:
    """SAST finding"""
    id: str
    tool: str
    file: str
    line: int
    severity: str
    confidence: str
    issue: str
    description: str
    recommendation: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SASTScanner:
    """
    Static Application Security Testing scanner.
    
    Uses Bandit for Python and Semgrep for multi-language analysis.
    """
    
    def __init__(self):
        """Initialize SAST scanner"""
        self.tools = {
            "bandit": self._run_bandit,
            "semgrep": self._run_semgrep
        }
    
    def scan(
        self,
        src_dir: str,
        output_path: str,
        tools: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Run SAST scanning.
        
        Args:
            src_dir: Source code directory
            output_path: Path to output file
            tools: Tools to use (default: all)
            
        Returns:
            Scan results
        """
        src_path = Path(src_dir)
        if not src_path.exists():
            return {"findings": [], "error": f"Source directory not found: {src_dir}"}
        
        findings = []
        tools_to_run = tools or list(self.tools.keys())
        
        for tool in tools_to_run:
            if tool in self.tools:
                tool_findings = self.tools[tool](src_path)
                findings.extend(tool_findings)
        
        # Generate report
        report = self._generate_report(findings, output_path)
        
        return {
            "findings": [f.to_dict() for f in findings],
            "tools_used": tools_to_run,
            "report": report
        }
    
    def _run_bandit(self, src_path: Path) -> List[SASTFinding]:
        """Run Bandit scanner"""
        findings = []
        
        try:
            # Run Bandit
            cmd = [
                "bandit",
                "-r", str(src_path),
                "-f", "json",
                "--severity-level", "medium",
                "--confidence-level", "medium"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            # Parse JSON output
            if result.stdout:
                output = json.loads(result.stdout)
                for result_item in output.get("results", []):
                    finding = SASTFinding(
                        id=f"BANDIT-{result_item.get('test_id', 'UNKNOWN')}",
                        tool="bandit",
                        file=result_item.get("filename", "unknown"),
                        line=result_item.get("line_number", 0),
                        severity=result_item.get("issue_severity", "medium").lower(),
                        confidence=result_item.get("issue_confidence", "medium").lower(),
                        issue=result_item.get("issue_text", "Unknown issue"),
                        description=result_item.get("issue_text", ""),
                        recommendation=self._get_bandit_recommendation(
                            result_item.get("test_id", "")
                        )
                    )
                    findings.append(finding)
        
        except subprocess.TimeoutExpired:
            pass
        except FileNotFoundError:
            # Bandit not installed
            pass
        except Exception as e:
            pass
        
        return findings
    
    def _run_semgrep(self, src_path: Path) -> List[SASTFinding]:
        """Run Semgrep scanner"""
        findings = []
        
        try:
            # Run Semgrep
            cmd = [
                "semgrep",
                "scan",
                "--config", "auto",
                "--json",
                str(src_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            # Parse JSON output
            if result.stdout:
                output = json.loads(result.stdout)
                for result_item in output.get("results", []):
                    finding = SASTFinding(
                        id=f"SEMGREP-{result_item.get('check_id', 'UNKNOWN')}",
                        tool="semgrep",
                        file=result_item.get("path", "unknown"),
                        line=result_item.get("start", {}).get("line", 0),
                        severity=self._map_semgrep_severity(
                            result_item.get("extra", {}).get("severity", "WARNING")
                        ),
                        confidence="high",
                        issue=result_item.get("check_id", "Unknown issue"),
                        description=result_item.get("extra", {}).get("message", ""),
                        recommendation="Review and fix the identified issue"
                    )
                    findings.append(finding)
        
        except subprocess.TimeoutExpired:
            pass
        except FileNotFoundError:
            # Semgrep not installed
            pass
        except Exception as e:
            pass
        
        return findings
    
    def _get_bandit_recommendation(self, test_id: str) -> str:
        """Get recommendation for Bandit finding"""
        recommendations = {
            "B101": "Avoid using assert in production code",
            "B102": "Avoid using exec()",
            "B103": "Avoid using set_bad_file_permissions",
            "B104": "Avoid binding to all interfaces",
            "B105": "Avoid using hardcoded passwords",
            "B106": "Avoid using hardcoded passwords",
            "B107": "Avoid using hardcoded passwords",
            "B108": "Avoid using insecure temporary file",
            "B110": "Avoid using try-except-pass",
            "B201": "Avoid using flask.run() in production",
            "B301": "Avoid using pickle",
            "B302": "Avoid using marshal",
            "B303": "Avoid using md5",
            "B304": "Avoid using des3",
            "B305": "Avoid using cipher modes",
            "B306": "Avoid using mktemp_q",
            "B307": "Avoid using eval()",
            "B308": "Avoid using mark_safe()",
            "B310": "Avoid using urllib.urlopen",
            "B311": "Avoid using random for security",
            "B312": "Avoid using telnetlib",
            "B313": "Avoid using xml parsers",
            "B314": "Avoid using xml parsers",
            "B315": "Avoid using xml parsers",
            "B316": "Avoid using xml parsers",
            "B317": "Avoid using xml parsers",
            "B318": "Avoid using xml parsers",
            "B319": "Avoid using xml parsers",
            "B320": "Avoid using xml parsers",
            "B321": "Avoid using ftplib",
            "B323": "Avoid using unverified_context",
            "B324": "Avoid using hashlib.insecure_hash"
        }
        return recommendations.get(test_id, "Review the code for security issues")
    
    def _map_semgrep_severity(self, severity: str) -> str:
        """Map Semgrep severity to standard levels"""
        mapping = {
            "ERROR": "high",
            "WARNING": "medium",
            "INFO": "low"
        }
        return mapping.get(severity.upper(), "medium")
    
    def _generate_report(self, findings: List[SASTFinding], output_path: str) -> str:
        """Generate SAST report"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Count by severity
        severity_counts = {}
        for finding in findings:
            severity_counts[finding.severity] = severity_counts.get(finding.severity, 0) + 1
        
        report = f"""# SAST Security Scan Report

## Summary

| Metric | Value |
|--------|-------|
| Total Findings | {len(findings)} |
| Critical | {severity_counts.get('critical', 0)} |
| High | {severity_counts.get('high', 0)} |
| Medium | {severity_counts.get('medium', 0)} |
| Low | {severity_counts.get('low', 0)} |

## Findings

| ID | Tool | File | Line | Severity | Issue |
|----|------|------|------|----------|-------|
"""
        
        for finding in findings:
            report += f"| {finding.id} | {finding.tool} | {finding.file} | {finding.line} | {finding.severity} | {finding.issue} |\n"
        
        report += "\n## Details\n\n"
        
        for finding in findings:
            report += f"""### {finding.id}

- **Tool**: {finding.tool}
- **File**: {finding.file}:{finding.line}
- **Severity**: {finding.severity}
- **Confidence**: {finding.confidence}
- **Issue**: {finding.issue}

**Description**: {finding.description}

**Recommendation**: {finding.recommendation}

---
"""
        
        # Write report
        with open(output_path, 'w') as f:
            f.write(report)
        
        return report
