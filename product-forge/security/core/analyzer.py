"""
Security Analyzer
Main orchestrator for multi-phase security analysis
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from datetime import datetime

from .threat_modeler import ThreatModeler
from .compliance_checker import ComplianceChecker
from .sast_scanner import SASTScanner
from .dast_scanner import DASTScanner
from .dependency_scanner import DependencyScanner
from .secret_detector import SecretDetector
from .reporter import SecurityReporter
from .issue_tracker import SecurityIssueTracker


@dataclass
class SecurityPhaseResult:
    """Result of a security phase"""
    phase: str
    project: str
    started_at: str
    completed_at: Optional[str]
    status: str  # running, completed, failed
    findings_count: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    info_count: int
    output_files: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SecurityAnalyzer:
    """
    Main security analyzer orchestrator.
    
    Coordinates all security analysis phases:
    - Phase 1: Design Security (threat modeling, compliance)
    - Phase 2: Architecture Security (security architecture, dependencies)
    - Phase 3: Implementation Security (SAST, secrets, dependency audit)
    - Phase 4: Validation Security (DAST, vulnerability assessment)
    """
    
    def __init__(self, products_dir: str = "products", security_dir: str = "security"):
        """
        Initialize security analyzer.
        
        Args:
            products_dir: Path to products directory
            security_dir: Path to security module
        """
        self.products_dir = Path(products_dir)
        self.security_dir = Path(security_dir)
        
        # Initialize components
        self.threat_modeler = ThreatModeler()
        self.compliance_checker = ComplianceChecker(security_dir)
        self.sast_scanner = SASTScanner()
        self.dast_scanner = DASTScanner()
        self.dependency_scanner = DependencyScanner()
        self.secret_detector = SecretDetector()
        self.reporter = SecurityReporter()
        self.issue_tracker = SecurityIssueTracker(products_dir)
    
    def _get_security_dir(self, project: str, phase: str) -> Path:
        """Get security output directory for project phase"""
        security_path = self.products_dir / project / "security" / phase
        security_path.mkdir(parents=True, exist_ok=True)
        return security_path
    
    def analyze_design(
        self,
        project: str,
        requirements_path: str,
        design_path: str
    ) -> SecurityPhaseResult:
        """
        Phase 1: Design Security Analysis
        
        Args:
            project: Project name
            requirements_path: Path to requirements.md
            design_path: Path to design.md
            
        Returns:
            SecurityPhaseResult
        """
        phase = "phase1-design"
        output_dir = self._get_security_dir(project, phase)
        
        started_at = datetime.now().isoformat()
        
        # Perform threat modeling
        threat_model = self.threat_modeler.analyze(
            requirements_path=requirements_path,
            design_path=design_path,
            output_path=str(output_dir / "threat-model.md")
        )
        
        # Check compliance requirements
        compliance = self.compliance_checker.check_requirements(
            project=project,
            requirements_path=requirements_path,
            output_path=str(output_dir / "compliance-requirements.md")
        )
        
        # Count findings
        findings = threat_model.get("findings", []) + compliance.get("findings", [])
        
        completed_at = datetime.now().isoformat()
        
        return SecurityPhaseResult(
            phase=phase,
            project=project,
            started_at=started_at,
            completed_at=completed_at,
            status="completed",
            findings_count=len(findings),
            critical_count=sum(1 for f in findings if f.get("severity") == "critical"),
            high_count=sum(1 for f in findings if f.get("severity") == "high"),
            medium_count=sum(1 for f in findings if f.get("severity") == "medium"),
            low_count=sum(1 for f in findings if f.get("severity") == "low"),
            info_count=sum(1 for f in findings if f.get("severity") == "info"),
            output_files=[
                str(output_dir / "threat-model.md"),
                str(output_dir / "compliance-requirements.md")
            ]
        )
    
    def analyze_architecture(
        self,
        project: str,
        architecture_path: str,
        phase1_dir: Optional[str] = None
    ) -> SecurityPhaseResult:
        """
        Phase 2: Architecture Security Analysis
        
        Args:
            project: Project name
            architecture_path: Path to architecture.md
            phase1_dir: Path to phase1 outputs (optional)
            
        Returns:
            SecurityPhaseResult
        """
        phase = "phase2-architecture"
        output_dir = self._get_security_dir(project, phase)
        
        started_at = datetime.now().isoformat()
        
        # Analyze security architecture
        security_arch = self._analyze_security_architecture(
            architecture_path=architecture_path,
            phase1_dir=phase1_dir,
            output_path=str(output_dir / "security-architecture.md")
        )
        
        # Analyze dependencies
        dependency_analysis = self.dependency_scan(
            project=project,
            output_path=str(output_dir / "dependency-analysis.md")
        )
        
        # Count findings
        findings = security_arch.get("findings", []) + dependency_analysis.get("findings", [])
        
        completed_at = datetime.now().isoformat()
        
        return SecurityPhaseResult(
            phase=phase,
            project=project,
            started_at=started_at,
            completed_at=completed_at,
            status="completed",
            findings_count=len(findings),
            critical_count=sum(1 for f in findings if f.get("severity") == "critical"),
            high_count=sum(1 for f in findings if f.get("severity") == "high"),
            medium_count=sum(1 for f in findings if f.get("severity") == "medium"),
            low_count=sum(1 for f in findings if f.get("severity") == "low"),
            info_count=sum(1 for f in findings if f.get("severity") == "info"),
            output_files=[
                str(output_dir / "security-architecture.md"),
                str(output_dir / "dependency-analysis.md")
            ]
        )
    
    def analyze_implementation(
        self,
        project: str,
        src_dir: str,
        phase2_dir: Optional[str] = None
    ) -> SecurityPhaseResult:
        """
        Phase 3: Implementation Security Analysis
        
        Args:
            project: Project name
            src_dir: Path to source code
            phase2_dir: Path to phase2 outputs (optional)
            
        Returns:
            SecurityPhaseResult
        """
        phase = "phase3-implementation"
        output_dir = self._get_security_dir(project, phase)
        
        started_at = datetime.now().isoformat()
        
        # Run SAST scanning
        sast_results = self.sast_scan(
            src_dir=src_dir,
            output_path=str(output_dir / "sast-report.md")
        )
        
        # Run dependency audit
        dep_audit = self.dependency_audit(
            project=project,
            output_path=str(output_dir / "dependency-audit.md")
        )
        
        # Run secret detection
        secrets_results = self.secret_scan(
            src_dir=src_dir,
            output_path=str(output_dir / "secrets-report.md")
        )
        
        # Count findings
        findings = (
            sast_results.get("findings", []) +
            dep_audit.get("findings", []) +
            secrets_results.get("findings", [])
        )
        
        completed_at = datetime.now().isoformat()
        
        return SecurityPhaseResult(
            phase=phase,
            project=project,
            started_at=started_at,
            completed_at=completed_at,
            status="completed",
            findings_count=len(findings),
            critical_count=sum(1 for f in findings if f.get("severity") == "critical"),
            high_count=sum(1 for f in findings if f.get("severity") == "high"),
            medium_count=sum(1 for f in findings if f.get("severity") == "medium"),
            low_count=sum(1 for f in findings if f.get("severity") == "low"),
            info_count=sum(1 for f in findings if f.get("severity") == "info"),
            output_files=[
                str(output_dir / "sast-report.md"),
                str(output_dir / "dependency-audit.md"),
                str(output_dir / "secrets-report.md")
            ]
        )
    
    def analyze_validation(
        self,
        project: str,
        target_url: str,
        phase3_dir: Optional[str] = None
    ) -> SecurityPhaseResult:
        """
        Phase 4: Validation Security Analysis
        
        Args:
            project: Project name
            target_url: Deployed application URL
            phase3_dir: Path to phase3 outputs (optional)
            
        Returns:
            SecurityPhaseResult
        """
        phase = "phase4-validation"
        output_dir = self._get_security_dir(project, phase)
        
        started_at = datetime.now().isoformat()
        
        # Run DAST scanning
        dast_results = self.dast_scan(
            target_url=target_url,
            output_path=str(output_dir / "dast-report.md")
        )
        
        # Run vulnerability assessment
        vuln_results = self._vulnerability_assessment(
            project=project,
            dast_results=dast_results,
            output_path=str(output_dir / "vulnerability-report.md")
        )
        
        # Count findings
        findings = dast_results.get("findings", []) + vuln_results.get("findings", [])
        
        completed_at = datetime.now().isoformat()
        
        return SecurityPhaseResult(
            phase=phase,
            project=project,
            started_at=started_at,
            completed_at=completed_at,
            status="completed",
            findings_count=len(findings),
            critical_count=sum(1 for f in findings if f.get("severity") == "critical"),
            high_count=sum(1 for f in findings if f.get("severity") == "high"),
            medium_count=sum(1 for f in findings if f.get("severity") == "medium"),
            low_count=sum(1 for f in findings if f.get("severity") == "low"),
            info_count=sum(1 for f in findings if f.get("severity") == "info"),
            output_files=[
                str(output_dir / "dast-report.md"),
                str(output_dir / "vulnerability-report.md")
            ]
        )
    
    def _analyze_security_architecture(
        self,
        architecture_path: str,
        phase1_dir: Optional[str],
        output_path: str
    ) -> Dict[str, Any]:
        """Analyze security architecture"""
        # Read architecture file
        with open(architecture_path, 'r') as f:
            architecture_content = f.read()
        
        # Analyze security controls
        findings = []
        
        # Check for common security architecture patterns
        security_patterns = {
            "authentication": ["auth", "login", "session", "token"],
            "authorization": ["rbac", "permission", "role", "access"],
            "encryption": ["encrypt", "tls", "ssl", "https", "aes"],
            "input_validation": ["validat", "sanitiz", "escape"],
            "error_handling": ["error", "exception", "catch"],
            "logging": ["log", "audit", "trail"]
        }
        
        for pattern_name, keywords in security_patterns.items():
            found = any(kw.lower() in architecture_content.lower() for kw in keywords)
            if not found:
                findings.append({
                    "type": "missing_pattern",
                    "severity": "medium",
                    "pattern": pattern_name,
                    "description": f"Security pattern '{pattern_name}' not found in architecture"
                })
        
        # Generate security architecture report
        report = self.reporter.generate_security_architecture_report(
            architecture_content=architecture_content,
            findings=findings,
            output_path=output_path
        )
        
        return {"findings": findings, "report": report}
    
    def dependency_scan(
        self,
        project: str,
        output_path: str
    ) -> Dict[str, Any]:
        """Run dependency scanning"""
        return self.dependency_scanner.scan(
            project=project,
            output_path=output_path
        )
    
    def sast_scan(
        self,
        src_dir: str,
        output_path: str
    ) -> Dict[str, Any]:
        """Run SAST scanning"""
        return self.sast_scanner.scan(
            src_dir=src_dir,
            output_path=output_path
        )
    
    def dependency_audit(
        self,
        project: str,
        output_path: str
    ) -> Dict[str, Any]:
        """Run dependency audit"""
        return self.dependency_scanner.audit(
            project=project,
            output_path=output_path
        )
    
    def secret_scan(
        self,
        src_dir: str,
        output_path: str
    ) -> Dict[str, Any]:
        """Run secret detection"""
        return self.secret_detector.scan(
            src_dir=src_dir,
            output_path=output_path
        )
    
    def dast_scan(
        self,
        target_url: str,
        output_path: str
    ) -> Dict[str, Any]:
        """Run DAST scanning"""
        return self.dast_scanner.scan(
            target_url=target_url,
            output_path=output_path
        )
    
    def _vulnerability_assessment(
        self,
        project: str,
        dast_results: Dict[str, Any],
        output_path: str
    ) -> Dict[str, Any]:
        """Perform vulnerability assessment"""
        # Aggregate all findings
        all_findings = dast_results.get("findings", [])
        
        # Generate vulnerability report
        report = self.reporter.generate_vulnerability_report(
            project=project,
            findings=all_findings,
            output_path=output_path
        )
        
        return {"findings": all_findings, "report": report}
    
    def get_project_summary(self, project: str) -> Dict[str, Any]:
        """
        Get security summary for a project.
        
        Args:
            project: Project name
            
        Returns:
            Security summary
        """
        security_dir = self.products_dir / project / "security"
        
        summary = {
            "project": project,
            "phases_completed": [],
            "total_findings": 0,
            "findings_by_severity": {
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "info": 0
            }
        }
        
        for phase in ["phase1-design", "phase2-architecture", "phase3-implementation", "phase4-validation"]:
            phase_dir = security_dir / phase
            if phase_dir.exists():
                summary["phases_completed"].append(phase)
                
                # Read phase results if available
                results_file = phase_dir / "results.json"
                if results_file.exists():
                    with open(results_file, 'r') as f:
                        results = json.load(f)
                        summary["total_findings"] += results.get("findings_count", 0)
                        for severity in ["critical", "high", "medium", "low", "info"]:
                            summary["findings_by_severity"][severity] += results.get(f"{severity}_count", 0)
        
        return summary
