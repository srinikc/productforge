"""
Secret Detector
Secret detection using TruffleHog and GitLeaks
"""

import json
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict


@dataclass
class SecretFinding:
    """Secret finding"""
    id: str
    tool: str
    file: str
    line: int
    secret_type: str
    severity: str
    description: str
    recommendation: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SecretDetector:
    """
    Secret detection scanner.
    
    Uses TruffleHog for deep history scanning and GitLeaks for quick scans.
    """
    
    def __init__(self):
        """Initialize secret detector"""
        self.tools = {
            "trufflehog": self._run_trufflehog,
            "gitleaks": self._run_gitleaks
        }
    
    def scan(
        self,
        src_dir: str,
        output_path: str,
        tools: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Run secret detection scanning.
        
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
    
    def _run_trufflehog(self, src_path: Path) -> List[SecretFinding]:
        """Run TruffleHog scanner"""
        findings = []
        
        try:
            # Run TruffleHog
            cmd = [
                "trufflehog",
                "filesystem",
                "--directory", str(src_path),
                "--json"
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
                            finding = SecretFinding(
                                id=f"TRUFFLEHOG-{len(findings) + 1:03d}",
                                tool="trufflehog",
                                file=output.get("SourceMetadata", {}).get("Data", {}).get("Filesystem", {}).get("file", "unknown"),
                                line=output.get("SourceMetadata", {}).get("Data", {}).get("Filesystem", {}).get("line", 0),
                                secret_type=output.get("DetectorName", "Unknown"),
                                severity="high",
                                description=f"Detected {output.get('DetectorName', 'secret')} in source code",
                                recommendation="Remove the secret and rotate it immediately"
                            )
                            findings.append(finding)
                        except json.JSONDecodeError:
                            continue
        
        except subprocess.TimeoutExpired:
            pass
        except FileNotFoundError:
            # TruffleHog not installed
            pass
        except Exception as e:
            pass
        
        return findings
    
    def _run_gitleaks(self, src_path: Path) -> List[SecretFinding]:
        """Run GitLeaks scanner"""
        findings = []
        
        try:
            # Run GitLeaks
            cmd = [
                "gitleaks",
                "dir",
                "--source", str(src_path),
                "--report-format", "json"
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
                for vuln in output:
                    finding = SecretFinding(
                        id=f"GITLEAKS-{len(findings) + 1:03d}",
                        tool="gitleaks",
                        file=vuln.get("File", "unknown"),
                        line=vuln.get("StartLine", 0),
                        secret_type=vuln.get("Description", "Unknown"),
                        severity="high",
                        description=vuln.get("Description", "Secret detected"),
                        recommendation="Remove the secret and rotate it immediately"
                    )
                    findings.append(finding)
        
        except subprocess.TimeoutExpired:
            pass
        except FileNotFoundError:
            # GitLeaks not installed
            pass
        except Exception as e:
            pass
        
        return findings
    
    def _generate_report(self, findings: List[SecretFinding], output_path: str) -> str:
        """Generate secret detection report"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        report = f"""# Secret Detection Report

## Summary

| Metric | Value |
|--------|-------|
| Total Findings | {len(findings)} |
| High Severity | {len(findings)} |

## Findings

| ID | Tool | File | Line | Type | Severity |
|----|------|------|------|------|----------|
"""
        
        for finding in findings:
            report += f"| {finding.id} | {finding.tool} | {finding.file} | {finding.line} | {finding.secret_type} | {finding.severity} |\n"
        
        report += "\n## Details\n\n"
        
        for finding in findings:
            report += f"""### {finding.id}

- **Tool**: {finding.tool}
- **File**: {finding.file}:{finding.line}
- **Secret Type**: {finding.secret_type}
- **Severity**: {finding.severity}

**Description**: {finding.description}

**Recommendation**: {finding.recommendation}

---
"""
        
        # Write report
        with open(output_path, 'w') as f:
            f.write(report)
        
        return report
