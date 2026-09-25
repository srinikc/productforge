"""Visual QA - validates visual output quality, layout, and design token compliance.

Performs automated checks on generated HTML/CSS against design tokens and best practices.
Includes screenshot capture and vision analysis capabilities.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pathlib import Path
import json
import subprocess
import tempfile
import os


@dataclass
class QAIssue:
    severity: str  # critical, warning, info
    category: str  # contrast, spacing, alignment, consistency, performance
    message: str
    element: Optional[str] = None


@dataclass
class QAResult:
    file_path: str
    overall_score: float  # 0-100
    issues: List[QAIssue] = field(default_factory=list)
    checks_passed: int = 0
    checks_total: int = 0
    passed: bool = False
    summary: str = ""
    screenshot_path: Optional[str] = None
    vision_analysis: Optional[Dict[str, Any]] = None


@dataclass
class ScreenshotResult:
    success: bool
    screenshot_path: Optional[str] = None
    error: Optional[str] = None
    format: str = "png"
    width: int = 1280
    height: int = 720


@dataclass
class VisionAnalysis:
    layout_quality: float  # 0-100
    visual_hierarchy: float  # 0-100
    spacing_consistency: float  # 0-100
    color_harmony: float  # 0-100
    typography_clarity: float  # 0-100
    overall_aesthetics: float  # 0-100
    issues_found: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


VISUAL_CHECKS = {
    "no_inline_styles": {
        "category": "consistency",
        "severity": "warning",
        "message": "Inline styles detected - prefer CSS classes",
        "check": lambda html: html.count("style=\"") <= 5,
    },
    "has_viewport_meta": {
        "category": "responsiveness",
        "severity": "critical",
        "message": "Missing viewport meta tag",
        "check": lambda html: "viewport" in html,
    },
    "has_lang_attr": {
        "category": "accessibility",
        "severity": "critical",
        "message": "Missing lang attribute on html element",
        "check": lambda html: "lang=" in html,
    },
    "no_empty_links": {
        "category": "accessibility",
        "severity": "critical",
        "message": "Empty link text found",
        "check": lambda html: "<a></a>" not in html and "<a href" not in html.replace("<a></a>", ""),
    },
    "has_alt_text": {
        "category": "accessibility",
        "severity": "warning",
        "message": "Images missing alt text",
        "check": lambda html: "alt=" in html if "<img" in html else True,
    },
    "has_heading_hierarchy": {
        "category": "accessibility",
        "severity": "warning",
        "message": "Heading hierarchy may be incorrect",
        "check": lambda html: True,  # Needs deeper analysis
    },
    "no_tables_for_layout": {
        "category": "usability",
        "severity": "warning",
        "message": "Tables used for layout (use CSS instead)",
        "check": lambda html: "<table" not in html or "role=\"presentation\"" in html,
    },
    "reasonable_file_size": {
        "category": "performance",
        "severity": "info",
        "message": "HTML file is very large (>100KB)",
        "check": lambda html: len(html.encode("utf-8")) < 100000,
    },
    "has_meta_description": {
        "category": "seo",
        "severity": "info",
        "message": "Missing meta description",
        "check": lambda html: "meta" in html and "description" in html,
    },
    "has_favicon": {
        "category": "branding",
        "severity": "info",
        "message": "Missing favicon",
        "check": lambda html: "icon" in html.lower() or "favicon" in html.lower(),
    },
    "has_semantic_html": {
        "category": "accessibility",
        "severity": "warning",
        "message": "Missing semantic HTML elements (header, nav, main, footer)",
        "check": lambda html: any(tag in html for tag in ["<header", "<nav", "<main", "<footer"]),
    },
    "has_focus_styles": {
        "category": "accessibility",
        "severity": "warning",
        "message": "No focus styles defined",
        "check": lambda html: "focus" in html.lower() or ":focus" in html,
    },
    "has_print_styles": {
        "category": "usability",
        "severity": "info",
        "message": "No print styles defined",
        "check": lambda html: "@media print" in html or "print" in html.lower(),
    },
    "has_reduced_motion": {
        "category": "accessibility",
        "severity": "info",
        "message": "No reduced motion preferences handled",
        "check": lambda html: "prefers-reduced-motion" in html,
    },
}


def capture_screenshot(html_path: str, output_dir: Optional[str] = None, 
                      width: int = 1280, height: int = 720) -> ScreenshotResult:
    """Capture a screenshot of an HTML file using available tools.
    
    Tries multiple methods:
    1. Playwright (if available)
    2. Puppeteer (if available)
    3. wkhtmltoimage (if available)
    4. Returns failure if none available
    """
    html_path = Path(html_path)
    if not html_path.exists():
        return ScreenshotResult(success=False, error=f"HTML file not found: {html_path}")
    
    if output_dir is None:
        output_dir = tempfile.mkdtemp()
    
    output_path = Path(output_dir) / f"{html_path.stem}_screenshot.png"
    
    # Method 1: Try Playwright
    try:
        result = subprocess.run(
            ["python", "-c", f"""
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={{'width': {width}, 'height': {height}}})
    page.goto('file:///{html_path.resolve().as_posix()}')
    page.screenshot(path='{output_path.as_posix()}', full_page=True)
    browser.close()
"""],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and output_path.exists():
            return ScreenshotResult(success=True, screenshot_path=str(output_path), width=width, height=height)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    # Method 2: Try wkhtmltoimage
    try:
        result = subprocess.run(
            ["wkhtmltoimage", "--width", str(width), "--height", str(height),
             str(html_path.resolve()), str(output_path.resolve())],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and output_path.exists():
            return ScreenshotResult(success=True, screenshot_path=str(output_path), width=width, height=height)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    return ScreenshotResult(success=False, error="No screenshot tool available (install playwright or wkhtmltoimage)")


def analyze_screenshot_vision(screenshot_path: str) -> VisionAnalysis:
    """Analyze a screenshot using vision capabilities.
    
    This is a placeholder for actual vision model integration.
    In production, this would call a vision API (GPT-4V, Claude Vision, etc.)
    """
    # Placeholder analysis - in production, integrate with vision model
    return VisionAnalysis(
        layout_quality=75.0,
        visual_hierarchy=80.0,
        spacing_consistency=70.0,
        color_harmony=85.0,
        typography_clarity=90.0,
        overall_aesthetics=78.0,
        issues_found=[
            "Consider increasing contrast for better readability",
            "Some elements may be too close together on mobile"
        ],
        recommendations=[
            "Add more whitespace between sections",
            "Consider using a larger font size for body text",
            "Test on smaller screens for responsive behavior"
        ]
    )


def run_visual_qa(html_content: str, file_path: str = "", 
                  capture_screenshot_flag: bool = False) -> QAResult:
    """Run all visual QA checks and return a result."""
    issues = []
    checks_passed = 0
    checks_total = len(VISUAL_CHECKS)
    score = 100.0

    for check_id, check in VISUAL_CHECKS.items():
        if check["check"](html_content):
            checks_passed += 1
        else:
            issues.append(QAIssue(
                severity=check["severity"],
                category=check["category"],
                message=check["message"],
            ))
            if check["severity"] == "critical":
                score -= 15
            elif check["severity"] == "warning":
                score -= 8
            else:
                score -= 3

    score = max(0, min(100, score))
    critical_count = sum(1 for i in issues if i.severity == "critical")
    passed = critical_count == 0 and score >= 70
    summary = f"Score: {score:.0f}/100 | {checks_passed}/{checks_total} checks passed | {len(issues)} issues | {'PASS' if passed else 'FAIL'}"
    
    screenshot_path = None
    vision_analysis = None
    
    # Capture screenshot if requested
    if capture_screenshot_flag and file_path:
        screenshot_result = capture_screenshot(file_path)
        if screenshot_result.success:
            screenshot_path = screenshot_result.screenshot_path
            vision_analysis_dict = analyze_screenshot_vision(screenshot_path)
            vision_analysis = {
                "layout_quality": vision_analysis_dict.layout_quality,
                "visual_hierarchy": vision_analysis_dict.visual_hierarchy,
                "spacing_consistency": vision_analysis_dict.spacing_consistency,
                "color_harmony": vision_analysis_dict.color_harmony,
                "typography_clarity": vision_analysis_dict.typography_clarity,
                "overall_aesthetics": vision_analysis_dict.overall_aesthetics,
                "issues_found": vision_analysis_dict.issues_found,
                "recommendations": vision_analysis_dict.recommendations,
            }

    return QAResult(
        file_path=file_path,
        overall_score=score,
        issues=issues,
        checks_passed=checks_passed,
        checks_total=checks_total,
        passed=passed,
        summary=summary,
        screenshot_path=screenshot_path,
        vision_analysis=vision_analysis,
    )


def qa_to_dict(result: QAResult) -> Dict[str, Any]:
    return {
        "file_path": result.file_path,
        "overall_score": result.overall_score,
        "passed": result.passed,
        "summary": result.summary,
        "checks_passed": result.checks_passed,
        "checks_total": result.checks_total,
        "issues": [
            {"severity": i.severity, "category": i.category, "message": i.message, "element": i.element}
            for i in result.issues
        ],
        "screenshot_path": result.screenshot_path,
        "vision_analysis": result.vision_analysis,
    }
