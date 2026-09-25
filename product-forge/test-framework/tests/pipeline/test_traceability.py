"""
Traceability Matrix Tests
Tests for the end-to-end traceability system
"""

import pytest
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.traceability import (
    TraceabilityMatrix, TraceEntry, TraceImplementation,
    TraceTest, TraceCoverage, QualityMetric, ImpactAnalysis, ChangeLog
)


class TestTraceabilityMatrix:
    """Test suite for TraceabilityMatrix"""

    def test_create_empty_trace(self, temp_products_dir, sample_project):
        """Test creating an empty traceability matrix"""
        trace = TraceabilityMatrix(sample_project, str(temp_products_dir))

        trace.save()

        assert trace.exists()
        assert trace.trace["project"] == sample_project
        assert trace.trace["version"] == "1.0.0"
        assert len(trace.trace["matrix"]) == 0

    def test_add_trace(self, temp_products_dir, sample_project):
        """Test adding a trace entry"""
        trace = TraceabilityMatrix(sample_project, str(temp_products_dir))

        entry = trace.add_trace("FR-1", "Authentication")
        trace.save()

        assert entry.requirement_id == "FR-1"
        assert entry.requirement_title == "Authentication"
        assert len(trace.trace["matrix"]) == 1

    def test_get_trace(self, temp_products_dir, sample_project):
        """Test getting a trace entry"""
        trace = TraceabilityMatrix(sample_project, str(temp_products_dir))

        trace.add_trace("FR-1", "Authentication")
        trace.save()
        entry = trace.get_trace("FR-1")

        assert entry is not None
        assert entry.requirement_id == "FR-1"

    def test_link_feature(self, temp_products_dir, sample_project):
        """Test linking a feature to a requirement"""
        trace = TraceabilityMatrix(sample_project, str(temp_products_dir))

        trace.add_trace("FR-1", "Authentication")
        trace.link_feature("FR-1", "F-001")
        trace.save()

        entry = trace.get_trace("FR-1")
        assert "F-001" in entry.features

    def test_link_architecture(self, temp_products_dir, sample_project):
        """Test linking an architecture decision to a requirement"""
        trace = TraceabilityMatrix(sample_project, str(temp_products_dir))

        trace.add_trace("FR-1", "Authentication")
        trace.link_architecture("FR-1", "ADR-001")
        trace.save()

        entry = trace.get_trace("FR-1")
        assert "ADR-001" in entry.architecture_decisions

    def test_link_design_section(self, temp_products_dir, sample_project):
        """Test linking a design section to a requirement"""
        trace = TraceabilityMatrix(sample_project, str(temp_products_dir))

        trace.add_trace("FR-1", "Authentication")
        trace.link_design_section("FR-1", "§2.1 Auth Flow")
        trace.save()

        entry = trace.get_trace("FR-1")
        assert "§2.1 Auth Flow" in entry.design_sections

    def test_link_implementation(self, temp_products_dir, sample_project):
        """Test linking an implementation file to a requirement"""
        trace = TraceabilityMatrix(sample_project, str(temp_products_dir))

        trace.add_trace("FR-1", "Authentication")
        trace.link_implementation("FR-1", "src/auth.py", "1-50")
        trace.save()

        entry = trace.get_trace("FR-1")
        assert len(entry.implementations) == 1
        assert entry.implementations[0].file == "src/auth.py"

    def test_link_test(self, temp_products_dir, sample_project):
        """Test linking a test to a requirement"""
        trace = TraceabilityMatrix(sample_project, str(temp_products_dir))

        trace.add_trace("FR-1", "Authentication")
        trace.link_test("FR-1", "test_auth", "tests/test_auth.py", "passing")
        trace.save()

        entry = trace.get_trace("FR-1")
        assert len(entry.tests) == 1
        assert entry.tests[0].status == "passing"

    def test_link_security_issue(self, temp_products_dir, sample_project):
        """Test linking a security issue to a requirement"""
        trace = TraceabilityMatrix(sample_project, str(temp_products_dir))

        trace.add_trace("FR-1", "Authentication")
        trace.link_security_issue("FR-1", "SEC-001")
        trace.save()

        entry = trace.get_trace("FR-1")
        assert "SEC-001" in entry.security_issues

    def test_compute_coverage(self, temp_products_dir, sample_project):
        """Test coverage computation"""
        trace = TraceabilityMatrix(sample_project, str(temp_products_dir))

        # Add requirements
        trace.add_trace("FR-1", "Auth")
        trace.add_trace("FR-2", "Dashboard")
        trace.add_trace("FR-3", "Search")

        # Link implementations for FR-1 and FR-2
        trace.link_implementation("FR-1", "src/auth.py")
        trace.link_implementation("FR-2", "src/dashboard.py")

        # Link tests for FR-1
        trace.link_test("FR-1", "test_auth", "tests/test_auth.py", "passing")
        trace.save()

        coverage = trace.get_coverage()

        assert coverage["total_requirements"] == 3
        assert coverage["implemented"] == 2
        assert coverage["tested"] == 1
        assert coverage["percent_implemented"] > 0

    def test_get_untested_requirements(self, temp_products_dir, sample_project):
        """Test getting untested requirements"""
        trace = TraceabilityMatrix(sample_project, str(temp_products_dir))

        trace.add_trace("FR-1", "Auth")
        trace.add_trace("FR-2", "Dashboard")

        trace.link_test("FR-1", "test_auth", "tests/test_auth.py", "passing")
        trace.save()

        untested = trace.get_untested_requirements()

        assert len(untested) == 1
        assert untested[0].requirement_id == "FR-2"

    def test_get_unsecured_requirements(self, temp_products_dir, sample_project):
        """Test getting unsecured requirements"""
        trace = TraceabilityMatrix(sample_project, str(temp_products_dir))

        trace.add_trace("FR-1", "Auth")
        trace.add_trace("FR-2", "Dashboard")

        trace.link_security_issue("FR-1", "SEC-001")
        trace.save()

        unsecured = trace.get_unsecured_requirements()

        assert len(unsecured) == 1
        assert unsecured[0].requirement_id == "FR-1"

    def test_update_quality_metric(self, temp_products_dir, sample_project):
        """Test updating quality metrics"""
        trace = TraceabilityMatrix(sample_project, str(temp_products_dir))

        trace.update_quality_metric(
            "F-001",
            test_pass_rate=0.95,
            test_count=20,
            defect_count=2,
            code_review_status="approved"
        )
        trace.save()

        metrics = trace.get_quality_metrics("F-001")

        assert metrics is not None
        assert metrics.test_pass_rate == 0.95
        assert metrics.defect_count == 2

    def test_get_quality_summary(self, temp_products_dir, sample_project):
        """Test getting quality summary"""
        trace = TraceabilityMatrix(sample_project, str(temp_products_dir))

        trace.update_quality_metric("F-001", test_pass_rate=1.0, code_review_status="approved")
        trace.update_quality_metric("F-002", test_pass_rate=0.8, code_review_status="pending")
        trace.save()

        summary = trace.get_quality_summary()

        assert summary["total_features"] == 2
        assert summary["avg_pass_rate"] == 0.9
        assert summary["reviewed_count"] == 1

    def test_impact_analysis(self, temp_products_dir, sample_project):
        """Test impact analysis"""
        trace = TraceabilityMatrix(sample_project, str(temp_products_dir))

        trace.add_trace("FR-1", "Auth")
        trace.link_feature("FR-1", "F-001")
        trace.link_implementation("FR-1", "src/auth.py")
        trace.link_test("FR-1", "test_auth", "tests/test_auth.py", "passing")
        trace.save()

        analysis = trace.impact_analysis("FR-1")

        assert analysis.requirement_id == "FR-1"
        assert "F-001" in analysis.affected_features
        assert "src/auth.py" in analysis.affected_files
        assert "test_auth" in analysis.affected_tests

    def test_record_change(self, temp_products_dir, sample_project):
        """Test recording change"""
        trace = TraceabilityMatrix(sample_project, str(temp_products_dir))

        trace.add_trace("FR-1", "Auth")

        trace.record_change(
            agent="implement",
            requirement_id="FR-1",
            change_type="implementation_complete",
            details="F-001 implemented",
            files_added=["src/auth.py"]
        )
        trace.save()

        log = trace.get_change_log()

        assert len(log) == 1
        assert log[0].agent == "implement"

    def test_generate_markdown(self, temp_products_dir, sample_project):
        """Test markdown generation"""
        trace = TraceabilityMatrix(sample_project, str(temp_products_dir))

        trace.add_trace("FR-1", "Auth")
        trace.link_feature("FR-1", "F-001")
        trace.link_implementation("FR-1", "src/auth.py")
        trace.link_test("FR-1", "test_auth", "tests/test_auth.py", "passing")

        md = trace.generate_markdown()

        assert "FR-1" in md
        assert "F-001" in md
        assert "auth.py" in md  # Markdown shows filename only
        assert "AUTO-GENERATED" in md


class TestTraceEntry:
    """Test suite for TraceEntry dataclass"""

    def test_trace_entry_creation(self):
        """Test TraceEntry creation"""
        entry = TraceEntry(
            requirement_id="FR-1",
            requirement_title="Authentication"
        )

        assert entry.requirement_id == "FR-1"
        assert entry.requirement_title == "Authentication"

    def test_trace_entry_serialization(self):
        """Test TraceEntry serialization"""
        entry = TraceEntry(
            requirement_id="FR-1",
            requirement_title="Authentication",
            features=["F-001"],
            implementations=[TraceImplementation(file="src/auth.py")],
            tests=[TraceTest(name="test_auth", file="tests/test.py", status="passing")]
        )

        data = entry.to_dict()
        assert data["requirement_id"] == "FR-1"
        assert len(data["features"]) == 1
        assert len(data["implementations"]) == 1
        assert len(data["tests"]) == 1

        restored = TraceEntry.from_dict(data)
        assert restored.requirement_id == entry.requirement_id
        assert len(restored.features) == len(entry.features)


class TestQualityMetric:
    """Test suite for QualityMetric dataclass"""

    def test_quality_metric_creation(self):
        """Test QualityMetric creation"""
        metric = QualityMetric(
            feature_id="F-001",
            test_pass_rate=0.95,
            test_count=20,
            defect_count=2
        )

        assert metric.feature_id == "F-001"
        assert metric.test_pass_rate == 0.95

    def test_quality_metric_serialization(self):
        """Test QualityMetric serialization"""
        metric = QualityMetric(
            feature_id="F-001",
            test_pass_rate=0.95,
            code_review_status="approved"
        )

        data = metric.to_dict()
        assert data["feature_id"] == "F-001"

        restored = QualityMetric.from_dict(data)
        assert restored.feature_id == metric.feature_id
        assert restored.test_pass_rate == metric.test_pass_rate


class TestImpactAnalysis:
    """Test suite for ImpactAnalysis dataclass"""

    def test_impact_analysis_creation(self):
        """Test ImpactAnalysis creation"""
        analysis = ImpactAnalysis(
            requirement_id="FR-1",
            affected_features=["F-001"],
            affected_files=["src/auth.py"],
            risk_level="high"
        )

        assert analysis.requirement_id == "FR-1"
        assert analysis.risk_level == "high"

    def test_impact_analysis_serialization(self):
        """Test ImpactAnalysis serialization"""
        analysis = ImpactAnalysis(
            requirement_id="FR-1",
            affected_features=["F-001"],
            affected_files=["src/auth.py"],
            affected_tests=["test_auth"],
            risk_level="medium"
        )

        data = analysis.to_dict()
        assert data["requirement_id"] == "FR-1"

        restored = ImpactAnalysis.from_dict(data)
        assert restored.requirement_id == analysis.requirement_id
        assert restored.risk_level == analysis.risk_level
