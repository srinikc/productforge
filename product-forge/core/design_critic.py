"""Design Critic - reviews design artifacts for quality, consistency, and completeness.

Evaluates design outputs against best practices and flags issues.
Used as a review stage in the pipeline after design agent completes.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CritiqueConfig:
    """Configurable thresholds for design critique."""
    critical_penalty: float = 20.0
    warning_penalty: float = 10.0
    info_penalty: float = 5.0
    min_score_to_pass: float = 60.0
    max_critical_issues: int = 0


@dataclass
class CritiqueIssue:
    severity: str  # critical, warning, info
    category: str  # consistency, completeness, accessibility, usability, branding
    message: str
    line_ref: Optional[str] = None


@dataclass
class CritiqueResult:
    artifact_path: str
    overall_score: float  # 0-100
    issues: List[CritiqueIssue] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    passed: bool = False
    summary: str = ""
    config_used: Optional[CritiqueConfig] = None


DESIGN_CHECKS = {
    "has_components": {
        "category": "completeness",
        "severity": "warning",
        "message": "No component definitions found in design",
        "check": lambda c: "component" in c.lower() or "widget" in c.lower(),
    },
    "has_layout": {
        "category": "completeness",
        "severity": "warning",
        "message": "No layout structure described",
        "check": lambda c: "layout" in c.lower() or "grid" in c.lower() or "flex" in c.lower(),
    },
    "has_typography": {
        "category": "consistency",
        "severity": "info",
        "message": "No typography system defined",
        "check": lambda c: "font" in c.lower() or "typography" in c.lower() or "heading" in c.lower(),
    },
    "has_colors": {
        "category": "consistency",
        "severity": "info",
        "message": "No color system defined",
        "check": lambda c: "color" in c.lower() or "palette" in c.lower() or "theme" in c.lower(),
    },
    "has_spacing": {
        "category": "consistency",
        "severity": "info",
        "message": "No spacing system defined",
        "check": lambda c: "spacing" in c.lower() or "margin" in c.lower() or "padding" in c.lower(),
    },
    "has_responsive": {
        "category": "usability",
        "severity": "warning",
        "message": "No responsive design considerations",
        "check": lambda c: "responsive" in c.lower() or "mobile" in c.lower() or "breakpoint" in c.lower(),
    },
    "has_accessibility": {
        "category": "accessibility",
        "severity": "critical",
        "message": "No accessibility considerations mentioned",
        "check": lambda c: "accessibility" in c.lower() or "a11y" in c.lower() or "aria" in c.lower(),
    },
    "has_states": {
        "category": "completeness",
        "severity": "warning",
        "message": "No component states described (hover, active, disabled)",
        "check": lambda c: "hover" in c.lower() or "active" in c.lower() or "disabled" in c.lower() or "state" in c.lower(),
    },
    "has_error_handling": {
        "category": "completeness",
        "severity": "warning",
        "message": "No error handling or error states described",
        "check": lambda c: "error" in c.lower() or "validation" in c.lower() or "invalid" in c.lower(),
    },
    "has_loading_states": {
        "category": "usability",
        "severity": "info",
        "message": "No loading states described",
        "check": lambda c: "loading" in c.lower() or "spinner" in c.lower() or "skeleton" in c.lower(),
    },
    "has_navigation": {
        "category": "usability",
        "severity": "warning",
        "message": "No navigation structure defined",
        "check": lambda c: "navigation" in c.lower() or "menu" in c.lower() or "nav" in c.lower(),
    },
    "has_user_flows": {
        "category": "usability",
        "severity": "info",
        "message": "No user flows described",
        "check": lambda c: "flow" in c.lower() or "journey" in c.lower() or "step" in c.lower(),
    },
    "has_branding": {
        "category": "branding",
        "severity": "info",
        "message": "No branding or visual identity defined",
        "check": lambda c: "brand" in c.lower() or "identity" in c.lower() or "logo" in c.lower(),
    },
    "has_dark_mode": {
        "category": "consistency",
        "severity": "info",
        "message": "No dark mode or theme switching considered",
        "check": lambda c: "dark" in c.lower() or "theme" in c.lower() or "mode" in c.lower(),
    },
}


def critique_design(content: str, artifact_path: str = "", config: Optional[CritiqueConfig] = None) -> CritiqueResult:
    """Run all design checks and return a critique result."""
    if config is None:
        config = CritiqueConfig()
    
    issues = []
    strengths = []
    score = 100.0

    for check_id, check in DESIGN_CHECKS.items():
        if check["check"](content):
            strengths.append(f"Good: {check['message'].replace('No ', 'Has ').replace('not found', 'present')}")
        else:
            issues.append(CritiqueIssue(
                severity=check["severity"],
                category=check["category"],
                message=check["message"],
            ))
            if check["severity"] == "critical":
                score -= config.critical_penalty
            elif check["severity"] == "warning":
                score -= config.warning_penalty
            else:
                score -= config.info_penalty

    score = max(0, min(100, score))
    critical_count = sum(1 for i in issues if i.severity == "critical")
    warning_count = sum(1 for i in issues if i.severity == "warning")

    passed = critical_count <= config.max_critical_issues and score >= config.min_score_to_pass
    summary = f"Score: {score:.0f}/100 | {len(issues)} issues ({critical_count} critical, {warning_count} warnings) | {'PASS' if passed else 'FAIL'}"

    return CritiqueResult(
        artifact_path=artifact_path,
        overall_score=score,
        issues=issues,
        strengths=strengths,
        passed=passed,
        summary=summary,
        config_used=config,
    )


def critique_to_dict(result: CritiqueResult) -> Dict[str, Any]:
    return {
        "artifact_path": result.artifact_path,
        "overall_score": result.overall_score,
        "passed": result.passed,
        "summary": result.summary,
        "issues": [
            {"severity": i.severity, "category": i.category, "message": i.message, "line_ref": i.line_ref}
            for i in result.issues
        ],
        "strengths": result.strengths,
        "config": {
            "critical_penalty": result.config_used.critical_penalty if result.config_used else 20.0,
            "warning_penalty": result.config_used.warning_penalty if result.config_used else 10.0,
            "info_penalty": result.config_used.info_penalty if result.config_used else 5.0,
            "min_score_to_pass": result.config_used.min_score_to_pass if result.config_used else 60.0,
            "max_critical_issues": result.config_used.max_critical_issues if result.config_used else 0,
        } if result.config_used else None,
    }
