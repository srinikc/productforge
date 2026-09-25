"""
Dependency Scanner
Third-party component vulnerability scanning using Trivy, Safety, and npm audit
"""

import json
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict


@dataclass
class DependencyFinding:
    """Dependency finding"""
    id: str
    tool: str
    package: str
    current_version: str
    latest_version: Optional[str]
    vulnerability: str
    severity: str
    cvss: Optional[str]
    description: str
    recommendation: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DependencyScanner:
    """
    Dependency vulnerability scanner.
    
    Uses Trivy for multi-language, Safety for Python, and npm audit for Node.js.
    """
    
    def __init__(self):
        """Initialize dependency scanner"""
        self.tools = {
            "trivy": self._run_trivy,
            "safety": self._run_safety,
            "npm_audit": self._run_npm_audit
        }
    
    def scan(
        self,
        project: str,
        output_path: str,
        tools: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Run dependency scanning.
        
        Args:
            project: Project name
            output_path: Path to output file
            tools: Tools to use (default: all)
            
        Returns:
            Scan results
        """
        findings = []
        tools_to_run = tools or list(self.tools.keys())
        
        for tool in tools_to_run:
            if tool in self.tools:
                tool_findings = self.tools[tool](project)
                findings.extend(tool_findings)
        
        # Generate report
        report = self._generate_report(findings, output_path)
        
        return {
            "findings": [f.to_dict() for f in findings],
            "tools_used": tools_to_run,
            "report": report
        }
    
    def audit(
        self,
        project: str,
        output_path: str
    ) -> Dict[str, Any]:
        """
        Run dependency audit.
        
        Args:
            project: Project name
            output_path: Path to output file
            
        Returns:
            Audit results
        """
        return self.scan(project, output_path)
    
    def _run_trivy(self, project: str) -> List[DependencyFinding]:
        """Run Trivy scanner"""
        findings = []
        project_path = Path("products") / project
        
        try:
            # Run Trivy filesystem scan
            cmd = [
                "trivy",
                "fs",
                "--scanners", "vuln",
                "--format", "json",
                str(project_path)
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
                for artifact in output.get("Results", []):
                    for vuln in artifact.get("Vulnerabilities", []):
                        finding = DependencyFinding(
                            id=f"TRIVY-{vuln.get('VulnerabilityID', 'UNKNOWN')}",
                            tool="trivy",
                            package=vuln.get("PkgName", "unknown"),
                            current_version=vuln.get("InstalledVersion", "unknown"),
                            latest_version=vuln.get("FixedVersion"),
                            vulnerability=vuln.get("VulnerabilityID", "Unknown"),
                            severity=self._map_trivy_severity(vuln.get("Severity", "UNKNOWN")),
                            cvss=str(vuln.get("CVSS", {}).get("nvd", {}).get("V3Score", "")),
                            description=vuln.get("Description", ""),
                            recommendation=f"Update to version {vuln.get('FixedVersion', 'latest')}"
                        )
                        findings.append(finding)
        
        except subprocess.TimeoutExpired:
            pass
        except FileNotFoundError:
            # Trivy not installed
            pass
        except Exception as e:
            pass
        
        return findings
    
    def _run_safety(self, project: str) -> List[DependencyFinding]:
        """Run Safety scanner"""
        findings = []
        project_path = Path("products") / project
        
        # Check for Python dependencies
        requirements_files = list(project_path.rglob("requirements*.txt"))
        if not requirements_files:
            return findings
        
        for req_file in requirements_files:
            try:
                # Run Safety
                cmd = [
                    "safety",
                    "scan",
                    "--file", str(req_file),
                    "--output", "json"
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
                    for vuln in output.get("vulnerabilities", []):
                        finding = DependencyFinding(
                            id=f"SAFETY-{vuln.get('id', 'UNKNOWN')}",
                            tool="safety",
                            package=vuln.get("package", "unknown"),
                            current_version=vuln.get("installed_version", "unknown"),
                            latest_version=vuln.get("fixed_version"),
                            vulnerability=vuln.get("advisory", "Unknown"),
                            severity=self._map_safety_severity(vuln),
                            cvss=None,
                            description=vuln.get("description", ""),
                            recommendation=f"Update to version {vuln.get('fixed_version', 'latest')}"
                        )
                        findings.append(finding)
            
            except subprocess.TimeoutExpired:
                continue
            except FileNotFoundError:
                # Safety not installed
                continue
            except Exception as e:
                continue
        
        return findings
    
    def _run_npm_audit(self, project: str) -> List[DependencyFinding]:
        """Run npm audit"""
        findings = []
        project_path = Path("products") / project
        
        # Check for Node.js dependencies
        package_json = project_path / "package.json"
        if not package_json.exists():
            return findings
        
        try:
            # Run npm audit
            cmd = [
                "npm",
                "audit",
                "--json"
            ]
            
            result = subprocess.run(
                cmd,
                cwd=str(project_path),
                capture_output=True,
                text=True,
                timeout=300
            )
            
            # Parse JSON output
            if result.stdout:
                output = json.loads(result.stdout)
                for vuln_id, vuln in output.get("vulnerabilities", {}).items():
                    finding = DependencyFinding(
                        id=f"NPM-{vuln_id}",
                        tool="npm_audit",
                        package=vuln.get("name", "unknown"),
                        current_version=vuln.get("version", "unknown"),
                        latest_version=None,
                        vulnerability=vuln_id,
                        severity=self._map_npm_severity(vuln.get("severity", "info")),
                        cvss=None,
                        description=vuln.get("title", ""),
                        recommendation=vuln.get("url", "Run npm audit fix")
                    )
                    findings.append(finding)
        
        except subprocess.TimeoutExpired:
            pass
        except FileNotFoundError:
            # npm not installed
            pass
        except Exception as e:
            pass
        
        return findings
    
    def _map_trivy_severity(self, severity: str) -> str:
        """Map Trivy severity to standard levels"""
        mapping = {
            "CRITICAL": "critical",
            "HIGH": "high",
            "MEDIUM": "medium",
            "LOW": "low",
            "UNKNOWN": "info"
        }
        return mapping.get(severity.upper(), "info")
    
    def _map_safety_severity(self, vuln: Dict[str, Any]) -> str:
        """Map Safety severity to standard levels"""
        # Safety doesn't provide explicit severity, use CVSS if available
        cvss = vuln.get("cvss", 0)
        if cvss >= 9.0:
            return "critical"
        elif cvss >= 7.0:
            return "high"
        elif cvss >= 4.0:
            return "medium"
        else:
            return "low"
    
    def _map_npm_severity(self, severity: str) -> str:
        """Map npm severity to standard levels"""
        mapping = {
            "critical": "critical",
            "high": "high",
            "moderate": "medium",
            "low": "low",
            "info": "info"
        }
        return mapping.get(severity.lower(), "info")
    
    def _generate_report(self, findings: List[DependencyFinding], output_path: str) -> str:
        """Generate dependency audit report"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Count by severity
        severity_counts = {}
        for finding in findings:
            severity_counts[finding.severity] = severity_counts.get(finding.severity, 0) + 1
        
        report = f"""# Dependency Security Audit Report

## Summary

| Metric | Value |
|--------|-------|
| Total Findings | {len(findings)} |
| Critical | {severity_counts.get('critical', 0)} |
| High | {severity_counts.get('high', 0)} |
| Medium | {severity_counts.get('medium', 0)} |
| Low | {severity_counts.get('low', 0)} |

## Findings

| ID | Tool | Package | Current | Latest | Severity | Vulnerability |
|----|------|---------|---------|--------|----------|---------------|
"""
        
        for finding in findings:
            latest = finding.latest_version or "-"
            report += f"| {finding.id} | {finding.tool} | {finding.package} | {finding.current_version} | {latest} | {finding.severity} | {finding.vulnerability} |\n"
        
        report += "\n## Details\n\n"
        
        for finding in findings:
            report += f"""### {finding.id}

- **Tool**: {finding.tool}
- **Package**: {finding.package}
- **Current Version**: {finding.current_version}
- **Latest Version**: {finding.latest_version or "N/A"}
- **Vulnerability**: {finding.vulnerability}
- **Severity**: {finding.severity}
- **CVSS**: {finding.cvss or "N/A"}

**Description**: {finding.description}

**Recommendation**: {finding.recommendation}

---
"""
        
        # Write report
        with open(output_path, 'w') as f:
            f.write(report)
        
        return report
