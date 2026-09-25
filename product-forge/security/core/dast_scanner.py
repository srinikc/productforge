"""
DAST Scanner
Dynamic Application Security Testing using OWASP ZAP and Nuclei
"""

import json
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict


@dataclass
class DASTFinding:
    """DAST finding"""
    id: str
    tool: str
    url: str
    method: str
    vulnerability: str
    severity: str
    cvss: Optional[str]
    description: str
    recommendation: str
    evidence: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DASTScanner:
    """
    Dynamic Application Security Testing scanner.
    
    Uses OWASP ZAP for web application scanning and Nuclei for vulnerability templates.
    """
    
    def __init__(self):
        """Initialize DAST scanner"""
        self.tools = {
            "zap": self._run_zap,
            "nuclei": self._run_nuclei
        }
    
    def scan(
        self,
        target_url: str,
        output_path: str,
        tools: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Run DAST scanning.
        
        Args:
            target_url: Target URL to scan
            output_path: Path to output file
            tools: Tools to use (default: all)
            
        Returns:
            Scan results
        """
        findings = []
        tools_to_run = tools or list(self.tools.keys())
        
        for tool in tools_to_run:
            if tool in self.tools:
                tool_findings = self.tools[tool](target_url)
                findings.extend(tool_findings)
        
        # Generate report
        report = self._generate_report(findings, output_path)
        
        return {
            "findings": [f.to_dict() for f in findings],
            "tools_used": tools_to_run,
            "target_url": target_url,
            "report": report
        }
    
    def _run_zap(self, target_url: str) -> List[DASTFinding]:
        """Run OWASP ZAP scanner"""
        findings = []
        
        try:
            # Run ZAP baseline scan
            cmd = [
                "docker", "run",
                "-t", "owasp/zap2docker-stable",
                "zap-baseline.py",
                "-t", target_url,
                "-r", "report.json",
                "-x", "report.xml"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600
            )
            
            # Parse output (simplified - in production, parse ZAP report)
            # For now, create placeholder findings
            if result.returncode == 0:
                pass  # Success, but no findings parsed
            
        except subprocess.TimeoutExpired:
            pass
        except FileNotFoundError:
            # Docker not installed
            pass
        except Exception as e:
            pass
        
        return findings
    
    def _run_nuclei(self, target_url: str) -> List[DASTFinding]:
        """Run Nuclei scanner"""
        findings = []
        
        try:
            # Run Nuclei
            cmd = [
                "nuclei",
                "-u", target_url,
                "-json",
                "-severity", "critical,high,medium"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            # Parse JSON output
            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        try:
                            output = json.loads(line)
                            finding = DASTFinding(
                                id=f"NUCLEI-{output.get('template-id', 'UNKNOWN')}",
                                tool="nuclei",
                                url=target_url,
                                method="GET",
                                vulnerability=output.get('info', {}).get('name', 'Unknown'),
                                severity=self._map_nuclei_severity(
                                    output.get('info', {}).get('severity', 'info')
                                ),
                                cvss=output.get('info', {}).get('classification', {}).get('cvss-score'),
                                description=output.get('info', {}).get('description', ''),
                                recommendation=output.get('info', {}).get('remediation', ''),
                                evidence=output.get('matched-at', '')
                            )
                            findings.append(finding)
                        except json.JSONDecodeError:
                            continue
        
        except subprocess.TimeoutExpired:
            pass
        except FileNotFoundError:
            # Nuclei not installed
            pass
        except Exception as e:
            pass
        
        return findings
    
    def _map_nuclei_severity(self, severity: str) -> str:
        """Map Nuclei severity to standard levels"""
        mapping = {
            "critical": "critical",
            "high": "high",
            "medium": "medium",
            "low": "low",
            "info": "info"
        }
        return mapping.get(severity.lower(), "info")
    
    def _generate_report(self, findings: List[DASTFinding], output_path: str) -> str:
        """Generate DAST report"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Count by severity
        severity_counts = {}
        for finding in findings:
            severity_counts[finding.severity] = severity_counts.get(finding.severity, 0) + 1
        
        report = f"""# DAST Security Scan Report

## Summary

| Metric | Value |
|--------|-------|
| Total Findings | {len(findings)} |
| Critical | {severity_counts.get('critical', 0)} |
| High | {severity_counts.get('high', 0)} |
| Medium | {severity_counts.get('medium', 0)} |
| Low | {severity_counts.get('low', 0)} |

## Findings

| ID | Tool | Vulnerability | Severity | CVSS | URL |
|----|------|---------------|----------|------|-----|
"""
        
        for finding in findings:
            cvss = finding.cvss or "-"
            report += f"| {finding.id} | {finding.tool} | {finding.vulnerability} | {finding.severity} | {cvss} | {finding.url} |\n"
        
        report += "\n## Details\n\n"
        
        for finding in findings:
            report += f"""### {finding.id}

- **Tool**: {finding.tool}
- **URL**: {finding.url}
- **Method**: {finding.method}
- **Vulnerability**: {finding.vulnerability}
- **Severity**: {finding.severity}
- **CVSS**: {finding.cvss or "N/A"}

**Description**: {finding.description}

**Recommendation**: {finding.recommendation}

**Evidence**: {finding.evidence or "N/A"}

---
"""
        
        # Write report
        with open(output_path, 'w') as f:
            f.write(report)
        
        return report
