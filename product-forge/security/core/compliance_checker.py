"""
Compliance Checker
Regulatory compliance verification based on product domain
"""

import yaml
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict


@dataclass
class ComplianceRequirement:
    """Compliance requirement"""
    regulation: str
    requirement: str
    status: str  # met, not_met, partial, na
    evidence: Optional[str]
    gap: Optional[str]
    remediation: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ComplianceChecker:
    """
    Compliance checker for regulatory requirements.
    
    Checks compliance based on product domain and type.
    """
    
    def __init__(self, security_dir: str = "security"):
        """
        Initialize compliance checker.
        
        Args:
            security_dir: Path to security module
        """
        self.security_dir = Path(security_dir)
        self.config = self._load_compliance_config()
    
    def _load_compliance_config(self) -> Dict[str, Any]:
        """Load compliance configuration"""
        config_path = self.security_dir / "config" / "compliance.yaml"
        if config_path.exists():
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        return {}
    
    def check_requirements(
        self,
        project: str,
        requirements_path: str,
        output_path: str
    ) -> Dict[str, Any]:
        """
        Check compliance requirements for a project.
        
        Args:
            project: Project name
            requirements_path: Path to requirements.md
            output_path: Path to output file
            
        Returns:
            Compliance check results
        """
        # Read requirements
        with open(requirements_path, 'r') as f:
            requirements_content = f.read()
        
        # Get domain from project config
        domain = self._get_project_domain(project)
        
        # Get applicable regulations
        regulations = self.config.get("domains", {}).get(domain, {}).get("regulations", [])
        
        # Check compliance
        requirements = self._check_regulations(requirements_content, regulations)
        
        # Generate report
        report = self._generate_compliance_report(
            domain=domain,
            requirements=requirements,
            output_path=output_path
        )
        
        findings = []
        for req in requirements:
            if req.status == "not_met":
                findings.append({
                    "type": "compliance_gap",
                    "severity": "high",
                    "regulation": req.regulation,
                    "requirement": req.requirement,
                    "gap": req.gap,
                    "remediation": req.remediation
                })
        
        return {
            "domain": domain,
            "regulations": [r.get("name") for r in regulations],
            "requirements": [r.to_dict() for r in requirements],
            "findings": findings,
            "report": report
        }
    
    def _get_project_domain(self, project: str) -> str:
        """Get product domain from project config"""
        config_path = Path("products") / project / "project-config.json"
        if config_path.exists():
            import json
            with open(config_path, 'r') as f:
                config = json.load(f)
                return config.get("product_domain", "general")
        return "general"
    
    def _check_regulations(
        self,
        requirements_content: str,
        regulations: List[Dict[str, Any]]
    ) -> List[ComplianceRequirement]:
        """Check compliance with regulations"""
        requirements = []
        
        for regulation in regulations:
            reg_name = regulation.get("name", "Unknown")
            reg_requirements = regulation.get("requirements", [])
            
            for req_key, req_value in reg_requirements.items():
                # Check if requirement is met
                status, evidence, gap, remediation = self._check_requirement(
                    req_key, req_value, requirements_content
                )
                
                requirements.append(ComplianceRequirement(
                    regulation=reg_name,
                    requirement=f"{req_key}: {req_value}",
                    status=status,
                    evidence=evidence,
                    gap=gap,
                    remediation=remediation
                ))
        
        return requirements
    
    def _check_requirement(
        self,
        req_key: str,
        req_value: Any,
        requirements_content: str
    ) -> tuple:
        """Check a single requirement"""
        content_lower = requirements_content.lower()
        
        # Simple keyword checking
        requirement_keywords = {
            "encryption_at_rest": ["encrypt", "at rest", "storage"],
            "encryption_in_transit": ["tls", "ssl", "https", "encrypt", "transit"],
            "access_control": ["rbac", "role", "permission", "access"],
            "audit_logging": ["audit", "log", "trail"],
            "mfa_required": ["mfa", "multi-factor", "two-factor", "2fa"],
            "phi_protection": ["phi", "protected health", "hipaa"],
            "pii_protection": ["pii", "personal data", "gdpr", "ccpa"],
            "consent_management": ["consent", "permission", "opt-in"],
            "breach_notification": ["breach", "notification", "notify"],
            "data_retention": ["retention", "archive", "delete"],
            "vulnerability_scanning": ["vulnerability", "scan", "pentest"],
            "penetration_testing": ["penetration", "pentest", "security test"]
        }
        
        keywords = requirement_keywords.get(req_key, [req_key.lower()])
        found = any(kw in content_lower for kw in keywords)
        
        if found:
            return ("met", f"Found in requirements", None, None)
        else:
            return (
                "not_met",
                None,
                f"Requirement '{req_key}' not documented",
                f"Add '{req_key}' to requirements documentation"
            )
    
    def _generate_compliance_report(
        self,
        domain: str,
        requirements: List[ComplianceRequirement],
        output_path: str
    ) -> str:
        """Generate compliance report"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Count by status
        status_counts = {}
        for req in requirements:
            status_counts[req.status] = status_counts.get(req.status, 0) + 1
        
        report = f"""# Compliance Requirements Report

## Domain: {domain}

## Summary

| Status | Count |
|--------|-------|
| Met | {status_counts.get('met', 0)} |
| Not Met | {status_counts.get('not_met', 0)} |
| Partial | {status_counts.get('partial', 0)} |
| N/A | {status_counts.get('na', 0)} |

## Requirements

| Regulation | Requirement | Status | Gap | Remediation |
|------------|-------------|--------|-----|-------------|
"""
        
        for req in requirements:
            gap = req.gap or "-"
            remediation = req.remediation or "-"
            report += f"| {req.regulation} | {req.requirement} | {req.status} | {gap} | {remediation} |\n"
        
        # Write report
        with open(output_path, 'w') as f:
            f.write(report)
        
        return report
