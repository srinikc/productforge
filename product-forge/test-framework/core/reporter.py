"""
Test Reporter - Generates test reports and metrics
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from pathlib import Path

@dataclass
class TestMetrics:
    total_tests: int
    passed: int
    failed: int
    skipped: int
    errors: int
    duration: float
    coverage: Optional[float]
    pass_rate: float

@dataclass
class FeatureStatus:
    feature_id: str
    feature_name: str
    status: str  # working, broken, partial
    last_working: Optional[str]
    last_broken: Optional[str]
    test_coverage: float

@dataclass
class TestComment:
    """Comment for a test run explaining WHY it was run"""
    test_id: str
    comment: str
    phase: str  # e.g., "4a", "4b", "4c"
    feature: str  # e.g., "auth", "dashboard"
    reason: str  # e.g., "phase_test", "fix_verification", "regression_check"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class TraceabilityEntry:
    """Traceability matrix entry: Requirement → Feature → Tests → Results"""
    requirement_id: str  # e.g., "FR-1"
    requirement_name: str
    feature_id: str  # e.g., "auth"
    feature_name: str
    test_ids: List[str]  # e.g., ["test_auth_login", "test_auth_register"]
    last_result: str  # "passed", "failed", "not_run"
    coverage: float  # 0-100%

class TestReporter:
    """Generates test reports and tracks metrics"""
    
    def __init__(self, project: str, reports_path: Optional[str] = None):
        self.project = project
        self.reports_path = Path(reports_path or Path(__file__).parent.parent / "reports" / project)
        self.reports_path.mkdir(parents=True, exist_ok=True)
        self.metrics_file = self.reports_path / "metrics.json"
        self.trends_file = self.reports_path / "trends.json"
        self.features_file = self.reports_path / "features.json"
        
    def record_run(self, suite_result: Any) -> Dict[str, Any]:
        """Record test run results"""
        report = {
            "report_id": f"RPT-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "suite_id": suite_result.suite_id,
            "project": self.project,
            "suite_name": suite_result.suite_name,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total": suite_result.total,
                "passed": suite_result.passed,
                "failed": suite_result.failed,
                "skipped": suite_result.skipped,
                "errors": suite_result.errors,
                "duration": suite_result.duration,
                "pass_rate": (suite_result.passed / suite_result.total * 100) if suite_result.total > 0 else 0
            },
            "tests": [asdict(t) for t in suite_result.tests] if suite_result.tests else [],
            "status": suite_result.status
        }
        
        # Save report
        report_file = self.reports_path / f"{report['report_id']}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Update metrics
        self._update_metrics(report)
        
        # Update trends
        self._update_trends(report)
        
        return report
    
    def _update_metrics(self, report: Dict[str, Any]):
        """Update overall metrics"""
        metrics = self._load_metrics()
        
        metrics["total_tests"] += report["summary"]["total"]
        metrics["total_passed"] += report["summary"]["passed"]
        metrics["total_failed"] += report["summary"]["failed"]
        metrics["total_skipped"] += report["summary"]["skipped"]
        metrics["total_errors"] += report["summary"]["errors"]
        metrics["total_duration"] += report["summary"]["duration"]
        metrics["run_count"] += 1
        metrics["last_run"] = report["timestamp"]
        
        if metrics["total_tests"] > 0:
            metrics["overall_pass_rate"] = (metrics["total_passed"] / metrics["total_tests"]) * 100
        
        with open(self.metrics_file, 'w') as f:
            json.dump(metrics, f, indent=2)
    
    def _load_metrics(self) -> Dict[str, Any]:
        """Load metrics from file"""
        if self.metrics_file.exists():
            with open(self.metrics_file) as f:
                return json.load(f)
        
        return {
            "total_tests": 0,
            "total_passed": 0,
            "total_failed": 0,
            "total_skipped": 0,
            "total_errors": 0,
            "total_duration": 0,
            "run_count": 0,
            "overall_pass_rate": 0,
            "last_run": None
        }
    
    def _update_trends(self, report: Dict[str, Any]):
        """Update trend data"""
        trends = self._load_trends()
        
        trends.append({
            "date": report["timestamp"],
            "suite": report["suite_name"],
            "total": report["summary"]["total"],
            "passed": report["summary"]["passed"],
            "failed": report["summary"]["failed"],
            "duration": report["summary"]["duration"]
        })
        
        # Keep last 100 entries
        trends = trends[-100:]
        
        with open(self.trends_file, 'w') as f:
            json.dump(trends, f, indent=2)
    
    def _load_trends(self) -> List[Dict[str, Any]]:
        """Load trends from file"""
        if self.trends_file.exists():
            with open(self.trends_file) as f:
                return json.load(f)
        return []
    
    def update_feature_status(self, feature_id: str, feature_name: str,
                             status: str, test_coverage: float):
        """Update feature status"""
        features = self._load_features()
        
        feature = None
        for f in features:
            if f["feature_id"] == feature_id:
                feature = f
                break
        
        if not feature:
            feature = {
                "feature_id": feature_id,
                "feature_name": feature_name,
                "status": status,
                "last_working": None,
                "last_broken": None,
                "test_coverage": test_coverage,
                "history": []
            }
            features.append(feature)
        
        old_status = feature["status"]
        feature["status"] = status
        feature["test_coverage"] = test_coverage
        
        if status == "working" and old_status != "working":
            feature["last_working"] = datetime.now().isoformat()
        elif status == "broken" and old_status != "broken":
            feature["last_broken"] = datetime.now().isoformat()
        
        feature["history"].append({
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "coverage": test_coverage
        })
        
        feature["history"] = feature["history"][-50:]
        
        with open(self.features_file, 'w') as f:
            json.dump(features, f, indent=2)
    
    def _load_features(self) -> List[Dict[str, Any]]:
        """Load features from file"""
        if self.features_file.exists():
            with open(self.features_file) as f:
                return json.load(f)
        return []
    
    def detect_regressions(self) -> List[Dict[str, Any]]:
        """Detect features that were working, now broken"""
        features = self._load_features()
        regressions = []
        
        for feature in features:
            if feature["status"] == "broken" and feature.get("last_working"):
                regressions.append({
                    "feature_id": feature["feature_id"],
                    "feature_name": feature["feature_name"],
                    "last_working": feature["last_working"],
                    "regression_detected": datetime.now().isoformat()
                })
        
        return regressions
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        return self._load_metrics()
    
    def get_trends(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get trend data for last N days"""
        trends = self._load_trends()
        
        cutoff = datetime.now() - timedelta(days=days)
        filtered = []
        
        for trend in trends:
            trend_date = datetime.fromisoformat(trend["date"])
            if trend_date >= cutoff:
                filtered.append(trend)
        
        return filtered
    
    def get_feature_status(self) -> List[Dict[str, Any]]:
        """Get feature status"""
        return self._load_features()
    
    def generate_summary(self) -> Dict[str, Any]:
        """Generate summary report"""
        metrics = self.get_metrics()
        features = self.get_feature_status()
        regressions = self.detect_regressions()
        
        return {
            "project": self.project,
            "metrics": metrics,
            "features": {
                "total": len(features),
                "working": sum(1 for f in features if f["status"] == "working"),
                "broken": sum(1 for f in features if f["status"] == "broken"),
                "partial": sum(1 for f in features if f["status"] == "partial")
            },
            "regressions": regressions,
            "generated_at": datetime.now().isoformat()
        }
    
    def add_test_comment(self, test_id: str, comment: str, phase: str, 
                         feature: str, reason: str):
        """Add a comment to a test run explaining WHY it was run"""
        comments_file = self.reports_path / "test-comments.json"
        
        if comments_file.exists():
            with open(comments_file) as f:
                comments = json.load(f)
        else:
            comments = []
        
        comments.append({
            "test_id": test_id,
            "comment": comment,
            "phase": phase,
            "feature": feature,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        })
        
        with open(comments_file, 'w') as f:
            json.dump(comments, f, indent=2)
    
    def get_test_comments(self, phase: str = None) -> List[Dict[str, Any]]:
        """Get test comments, optionally filtered by phase"""
        comments_file = self.reports_path / "test-comments.json"
        
        if not comments_file.exists():
            return []
        
        with open(comments_file) as f:
            comments = json.load(f)
        
        if phase:
            comments = [c for c in comments if c.get("phase") == phase]
        
        return comments
    
    def add_traceability_entry(self, requirement_id: str, requirement_name: str,
                               feature_id: str, feature_name: str, 
                               test_ids: List[str], last_result: str, coverage: float):
        """Add entry to traceability matrix"""
        trace_file = self.reports_path / "traceability.json"
        
        if trace_file.exists():
            with open(trace_file) as f:
                traceability = json.load(f)
        else:
            traceability = []
        
        # Update existing entry or add new
        existing = next((t for t in traceability if t["requirement_id"] == requirement_id), None)
        
        if existing:
            existing["test_ids"] = test_ids
            existing["last_result"] = last_result
            existing["coverage"] = coverage
            existing["updated_at"] = datetime.now().isoformat()
        else:
            traceability.append({
                "requirement_id": requirement_id,
                "requirement_name": requirement_name,
                "feature_id": feature_id,
                "feature_name": feature_name,
                "test_ids": test_ids,
                "last_result": last_result,
                "coverage": coverage,
                "created_at": datetime.now().isoformat()
            })
        
        with open(trace_file, 'w') as f:
            json.dump(traceability, f, indent=2)
    
    def get_traceability_matrix(self) -> List[Dict[str, Any]]:
        """Get full traceability matrix"""
        trace_file = self.reports_path / "traceability.json"
        
        if not trace_file.exists():
            return []
        
        with open(trace_file) as f:
            return json.load(f)
    
    def get_traceability_summary(self) -> Dict[str, Any]:
        """Get traceability summary"""
        matrix = self.get_traceability_matrix()
        
        return {
            "total_requirements": len(matrix),
            "fully_tested": sum(1 for t in matrix if t["coverage"] >= 80),
            "partially_tested": sum(1 for t in matrix if 0 < t["coverage"] < 80),
            "not_tested": sum(1 for t in matrix if t["coverage"] == 0),
            "all_passing": sum(1 for t in matrix if t["last_result"] == "passed"),
            "has_failures": sum(1 for t in matrix if t["last_result"] == "failed")
        }
