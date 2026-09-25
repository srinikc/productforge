"""Tests for Product Analyzer"""
import sys
import tempfile
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest


@pytest.fixture
def sample_project_dir():
    """Create a sample project directory for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        project = Path(tmpdir) / "test-product"
        project.mkdir()

        # Create structure
        (project / "src").mkdir()
        (project / "src" / "main.py").write_text('"""Main module"""\nimport os\n\ndef hello():\n    """Say hello"""\n    try:\n        return "hello"\n    except Exception as e:\n        print(e)\n        return None\n')
        (project / "src" / "utils.py").write_text('"""Utilities"""\n\ndef add(a, b):\n    return a + b\n')

        (project / "tests").mkdir()
        (project / "tests" / "test_main.py").write_text('import sys\nsys.path.insert(0, "../src")\nfrom main import hello\n\ndef test_hello():\n    assert hello() == "hello"\n')
        (project / "tests" / "conftest.py").write_text('# pytest configuration\n')

        (project / "README.md").write_text("# Test Product\nThis is a test.")
        (project / "requirements.txt").write_text("pytest\nrequests\n")
        (project / ".gitignore").write_text("__pycache__/\n*.pyc\n.env\n")

        yield str(project)


@pytest.fixture
def empty_project_dir():
    """Create an empty project directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        project = Path(tmpdir) / "empty-product"
        project.mkdir()
        yield str(project)


class TestProductAnalyzer:
    def test_create_analyzer(self):
        from core.product_analyzer import ProductAnalyzer
        analyzer = ProductAnalyzer()
        assert analyzer is not None

    def test_analyze_product_structure(self, sample_project_dir):
        from core.product_analyzer import ProductAnalyzer
        analyzer = ProductAnalyzer()
        report = analyzer.analyze_product("test-product", sample_project_dir)
        assert report.structure.total_files > 0
        assert report.structure.code_files > 0
        assert report.structure.test_files > 0
        assert "Python" in report.structure.tech_stack

    def test_analyze_detects_frameworks(self, sample_project_dir):
        from core.product_analyzer import ProductAnalyzer
        analyzer = ProductAnalyzer()
        report = analyzer.analyze_product("test-product", sample_project_dir)
        assert "pytest" in report.structure.detected_frameworks

    def test_analyze_detects_entry_points(self, sample_project_dir):
        from core.product_analyzer import ProductAnalyzer
        analyzer = ProductAnalyzer()
        report = analyzer.analyze_product("test-product", sample_project_dir)
        assert len(report.structure.main_entry_points) > 0

    def test_analyze_code_quality(self, sample_project_dir):
        from core.product_analyzer import ProductAnalyzer
        analyzer = ProductAnalyzer()
        report = analyzer.analyze_product("test-product", sample_project_dir)
        assert report.code_quality.overall_quality_score >= 0
        assert report.code_quality.overall_quality_score <= 1

    def test_analyze_test_coverage(self, sample_project_dir):
        from core.product_analyzer import ProductAnalyzer
        analyzer = ProductAnalyzer()
        report = analyzer.analyze_product("test-product", sample_project_dir)
        assert report.test_coverage.has_tests is True
        assert "pytest" in report.test_coverage.test_frameworks
        assert "unit" in report.test_coverage.test_types

    def test_analyze_security(self, sample_project_dir):
        from core.product_analyzer import ProductAnalyzer
        analyzer = ProductAnalyzer()
        report = analyzer.analyze_product("test-product", sample_project_dir)
        # Should not have critical security issues in our clean sample
        critical = [f for f in report.security_findings if f.severity == "critical"]
        assert len(critical) == 0

    def test_analyze_detects_security_issues(self):
        """Test that security issues are detected"""
        from core.product_analyzer import ProductAnalyzer
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "insecure-product"
            project.mkdir()
            (project / "config.py").write_text('password = "secret123"\napi_key = "abc123"\n')
            (project / ".gitignore").write_text("__pycache__/\n")

            analyzer = ProductAnalyzer()
            report = analyzer.analyze_product("insecure", str(project))
            assert len(report.security_findings) > 0
            assert any(f.severity == "high" for f in report.security_findings)

    def test_analyze_gap_analysis(self, sample_project_dir):
        from core.product_analyzer import ProductAnalyzer
        analyzer = ProductAnalyzer()
        report = analyzer.analyze_product("test-product", sample_project_dir)
        assert report.gap_analysis.best_practice_score >= 0
        assert report.gap_analysis.pipeline_readiness >= 0

    def test_analyze_detects_missing_docker(self, sample_project_dir):
        from core.product_analyzer import ProductAnalyzer
        analyzer = ProductAnalyzer()
        report = analyzer.analyze_product("test-product", sample_project_dir)
        assert any("Docker" in item for item in report.gap_analysis.missing_artifacts)

    def test_analyze_agent_work_plan(self, sample_project_dir):
        from core.product_analyzer import ProductAnalyzer
        analyzer = ProductAnalyzer()
        report = analyzer.analyze_product("test-product", sample_project_dir)
        assert len(report.agent_work_plan) > 0
        # Should include code-review agent
        assert any(w.agent == "code-review" for w in report.agent_work_plan)
        # Should include document agent
        assert any(w.agent == "document" for w in report.agent_work_plan)

    def test_analyze_recommendations(self, sample_project_dir):
        from core.product_analyzer import ProductAnalyzer
        analyzer = ProductAnalyzer()
        report = analyzer.analyze_product("test-product", sample_project_dir)
        assert len(report.recommendations) > 0
        # Should recommend CI/CD
        assert any("CI/CD" in r.title for r in report.recommendations)

    def test_analyze_user_questions(self, sample_project_dir):
        from core.product_analyzer import ProductAnalyzer
        analyzer = ProductAnalyzer()
        report = analyzer.analyze_product("test-product", sample_project_dir)
        assert len(report.user_questions) > 0
        # Should have product type question
        assert any("product type" in q.question.lower() for q in report.user_questions)

    def test_analyze_calculates_score(self, sample_project_dir):
        from core.product_analyzer import ProductAnalyzer
        analyzer = ProductAnalyzer()
        report = analyzer.analyze_product("test-product", sample_project_dir)
        assert report.overall_score >= 0
        assert report.overall_score <= 100

    def test_analyze_empty_project(self, empty_project_dir):
        from core.product_analyzer import ProductAnalyzer
        analyzer = ProductAnalyzer()
        report = analyzer.analyze_product("empty", empty_project_dir)
        assert report.structure.total_files == 0
        assert report.test_coverage.has_tests is False
        assert len(report.recommendations) > 0

    def test_analyze_source_not_found(self):
        from core.product_analyzer import ProductAnalyzer
        analyzer = ProductAnalyzer()
        with pytest.raises(FileNotFoundError):
            analyzer.analyze_product("nonexistent", "/nonexistent/path")

    def test_save_analysis(self, sample_project_dir):
        from core.product_analyzer import ProductAnalyzer
        analyzer = ProductAnalyzer()
        report = analyzer.analyze_product("test-product", sample_project_dir)
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "analysis"
            json_path, md_path = analyzer.save_analysis(report, output_dir)
            assert json_path.exists()
            assert md_path.exists()
            assert json_path.stat().st_size > 0
            assert md_path.stat().st_size > 0

    def test_analysis_report_dataclass(self):
        from core.product_analyzer import AnalysisReport, StructureAnalysis, CodeQualityMetrics, TestCoverageAnalysis, GapAnalysis
        report = AnalysisReport(
            product_name="test",
            timestamp="2026-01-01",
            structure=StructureAnalysis(),
            code_quality=CodeQualityMetrics(),
            test_coverage=TestCoverageAnalysis(),
            security_findings=[],
            gap_analysis=GapAnalysis(),
            agent_work_plan=[],
            recommendations=[],
            user_questions=[]
        )
        assert report.product_name == "test"
        assert report.overall_score == 0.0

    def test_recommendation_dataclass(self):
        from core.product_analyzer import Recommendation
        rec = Recommendation(
            title="Test",
            description="Test desc",
            priority="high",
            effort="2 hours",
            impact="high",
            category="quality",
            agent_responsible="test-agent"
        )
        assert rec.title == "Test"
        assert rec.priority == "high"

    def test_user_question_dataclass(self):
        from core.product_analyzer import UserQuestion
        q = UserQuestion(
            question="What?",
            context="Context",
            options=["A", "B"],
            default="A"
        )
        assert q.question == "What?"
        assert len(q.options) == 2
