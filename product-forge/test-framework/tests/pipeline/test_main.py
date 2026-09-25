"""Tests for Product Forge main entry point"""
import sys
import tempfile
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


class TestProductForgeMain:
    def test_import_main(self):
        from core.main import main
        assert callable(main)

    def test_list_products(self, capsys):
        from core.main import list_products
        list_products()
        captured = capsys.readouterr()
        assert "Product Forge" in captured.out

    def test_run_pipeline(self, capsys):
        from core.main import run_pipeline
        run_pipeline("test_product", simple=True)
        captured = capsys.readouterr()
        assert "Product Forge" in captured.out
        assert "Simple" in captured.out

    def test_run_pipeline_advanced(self, capsys):
        from core.main import run_pipeline
        run_pipeline("test_product", simple=False)
        captured = capsys.readouterr()
        assert "Advanced" in captured.out

    def test_generate_docs(self, capsys):
        from core.main import generate_docs
        generate_docs()
        captured = capsys.readouterr()
        assert "Product Forge" in captured.out or "Documentation" in captured.out
