#!/usr/bin/env python3
"""
PDF Generation Helper for Pipeline Architecture
Generates PDF from draw.io file or HTML architecture overview
"""
import os
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent
DRAWIO_FILE = ROOT / "products" / "myworld" / "architecture" / "pipeline-architecture.drawio"
HTML_FILE = ROOT / "products" / "myworld" / "architecture" / "architecture-overview.html"
PDF_FILE = ROOT / "products" / "myworld" / "architecture" / "pipeline-architecture.pdf"


def print_status(msg, status="info"):
    prefix = {"info": "ℹ ", "success": "✓", "error": "✗", "warn": "⚠"}
    colors = {"info": "\033[94m", "success": "\033[92m", "error": "\033[91m", "warn": "\033[93m"}
    reset = "\033[0m"
    print(f"{colors.get(status, '')}{prefix.get(status, '')} {msg}{reset}")


def find_drawio_cli():
    """Check for draw.io CLI in common locations"""
    paths = [
        r"C:\Program Files\draw.io\draw.io.exe",
        r"C:\Program Files (x86)\draw.io\draw.io.exe",
        r"C:\Users\{}\AppData\Local\draw.io\app-{}\draw.io.exe".format(os.environ.get("USERNAME", ""), ""),
        r"C:\Users\{}\AppData\Local\Programs\draw.io\draw.io.exe".format(os.environ.get("USERNAME", "")),
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None


def try_pip_install(package):
    """Try to install a Python package"""
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", package, "--quiet"],
                      check=True, timeout=60)
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def generate_pdf_from_drawio():
    """Use draw.io CLI to generate PDF"""
    cli = find_drawio_cli()
    if not cli:
        print_status("draw.io CLI not found. Install from https://github.com/jgraph/drawio-desktop/releases", "warn")
        return False
    
    print_status(f"Found draw.io CLI: {cli}", "info")
    print_status("Generating PDF from .drawio file...", "info")
    
    try:
        # draw.io CLI: drawio --export --format pdf input.drawio
        subprocess.run([
            cli, "--export", "--format", "pdf",
            "--output", str(PDF_FILE),
            str(DRAWIO_FILE)
        ], check=True, timeout=60)
        print_status(f"PDF generated: {PDF_FILE}", "success")
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print_status(f"draw.io export failed: {e}", "error")
        return False


def generate_pdf_from_html():
    """Try to generate PDF from HTML using various tools"""
    
    # Try weasyprint
    print_status("Trying weasyprint...", "info")
    try:
        import weasyprint
        weasyprint.HTML(filename=str(HTML_FILE)).write_pdf(str(PDF_FILE))
        print_status(f"PDF generated: {PDF_FILE}", "success")
        return True
    except ImportError:
        print_status("weasyprint not installed", "warn")
    except Exception as e:
        print_status(f"weasyprint failed: {e}", "error")
    
    # Try installing weasyprint
    if try_pip_install("weasyprint"):
        try:
            import weasyprint
            weasyprint.HTML(filename=str(HTML_FILE)).write_pdf(str(PDF_FILE))
            print_status(f"PDF generated: {PDF_FILE}", "success")
            return True
        except Exception as e:
            print_status(f"weasyprint after install failed: {e}", "error")
    
    # Try pdfkit
    print_status("Trying pdfkit...", "info")
    try:
        import pdfkit
        options = {
            'page-size': 'A3',
            'orientation': 'Landscape',
            'margin-top': '0.5in',
            'margin-right': '0.5in',
            'margin-bottom': '0.5in',
            'margin-left': '0.5in',
            'encoding': "UTF-8",
            'enable-local-file-access': None
        }
        pdfkit.from_file(str(HTML_FILE), str(PDF_FILE), options=options)
        print_status(f"PDF generated: {PDF_FILE}", "success")
        return True
    except ImportError:
        print_status("pdfkit not installed (also requires wkhtmltopdf)", "warn")
    except Exception as e:
        print_status(f"pdfkit failed: {e}", "error")
    
    return False


def generate_pdf_via_chrome():
    """Use Chrome/Edge headless to generate PDF from HTML"""
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    
    chrome = None
    for p in chrome_paths:
        if os.path.exists(p):
            chrome = p
            break
    
    if not chrome:
        print_status("Chrome/Edge not found", "warn")
        return False
    
    print_status(f"Found browser: {chrome}", "info")
    print_status("Generating PDF using headless browser...", "info")
    
    try:
        subprocess.run([
            chrome,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            f"--print-to-pdf={PDF_FILE}",
            f"file:///{HTML_FILE.as_posix()}"
        ], check=True, timeout=60)
        print_status(f"PDF generated: {PDF_FILE}", "success")
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print_status(f"Browser PDF generation failed: {e}", "error")
        return False


def print_manual_instructions():
    """Print manual PDF generation instructions"""
    print("\n" + "=" * 70)
    print(" MANUAL PDF GENERATION OPTIONS")
    print("=" * 70)
    print()
    print("Since automated PDF generation tools aren't available, here are")
    print("three ways to generate the PDF:")
    print()
    print("OPTION 1: Using draw.io Desktop App (Recommended)")
    print("  1. Download from: https://github.com/jgraph/drawio-desktop/releases")
    print(f"  2. Open: {DRAWIO_FILE}")
    print("  3. Menu: File → Export As → PDF")
    print(f"  4. Save to: {PDF_FILE}")
    print()
    print("OPTION 2: Using draw.io Web (No Install)")
    print("  1. Go to: https://app.diagrams.net/")
    print("  2. Menu: File → Open from Device")
    print(f"  3. Select: {DRAWIO_FILE}")
    print("  4. Menu: File → Export As → PDF")
    print()
    print("OPTION 3: From HTML (Browser Print)")
    print(f"  1. Open: {HTML_FILE}")
    print("  2. Ctrl+P (or Cmd+P on Mac)")
    print("  3. Set: A3 Landscape, Background graphics ON")
    print("  4. Save as PDF")
    print()
    print("OPTION 4: Install Python PDF Library (Auto)")
    print("  Run: pip install weasyprint")
    print("  Then: python generate_pdf.py")
    print()


def main():
    print("=" * 70)
    print(" PDF GENERATION - Pipeline Architecture")
    print("=" * 70)
    print()
    
    # Check source files exist
    if not DRAWIO_FILE.exists():
        print_status(f"Drawio file not found: {DRAWIO_FILE}", "error")
        sys.exit(1)
    if not HTML_FILE.exists():
        print_status(f"HTML file not found: {HTML_FILE}", "error")
        sys.exit(1)
    
    print_status(f"Source: {DRAWIO_FILE}", "info")
    print_status(f"Output: {PDF_FILE}", "info")
    print()
    
    # Try multiple methods in order
    success = False
    
    # Method 1: draw.io CLI
    success = generate_pdf_from_drawio()
    
    # Method 2: Headless Chrome
    if not success:
        success = generate_pdf_via_chrome()
    
    # Method 3: Python libraries
    if not success:
        success = generate_pdf_from_html()
    
    # Show manual instructions if all fail
    if not success:
        print()
        print_status("Automated PDF generation failed", "warn")
        print_manual_instructions()
        sys.exit(1)
    
    # Verify
    if PDF_FILE.exists():
        size_kb = PDF_FILE.stat().st_size / 1024
        print()
        print_status(f"SUCCESS! PDF size: {size_kb:.1f} KB", "success")
        print_status(f"Location: {PDF_FILE}", "success")
    else:
        print_status("PDF not found after generation", "error")
        sys.exit(1)


if __name__ == "__main__":
    main()
