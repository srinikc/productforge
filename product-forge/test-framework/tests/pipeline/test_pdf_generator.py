"""Tests for PDF Generator"""
import sys
import tempfile
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest


class TestPDFGenerator:
    def test_create_generator(self):
        from core.pdf_generator import PDFGenerator
        gen = PDFGenerator()
        assert gen is not None
        # BI-0085: reportlab is a supported (pure-Python) backend used when the
        # native-lib backends (weasyprint/playwright/pdfkit) are unavailable.
        assert gen.backend in ["weasyprint", "playwright", "pdfkit", "reportlab", "none"]

    def test_html_to_pdf_fallback(self):
        """Test that PDF generation works with fallback"""
        from core.pdf_generator import PDFGenerator
        gen = PDFGenerator()
        html = "<html><body><h1>Test</h1><p>Hello World</p></body></html>"
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "test.pdf"
            result = gen.html_to_pdf(html, output)
            assert result is True
            assert output.exists()
            assert output.stat().st_size > 0

    def test_html_to_pdf_creates_directory(self):
        from core.pdf_generator import PDFGenerator
        gen = PDFGenerator()
        html = "<html><body>Test</body></html>"
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "subdir" / "test.pdf"
            result = gen.html_to_pdf(html, output)
            assert result is True
            assert output.exists()

    def test_minimal_pdf_format(self):
        """Test that the fallback creates valid PDF format"""
        from core.pdf_generator import PDFGenerator
        gen = PDFGenerator()
        content = gen._build_minimal_pdf("Test content")
        assert b"%PDF-1.4" in content
        assert b"%%EOF" in content

    def test_pdf_with_complex_html(self):
        from core.pdf_generator import PDFGenerator
        gen = PDFGenerator()
        html = """
        <html>
            <head><title>Product Forge Test</title></head>
            <body>
                <h1>Product Forge</h1>
                <h2>Multi-Agent Multi-Project System</h2>
                <p>This is a test of PDF generation.</p>
                <ul>
                    <li>Item 1</li>
                    <li>Item 2</li>
                    <li>Item 3</li>
                </ul>
            </body>
        </html>
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "test.pdf"
            result = gen.html_to_pdf(html, output)
            assert result is True
            assert output.exists()
