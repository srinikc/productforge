"""
RCCA - Root Cause Analysis
Analyzes defects to determine root cause and prevention rules
"""

import os
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path
from enum import Enum

class PipelineStage(Enum):
    IDEATION = "ideation"
    DESIGN = "design"
    ARCHITECTURE = "architecture"
    IMPLEMENTATION = "implementation"
    VALIDATION = "validation"

class RootCauseCategory(Enum):
    REQUIREMENTS = "requirements"
    DESIGN = "design"
    ARCHITECTURE = "architecture"
    IMPLEMENTATION = "implementation"
    TESTING = "testing"
    DEPENDENCY = "dependency"
    SECURITY = "security"
    DEPLOYMENT = "deployment"

@dataclass
class RCCAFinding:
    finding_id: str
    defect_id: str
    root_cause: str
    category: RootCauseCategory
    stage_caught: PipelineStage
    stage_prevented: PipelineStage
    recommendation: str
    agent_responsible: str
    confidence: float
    evidence: Optional[List[str]] = None

@dataclass
class RCCAReport:
    defect_id: str
    findings: List[RCCAFinding]
    overall_stage: PipelineStage
    overall_confidence: float
    recommendations: List[str]
    agent_updates: List[Dict[str, Any]]

class RCCAAnalyzer:
    """Analyzes defects and generates prevention rules"""
    
    def __init__(self, defects_path: Optional[str] = None):
        self.defects_path = Path(defects_path or Path(__file__).parent.parent / "defects")
        self.rcca_path = self.defects_path / "rcca"
        self.rcca_path.mkdir(parents=True, exist_ok=True)
        self.analysis_rules = self._load_analysis_rules()
        
    def _load_analysis_rules(self) -> Dict[str, Any]:
        """Load analysis rules for defect classification"""
        return {
            "test_patterns": {
                r"test_.*_api": {
                    "category": RootCauseCategory.IMPLEMENTATION,
                    "stage": PipelineStage.IMPLEMENTATION,
                    "agent": "implement"
                },
                r"test_.*_ui": {
                    "category": RootCauseCategory.IMPLEMENTATION,
                    "stage": PipelineStage.IMPLEMENTATION,
                    "agent": "implement"
                },
                r"test_.*_integration": {
                    "category": RootCauseCategory.ARCHITECTURE,
                    "stage": PipelineStage.ARCHITECTURE,
                    "agent": "architect"
                },
                r"test_.*_security": {
                    "category": RootCauseCategory.REQUIREMENTS,
                    "stage": PipelineStage.DESIGN,
                    "agent": "design"
                },
                r"test_.*_performance": {
                    "category": RootCauseCategory.ARCHITECTURE,
                    "stage": PipelineStage.ARCHITECTURE,
                    "agent": "architect"
                }
            },
            "error_patterns": {
                r"import.*error": {
                    "category": RootCauseCategory.DEPENDENCY,
                    "stage": PipelineStage.ARCHITECTURE,
                    "agent": "architect"
                },
                r"null.*reference|undefined.*function": {
                    "category": RootCauseCategory.IMPLEMENTATION,
                    "stage": PipelineStage.IMPLEMENTATION,
                    "agent": "implement"
                },
                r"timeout|timed.out": {
                    "category": RootCauseCategory.ARCHITECTURE,
                    "stage": PipelineStage.ARCHITECTURE,
                    "agent": "architect"
                },
                r"permission.*denied|unauthorized": {
                    "category": RootCauseCategory.SECURITY,
                    "stage": PipelineStage.DESIGN,
                    "agent": "design"
                }
            }
        }
    
    def analyze_defect(self, defect_id: str, defect_data: Dict[str, Any]) -> RCCAReport:
        """Analyze a defect and generate RCCA report"""
        findings = []
        
        # Analyze test name patterns
        test_name = defect_data.get("test_name", "")
        for pattern, rules in self.analysis_rules["test_patterns"].items():
            if re.match(pattern, test_name):
                findings.append(self._create_finding(
                    defect_id, rules, f"Test name matches: {pattern}"
                ))
        
        # Analyze stack trace patterns
        stack_trace = defect_data.get("stack_trace", "")
        for pattern, rules in self.analysis_rules["error_patterns"].items():
            if re.search(pattern, stack_trace, re.IGNORECASE):
                findings.append(self._create_finding(
                    defect_id, rules, f"Error pattern: {pattern}"
                ))
        
        # Determine overall stage
        if findings:
            stage_counts = {}
            for finding in findings:
                stage = finding.stage_caught.value
                stage_counts[stage] = stage_counts.get(stage, 0) + 1
            
            overall_stage = max(stage_counts, key=stage_counts.get)
            overall_stage_enum = PipelineStage(overall_stage)
            overall_confidence = sum(f.confidence for f in findings) / len(findings)
        else:
            overall_stage_enum = PipelineStage.IMPLEMENTATION
            overall_confidence = 0.5
        
        # Generate recommendations
        recommendations = self._generate_recommendations(findings)
        
        # Generate agent updates
        agent_updates = self._generate_agent_updates(findings, defect_id)
        
        report = RCCAReport(
            defect_id=defect_id,
            findings=findings,
            overall_stage=overall_stage_enum,
            overall_confidence=overall_confidence,
            recommendations=recommendations,
            agent_updates=agent_updates
        )
        
        # Save report
        self._save_rcca_report(report)
        
        return report
    
    def _create_finding(self, defect_id: str, rules: Dict[str, Any],
                       evidence: str) -> RCCAFinding:
        """Create an RCCA finding"""
        finding_id = f"RCCA-{defect_id}-{datetime.now().strftime('%H%M%S')}"
        
        return RCCAFinding(
            finding_id=finding_id,
            defect_id=defect_id,
            root_cause=rules.get("category", RootCauseCategory.IMPLEMENTATION).value,
            category=rules.get("category", RootCauseCategory.IMPLEMENTATION),
            stage_caught=rules.get("stage", PipelineStage.IMPLEMENTATION),
            stage_prevented=self._get_prevention_stage(rules.get("stage", PipelineStage.IMPLEMENTATION)),
            recommendation=rules.get("recommendation", f"Add validation in {rules.get('stage', 'implementation')} stage"),
            agent_responsible=rules.get("agent", "implement"),
            confidence=0.7,
            evidence=[evidence]
        )
    
    def _get_prevention_stage(self, current_stage: PipelineStage) -> PipelineStage:
        """Determine where the defect could have been prevented"""
        prevention_map = {
            PipelineStage.IDEATION: PipelineStage.IDEATION,
            PipelineStage.DESIGN: PipelineStage.IDEATION,
            PipelineStage.ARCHITECTURE: PipelineStage.DESIGN,
            PipelineStage.IMPLEMENTATION: PipelineStage.ARCHITECTURE,
            PipelineStage.VALIDATION: PipelineStage.IMPLEMENTATION
        }
        return prevention_map.get(current_stage, PipelineStage.IMPLEMENTATION)
    
    def _generate_recommendations(self, findings: List[RCCAFinding]) -> List[str]:
        """Generate recommendations based on findings"""
        recommendations = []
        
        stage_findings = {}
        for finding in findings:
            stage = finding.stage_caught.value
            if stage not in stage_findings:
                stage_findings[stage] = []
            stage_findings[stage].append(finding)
        
        if "ideation" in stage_findings:
            recommendations.append("Update ideation agent to clarify requirements for this type of feature")
        
        if "design" in stage_findings:
            recommendations.append("Update design agent to add validation rules for this pattern")
        
        if "architecture" in stage_findings:
            recommendations.append("Update architect agent to add constraints for this pattern")
        
        if "implementation" in stage_findings:
            recommendations.append("Update implement agent to add error handling for this pattern")
        
        return recommendations
    
    def _generate_agent_updates(self, findings: List[RCCAFinding],
                               defect_id: str) -> List[Dict[str, Any]]:
        """Generate agent update recommendations"""
        updates = []
        
        agent_findings = {}
        for finding in findings:
            agent = finding.agent_responsible
            if agent not in agent_findings:
                agent_findings[agent] = []
            agent_findings[agent].append(finding)
        
        for agent, agent_finding_list in agent_findings.items():
            updates.append({
                "agent": agent,
                "update_type": "prevention_rule",
                "defect_id": defect_id,
                "description": agent_finding_list[0].recommendation,
                "rule": f"Based on defect {defect_id}: {agent_finding_list[0].recommendation}"
            })
        
        return updates
    
    def _save_rcca_report(self, report: RCCAReport):
        """Save RCCA report"""
        report_file = self.rcca_path / f"{report.defect_id}.json"
        
        data = {
            "defect_id": report.defect_id,
            "overall_stage": report.overall_stage.value,
            "overall_confidence": report.overall_confidence,
            "recommendations": report.recommendations,
            "agent_updates": report.agent_updates,
            "findings": [asdict(f) for f in report.findings],
            "created_at": datetime.now().isoformat()
        }
        
        # Convert enums to values
        for finding in data["findings"]:
            if hasattr(finding["category"], "value"):
                finding["category"] = finding["category"].value
            if hasattr(finding["stage_caught"], "value"):
                finding["stage_caught"] = finding["stage_caught"].value
            if hasattr(finding["stage_prevented"], "value"):
                finding["stage_prevented"] = finding["stage_prevented"].value
        
        with open(report_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def get_rcca_report(self, defect_id: str) -> Optional[RCCAReport]:
        """Get RCCA report for a defect"""
        report_file = self.rcca_path / f"{defect_id}.json"
        if not report_file.exists():
            return None
        
        with open(report_file) as f:
            data = json.load(f)
        
        findings = []
        for finding_data in data.get("findings", []):
            findings.append(RCCAFinding(
                finding_id=finding_data["finding_id"],
                defect_id=finding_data["defect_id"],
                root_cause=finding_data["root_cause"],
                category=RootCauseCategory(finding_data["category"]),
                stage_caught=PipelineStage(finding_data["stage_caught"]),
                stage_prevented=PipelineStage(finding_data["stage_prevented"]),
                recommendation=finding_data["recommendation"],
                agent_responsible=finding_data["agent_responsible"],
                confidence=finding_data["confidence"],
                evidence=finding_data.get("evidence")
            ))
        
        return RCCAReport(
            defect_id=data["defect_id"],
            findings=findings,
            overall_stage=PipelineStage(data["overall_stage"]),
            overall_confidence=data["overall_confidence"],
            recommendations=data["recommendations"],
            agent_updates=data["agent_updates"]
        )
    
    def get_rcca_summary(self) -> Dict[str, Any]:
        """Get RCCA summary"""
        reports = []
        
        for report_file in self.rcca_path.glob("*.json"):
            with open(report_file) as f:
                data = json.load(f)
            reports.append(data)
        
        stage_counts = {}
        agent_counts = {}
        
        for report in reports:
            stage = report.get("overall_stage", "unknown")
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
            
            for update in report.get("agent_updates", []):
                agent = update.get("agent", "unknown")
                agent_counts[agent] = agent_counts.get(agent, 0) + 1
        
        return {
            "total_reports": len(reports),
            "by_stage": stage_counts,
            "by_agent": agent_counts
        }
