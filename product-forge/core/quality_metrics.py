"""Quality Metrics - Track Product Forge performance and quality.

Tracks:
- Product Forge Quality Score
- Cost per Accepted Product
- Iterations per Product
- Human Corrections per Product
- Time to Accepted Product
- Input/Output Tokens per Product
"""
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path


@dataclass
class QualityMetrics:
    """Quality metrics for a pipeline run."""
    run_id: str
    project: str
    started_at: str = ""
    completed_at: str = ""
    
    # Core metrics
    quality_score: float = 0.0  # 0-100
    cost_per_product: float = 0.0  # USD
    iterations_per_product: float = 0.0
    human_corrections: int = 0
    time_to_accepted: float = 0.0  # seconds
    
    # Token metrics
    input_tokens_per_product: int = 0
    output_tokens_per_product: int = 0
    total_tokens: int = 0
    
    # Cost metrics
    total_cost: float = 0.0
    budget_utilization: float = 0.0  # percent
    
    # Quality breakdown
    design_quality: float = 0.0
    code_quality: float = 0.0
    test_coverage: float = 0.0
    security_score: float = 0.0
    nfr_compliance: float = 0.0
    
    # Human feedback
    approval_rate: float = 0.0  # percent approved on first try
    rejection_count: int = 0
    revision_count: int = 0
    
    created_at: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "run_id": self.run_id,
            "project": self.project,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "quality_score": self.quality_score,
            "cost_per_product": self.cost_per_product,
            "iterations_per_product": self.iterations_per_product,
            "human_corrections": self.human_corrections,
            "time_to_accepted": self.time_to_accepted,
            "input_tokens_per_product": self.input_tokens_per_product,
            "output_tokens_per_product": self.output_tokens_per_product,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "budget_utilization": self.budget_utilization,
            "design_quality": self.design_quality,
            "code_quality": self.code_quality,
            "test_coverage": self.test_coverage,
            "security_score": self.security_score,
            "nfr_compliance": self.nfr_compliance,
            "approval_rate": self.approval_rate,
            "rejection_count": self.rejection_count,
            "revision_count": self.revision_count,
            "created_at": self.created_at,
        }


def calculate_quality_score(metrics: QualityMetrics) -> float:
    """Calculate overall quality score from component metrics."""
    weights = {
        "design": 0.2,
        "code": 0.25,
        "tests": 0.2,
        "security": 0.15,
        "nfr": 0.1,
        "human": 0.1,
    }
    
    score = (
        metrics.design_quality * weights["design"] +
        metrics.code_quality * weights["code"] +
        metrics.test_coverage * weights["tests"] +
        metrics.security_score * weights["security"] +
        metrics.nfr_compliance * weights["nfr"] +
        metrics.approval_rate * weights["human"]
    )
    
    return min(100.0, max(0.0, score))


def calculate_cost_efficiency(metrics: QualityMetrics) -> float:
    """Calculate cost efficiency (quality per dollar)."""
    if metrics.total_cost <= 0:
        return 0.0
    return metrics.quality_score / metrics.total_cost


def calculate_time_efficiency(metrics: QualityMetrics) -> float:
    """Calculate time efficiency (quality per hour)."""
    if metrics.time_to_accepted <= 0:
        return 0.0
    hours = metrics.time_to_accepted / 3600.0
    return metrics.quality_score / hours


def generate_quality_report(metrics: QualityMetrics) -> str:
    """Generate a quality metrics report."""
    efficiency = calculate_cost_efficiency(metrics)
    time_eff = calculate_time_efficiency(metrics)
    
    report = f"""# Product Forge Quality Report

## Run: {metrics.run_id}
## Project: {metrics.project}

## Overall Quality Score: {metrics.quality_score:.1f}/100

## Core Metrics

| Metric | Value |
|--------|-------|
| Cost per Product | ${metrics.cost_per_product:.2f} |
| Iterations per Product | {metrics.iterations_per_product:.1f} |
| Human Corrections | {metrics.human_corrections} |
| Time to Accepted | {metrics.time_to_accepted/3600:.1f} hours |
| Cost Efficiency | {efficiency:.1f} quality/$ |
| Time Efficiency | {time_eff:.1f} quality/hour |

## Token Metrics

| Metric | Value |
|--------|-------|
| Input Tokens | {metrics.input_tokens_per_product:,} |
| Output Tokens | {metrics.output_tokens_per_product:,} |
| Total Tokens | {metrics.total_tokens:,} |
| Total Cost | ${metrics.total_cost:.2f} |
| Budget Utilization | {metrics.budget_utilization:.1f}% |

## Quality Breakdown

| Category | Score |
|----------|-------|
| Design Quality | {metrics.design_quality:.1f}/100 |
| Code Quality | {metrics.code_quality:.1f}/100 |
| Test Coverage | {metrics.test_coverage:.1f}/100 |
| Security Score | {metrics.security_score:.1f}/100 |
| NFR Compliance | {metrics.nfr_compliance:.1f}/100 |

## Human Feedback

| Metric | Value |
|--------|-------|
| Approval Rate | {metrics.approval_rate:.1f}% |
| Rejections | {metrics.rejection_count} |
| Revisions | {metrics.revision_count} |

## Benchmarks

| Target | Status |
|--------|--------|
| Quality Score >= 80 | {'PASS' if metrics.quality_score >= 80 else 'FAIL'} |
| Cost <= $3.00 | {'PASS' if metrics.total_cost <= 3.00 else 'FAIL'} |
| Time <= 2 hours | {'PASS' if metrics.time_to_accepted <= 7200 else 'FAIL'} |
| Approval Rate >= 80% | {'PASS' if metrics.approval_rate >= 80 else 'FAIL'} |

---
*Generated by Quality Metrics module*
"""
    
    return report


def save_quality_metrics(metrics: QualityMetrics, products_dir: str = "products") -> str:
    """Save quality metrics to file."""
    project_dir = os.path.join(products_dir, metrics.project)
    os.makedirs(project_dir, exist_ok=True)
    
    metrics_file = os.path.join(project_dir, "quality-metrics.json")
    with open(metrics_file, 'w', encoding='utf-8') as f:
        json.dump(metrics.to_dict(), f, indent=2, ensure_ascii=False)
    
    return metrics_file


def load_quality_metrics(project: str, products_dir: str = "products") -> Optional[QualityMetrics]:
    """Load quality metrics from file."""
    metrics_file = os.path.join(products_dir, project, "quality-metrics.json")
    
    if not os.path.exists(metrics_file):
        return None
    
    with open(metrics_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    metrics = QualityMetrics(
        run_id=data.get("run_id", ""),
        project=data.get("project", project),
        started_at=data.get("started_at", ""),
        completed_at=data.get("completed_at", ""),
        quality_score=data.get("quality_score", 0.0),
        cost_per_product=data.get("cost_per_product", 0.0),
        iterations_per_product=data.get("iterations_per_product", 0.0),
        human_corrections=data.get("human_corrections", 0),
        time_to_accepted=data.get("time_to_accepted", 0.0),
        input_tokens_per_product=data.get("input_tokens_per_product", 0),
        output_tokens_per_product=data.get("output_tokens_per_product", 0),
        total_tokens=data.get("total_tokens", 0),
        total_cost=data.get("total_cost", 0.0),
        budget_utilization=data.get("budget_utilization", 0.0),
        design_quality=data.get("design_quality", 0.0),
        code_quality=data.get("code_quality", 0.0),
        test_coverage=data.get("test_coverage", 0.0),
        security_score=data.get("security_score", 0.0),
        nfr_compliance=data.get("nfr_compliance", 0.0),
        approval_rate=data.get("approval_rate", 0.0),
        rejection_count=data.get("rejection_count", 0),
        revision_count=data.get("revision_count", 0),
        created_at=data.get("created_at", ""),
    )
    
    return metrics


if __name__ == "__main__":
    # Test quality metrics
    metrics = QualityMetrics(
        run_id="test-run-001",
        project="test-project",
        started_at=datetime.now().isoformat(),
        quality_score=85.0,
        total_cost=2.50,
        total_tokens=50000,
        design_quality=80.0,
        code_quality=85.0,
        test_coverage=90.0,
        security_score=88.0,
        nfr_compliance=82.0,
        approval_rate=85.0,
        created_at=datetime.now().isoformat(),
    )
    
    metrics.quality_score = calculate_quality_score(metrics)
    print(f"Quality score: {metrics.quality_score:.1f}")
    
    report = generate_quality_report(metrics)
    print(f"\nReport generated ({len(report)} chars)")
