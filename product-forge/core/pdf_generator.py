"""
PDF Generation
Generates PDF files from HTML using available tools
"""
from pathlib import Path
from typing import Optional


class PDFGenerator:
    """Generate PDF files from HTML"""

    def __init__(self):
        self.backend = self._detect_backend()

    def _detect_backend(self) -> str:
        """Detect a WORKING PDF backend (probe usability, not just import).

        BI-0085: WeasyPrint raises OSError when its native lib (libgobject-2.0-0) is
        missing, and Playwright raises when its browsers aren't installed. Both are
        probed here; reportlab (pure Python, no native libs) is the reliable fallback.
        """
        # WeasyPrint: import AND instantiate (its native-lib failure surfaces at use).
        try:
            import contextlib, io
            from weasyprint import HTML  # noqa
            with contextlib.redirect_stderr(io.StringIO()):
                HTML(string="<p>ok</p>").render()
            return "weasyprint"
        except Exception:
            pass

        # pdfkit needs the wkhtmltopdf binary on PATH.
        try:
            import shutil
            from pdfkit import from_string  # noqa
            if shutil.which("wkhtmltopdf"):
                return "pdfkit"
        except Exception:
            pass

        # playwright needs its browsers installed.
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                b = p.chromium.launch()
                b.close()
            return "playwright"
        except Exception:
            pass

        # reportlab: pure Python, always usable when installed.
        try:
            import reportlab  # noqa
            return "reportlab"
        except Exception:
            pass

        return "none"

    def html_to_pdf(self, html_content: str, output_path: Path) -> bool:
        """Convert HTML to PDF"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if self.backend == "weasyprint":
            return self._weasyprint_convert(html_content, output_path)
        elif self.backend == "playwright":
            return self._playwright_convert(html_content, output_path)
        elif self.backend == "pdfkit":
            return self._pdfkit_convert(html_content, output_path)
        elif self.backend == "reportlab":
            return self._reportlab_convert(html_content, output_path)
        else:
            # Fallback: Create a simple text-based PDF placeholder
            return self._create_simple_pdf(html_content, output_path)

    def _reportlab_convert(self, html_content: str, output_path: Path) -> bool:
        """BI-0085: pure-Python HTML->PDF via reportlab (no native libs required)."""
        try:
            import re as _re
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.pdfgen import canvas

            # very light HTML -> text: strip script/style, convert block tags to newlines
            t = _re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html_content or "")
            t = _re.sub(r"(?i)<br\s*/?>", "\n", t)
            t = _re.sub(r"(?i)</(p|div|h[1-6]|li|tr)>", "\n", t)
            t = _re.sub(r"<[^>]+>", "", t)
            t = (t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                   .replace("&nbsp;", " ").replace("&#xa;", "\n"))
            t = _re.sub(r"[ \t]+", " ", t)

            c = canvas.Canvas(str(output_path), pagesize=A4)
            width, height = A4
            x, y = 18 * mm, height - 18 * mm
            c.setFont("Helvetica", 9)
            for raw in t.splitlines():
                line = raw.strip()
                for chunk in ([line[i:i + 110] for i in range(0, len(line), 110)] or [""]):
                    if y < 18 * mm:
                        c.showPage(); c.setFont("Helvetica", 9); y = height - 18 * mm
                    c.drawString(x, y, chunk)
                    y -= 12
            c.save()
            return output_path.exists() and output_path.stat().st_size > 0
        except Exception:
            return False

    def _weasyprint_convert(self, html_content: str, output_path: Path) -> bool:
        """Convert using WeasyPrint"""
        try:
            from weasyprint import HTML
            HTML(string=html_content).write_pdf(str(output_path))
            return True
        except Exception:
            return False

    def _playwright_convert(self, html_content: str, output_path: Path) -> bool:
        """Convert using Playwright"""
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.set_content(html_content)
                page.pdf(path=str(output_path))
                browser.close()
            return True
        except Exception:
            return False

    def _pdfkit_convert(self, html_content: str, output_path: Path) -> bool:
        """Convert using pdfkit"""
        try:
            import pdfkit
            pdfkit.from_string(html_content, str(output_path))
            return True
        except Exception:
            return False

    def _create_simple_pdf(self, html_content: str, output_path: Path) -> bool:
        """Create a simple text-based PDF (fallback)"""
        try:
            # Extract text from HTML (very simple)
            import re
            text = re.sub(r'<[^>]+>', ' ', html_content)
            text = re.sub(r'\s+', ' ', text).strip()

            # Create minimal PDF
            pdf_content = self._build_minimal_pdf(text)
            with open(output_path, 'wb') as f:
                f.write(pdf_content)
            return True
        except Exception:
            return False

    def _build_minimal_pdf(self, text: str) -> bytes:
        """Build a minimal valid PDF file"""
        # Truncate text for safety
        text = text[:5000]

        # Escape for PDF
        text_escaped = text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')

        pdf = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj

2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj

3 0 obj
<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 612 792] /Contents 5 0 R >>
endobj

4 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj

5 0 obj
<< /Length {len(text_escaped) + 100} >>
stream
BT
/F1 10 Tf
50 750 Td
15 TL
{text_escaped}
ET
endstream
endobj

xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000226 00000 n
0000000297 00000 n

trailer
<< /Size 6 /Root 1 0 R >>
startxref
{500 + len(text_escaped)}
%%EOF
"""
        return pdf.encode('latin-1', errors='ignore')
