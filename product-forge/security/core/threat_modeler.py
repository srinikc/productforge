"""
Threat Modeler
STRIDE-based threat modeling for security analysis
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from enum import Enum


class ThreatCategory(Enum):
    """STRIDE threat categories"""
    SPOOFING = "spoofing"
    TAMPERING = "tampering"
    REPUDIATION = "repudiation"
    INFORMATION_DISCLOSURE = "information_disclosure"
    DENIAL_OF_SERVICE = "denial_of_service"
    ELEVATION_OF_PRIVILEGE = "elevation_of_privilege"


@dataclass
class Threat:
    """Threat definition"""
    id: str
    category: str
    title: str
    description: str
    affected_component: str
    severity: str
    likelihood: str
    impact: str
    risk: str
    mitigation: str
    recommendations: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ThreatModeler:
    """
    STRIDE-based threat modeler.
    
    Analyzes requirements and design to identify potential threats
    using the STRIDE methodology.
    """
    
    def __init__(self):
        """Initialize threat modeler"""
        self.threat_patterns = self._load_threat_patterns()
    
    def _load_threat_patterns(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load threat patterns"""
        return {
            ThreatCategory.SPOOFING.value: [
                {
                    "pattern": "authentication",
                    "description": "Weak or missing authentication mechanisms",
                    "severity": "high",
                    "mitigation": "Implement strong authentication with MFA"
                },
                {
                    "pattern": "identity",
                    "description": "Identity verification weaknesses",
                    "severity": "high",
                    "mitigation": "Use cryptographic identity verification"
                }
            ],
            ThreatCategory.TAMPERING.value: [
                {
                    "pattern": "input",
                    "description": "Unvalidated input data",
                    "severity": "high",
                    "mitigation": "Implement input validation and sanitization"
                },
                {
                    "pattern": "data",
                    "description": "Data integrity vulnerabilities",
                    "severity": "medium",
                    "mitigation": "Use digital signatures and checksums"
                }
            ],
            ThreatCategory.REPUDIATION.value: [
                {
                    "pattern": "audit",
                    "description": "Insufficient audit logging",
                    "severity": "medium",
                    "mitigation": "Implement comprehensive audit trails"
                },
                {
                    "pattern": "log",
                    "description": "Missing or tamperable logs",
                    "severity": "medium",
                    "mitigation": "Use immutable logging with integrity checks"
                }
            ],
            ThreatCategory.INFORMATION_DISCLOSURE.value: [
                {
                    "pattern": "sensitive",
                    "description": "Sensitive data exposure",
                    "severity": "critical",
                    "mitigation": "Encrypt sensitive data at rest and in transit"
                },
                {
                    "pattern": "error",
                    "description": "Verbose error messages",
                    "severity": "medium",
                    "mitigation": "Implement proper error handling"
                }
            ],
            ThreatCategory.DENIAL_OF_SERVICE.value: [
                {
                    "pattern": "resource",
                    "description": "Resource exhaustion vulnerabilities",
                    "severity": "high",
                    "mitigation": "Implement rate limiting and resource quotas"
                },
                {
                    "pattern": "availability",
                    "description": "Availability attack vectors",
                    "severity": "high",
                    "mitigation": "Implement redundancy and failover"
                }
            ],
            ThreatCategory.ELEVATION_OF_PRIVILEGE.value: [
                {
                    "pattern": "authorization",
                    "description": "Broken access control",
                    "severity": "critical",
                    "mitigation": "Implement proper authorization checks"
                },
                {
                    "pattern": "permission",
                    "description": "Privilege escalation vulnerabilities",
                    "severity": "critical",
                    "mitigation": "Use principle of least privilege"
                }
            ]
        }
    
    def analyze(
        self,
        requirements_path: str,
        design_path: str,
        output_path: str
    ) -> Dict[str, Any]:
        """
        Perform threat modeling analysis.
        
        Args:
            requirements_path: Path to requirements.md
            design_path: Path to design.md
            output_path: Path to output file
            
        Returns:
            Analysis results
        """
        # Read input files
        with open(requirements_path, 'r') as f:
            requirements_content = f.read()
        
        with open(design_path, 'r') as f:
            design_content = f.read()
        
        # Analyze threats
        threats = self._identify_threats(requirements_content, design_content)
        
        # Generate report
        report = self._generate_threat_report(threats, output_path)
        
        return {
            "threats": [t.to_dict() for t in threats],
            "findings": [t.to_dict() for t in threats],
            "report": report
        }
    
    def _identify_threats(
        self,
        requirements_content: str,
        design_content: str
    ) -> List[Threat]:
        """Identify threats from requirements and design"""
        threats = []
        threat_id = 1
        
        # Analyze for each STRIDE category
        for category, patterns in self.threat_patterns.items():
            for pattern_info in patterns:
                # Check if pattern is relevant
                if self._is_pattern_relevant(
                    pattern_info["pattern"],
                    requirements_content,
                    design_content
                ):
                    threat = Threat(
                        id=f"THR-{threat_id:03d}",
                        category=category,
                        title=f"{category.replace('_', ' ').title()}: {pattern_info['description']}",
                        description=pattern_info["description"],
                        affected_component="Application",
                        severity=pattern_info["severity"],
                        likelihood="medium",
                        impact=pattern_info["severity"],
                        risk=self._calculate_risk(pattern_info["severity"], "medium"),
                        mitigation=pattern_info["mitigation"],
                        recommendations=[pattern_info["mitigation"]]
                    )
                    threats.append(threat)
                    threat_id += 1
        
        return threats
    
    def _is_pattern_relevant(
        self,
        pattern: str,
        requirements_content: str,
        design_content: str
    ) -> bool:
        """Check if a threat pattern is relevant"""
        combined = (requirements_content + design_content).lower()
        
        # Simple keyword matching
        pattern_keywords = {
            "authentication": ["auth", "login", "password", "credential", "session"],
            "identity": ["user", "identity", "account", "profile"],
            "input": ["input", "form", "field", "parameter", "query"],
            "data": ["data", "storage", "database", "file"],
            "audit": ["audit", "log", "trail", "monitor"],
            "log": ["log", "logging", "logger"],
            "sensitive": ["sensitive", "private", "confidential", "secret", "pii"],
            "error": ["error", "exception", "fault", "failure"],
            "resource": ["resource", "memory", "cpu", "bandwidth", "storage"],
            "availability": ["available", "uptime", "service", "downtime"],
            "authorization": ["permission", "access", "role", "privilege"],
            "permission": ["permission", "grant", "deny", "allow"]
        }
        
        keywords = pattern_keywords.get(pattern, [pattern])
        return any(kw in combined for kw in keywords)
    
    def _calculate_risk(self, severity: str, likelihood: str) -> str:
        """Calculate risk level"""
        risk_matrix = {
            ("critical", "high"): "critical",
            ("critical", "medium"): "high",
            ("critical", "low"): "medium",
            ("high", "high"): "high",
            ("high", "medium"): "high",
            ("high", "low"): "medium",
            ("medium", "high"): "medium",
            ("medium", "medium"): "medium",
            ("medium", "low"): "low",
            ("low", "high"): "low",
            ("low", "medium"): "low",
            ("low", "low"): "low"
        }
        
        return risk_matrix.get((severity, likelihood), "medium")
    
    def _generate_threat_report(
        self,
        threats: List[Threat],
        output_path: str
    ) -> str:
        """Generate threat model report"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Count by category
        category_counts = {}
        for threat in threats:
            category_counts[threat.category] = category_counts.get(threat.category, 0) + 1
        
        # Count by severity
        severity_counts = {}
        for threat in threats:
            severity_counts[threat.severity] = severity_counts.get(threat.severity, 0) + 1
        
        report = f"""# Security Threat Model (STRIDE)

## Summary

| Metric | Value |
|--------|-------|
| Total Threats | {len(threats)} |
| Critical | {severity_counts.get('critical', 0)} |
| High | {severity_counts.get('high', 0)} |
| Medium | {severity_counts.get('medium', 0)} |
| Low | {severity_counts.get('low', 0)} |

## Threats by Category

| Category | Count |
|----------|-------|
"""
        
        for category, count in category_counts.items():
            report += f"| {category.replace('_', ' ').title()} | {count} |\n"
        
        report += "\n## Threat Details\n\n"
        
        for threat in threats:
            report += f"""### {threat.id}: {threat.title}

- **Category**: {threat.category.replace('_', ' ').title()}
- **Severity**: {threat.severity}
- **Likelihood**: {threat.likelihood}
- **Impact**: {threat.impact}
- **Risk**: {threat.risk}
- **Affected Component**: {threat.affected_component}

**Description**: {threat.description}

**Mitigation**: {threat.mitigation}

**Recommendations**:
"""
            for rec in threat.recommendations:
                report += f"- {rec}\n"
            
            report += "\n"
        
        # Write report
        with open(output_path, 'w') as f:
            f.write(report)
        
        return report
