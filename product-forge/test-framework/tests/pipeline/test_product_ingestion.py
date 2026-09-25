"""Tests for Product Ingestion"""
import sys
import tempfile
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest


@pytest.fixture
def temp_dirs():
    with tempfile.TemporaryDirectory() as products_dir:
        with tempfile.TemporaryDirectory() as source_dir:
            yield products_dir, source_dir


@pytest.fixture
def sample_source_folder(temp_dirs):
    products_dir, source_dir = temp_dirs
    source_path = Path(source_dir)

    # Create some sample files
    (source_path / "src").mkdir()
    (source_path / "src" / "main.py").write_text("print('hello')")
    (source_path / "src" / "utils.py").write_text("# utilities")
    (source_path / "tests").mkdir()
    (source_path / "tests" / "test_main.py").write_text("# tests")
    (source_path / "README.md").write_text("# Sample Project")
    (source_path / "requirements.txt").write_text("pytest\n")

    return temp_dirs


class TestProductIngester:
    def test_create_ingester(self, temp_dirs):
        from core.product_ingestion import ProductIngester
        products_dir, _ = temp_dirs
        ingester = ProductIngester(products_dir)
        assert ingester is not None
        assert ingester.products_dir == Path(products_dir)

    def test_ingest_from_folder_success(self, sample_source_folder):
        from core.product_ingestion import ProductIngester
        products_dir, source_dir = sample_source_folder
        ingester = ProductIngester(products_dir)
        result = ingester.ingest_from_folder("imported-product", source_dir)
        assert result.success is True
        assert result.files_imported > 0

    def test_ingest_from_folder_not_found(self, temp_dirs):
        from core.product_ingestion import ProductIngester
        products_dir, _ = temp_dirs
        ingester = ProductIngester(products_dir)
        result = ingester.ingest_from_folder("test", "/nonexistent/path")
        assert result.success is False
        assert len(result.errors) > 0

    def test_ingest_creates_product_plan(self, sample_source_folder):
        from core.product_ingestion import ProductIngester
        products_dir, source_dir = sample_source_folder
        ingester = ProductIngester(products_dir)
        result = ingester.ingest_from_folder("imported-product", source_dir)
        assert result.product_plan_path is not None
        assert Path(result.product_plan_path).exists()

    def test_ingest_creates_traceability(self, sample_source_folder):
        from core.product_ingestion import ProductIngester
        products_dir, source_dir = sample_source_folder
        ingester = ProductIngester(products_dir)
        result = ingester.ingest_from_folder("imported-product", source_dir)
        assert result.traceability_path is not None
        assert Path(result.traceability_path).exists()

    def test_ingest_creates_agent_ledger(self, sample_source_folder):
        from core.product_ingestion import ProductIngester
        products_dir, source_dir = sample_source_folder
        ingester = ProductIngester(products_dir)
        result = ingester.ingest_from_folder("imported-product", source_dir)
        assert result.agent_ledger_path is not None
        assert Path(result.agent_ledger_path).exists()

    def test_ingest_detects_tech_stack(self, sample_source_folder):
        from core.product_ingestion import ProductIngester
        products_dir, source_dir = sample_source_folder
        ingester = ProductIngester(products_dir)
        result = ingester.ingest_from_folder("imported-product", source_dir)
        assert result.modules_detected > 0

    def test_ingest_detects_modules(self, sample_source_folder):
        from core.product_ingestion import ProductIngester
        products_dir, source_dir = sample_source_folder
        ingester = ProductIngester(products_dir)
        result = ingester.ingest_from_folder("imported-product", source_dir)
        assert result.modules_detected >= 1

    def test_ingest_detects_features(self, sample_source_folder):
        from core.product_ingestion import ProductIngester
        products_dir, source_dir = sample_source_folder
        ingester = ProductIngester(products_dir)
        result = ingester.ingest_from_folder("imported-product", source_dir)
        assert result.features_detected >= 1

    def test_generate_ingestion_report(self, sample_source_folder):
        from core.product_ingestion import ProductIngester
        products_dir, source_dir = sample_source_folder
        ingester = ProductIngester(products_dir)
        result = ingester.ingest_from_folder("imported-product", source_dir)
        report = ingester.generate_ingestion_report(result)
        assert "Ingestion" in report
        assert "imported-product" in report
        assert "Files Imported" in report

    def test_ingestion_source_dataclass(self):
        from core.product_ingestion import IngestionSource
        source = IngestionSource(
            type="git",
            location="https://github.com/user/repo",
            branch="main"
        )
        assert source.type == "git"
        assert source.branch == "main"

    def test_ingestion_result_dataclass(self):
        from core.product_ingestion import IngestionResult
        result = IngestionResult(product_name="test", success=True)
        assert result.product_name == "test"
        assert result.success is True
        assert result.files_imported == 0
