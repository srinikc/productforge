# DEPRECATED (2026-09-12): superseded by PipelineExecutor + core/orchestrator/*.
# Kept for reference; not part of the generic pipeline. See docs/UNWIRED-MODULES-TRIAGE.md.
#!/usr/bin/env python
"""
Product Forge - Main Entry Point
Multi-Agent Multi-Project System
"""
import sys
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Product Forge - Multi-Agent Multi-Project System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  productforge list                    # List all products
  productforge run <product>            # Run pipeline for a product
  productforge docs                    # Generate workflow documentation
  productforge dashboard               # Start the dashboard server
  productforge test                    # Run test suite
        """
    )

    parser.add_argument(
        "command",
        nargs="?",
        default="help",
        choices=["list", "run", "docs", "dashboard", "test", "help"]
    )
    parser.add_argument("product", nargs="?")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--simple", action="store_true", help="Use simple mode")

    args = parser.parse_args()

    if args.command == "help":
        parser.print_help()
        return 0

    if args.command == "list":
        list_products()
        return 0

    if args.command == "run":
        if not args.product:
            print("Error: Product name required")
            return 1
        run_pipeline(args.product, simple=args.simple)
        return 0

    if args.command == "docs":
        generate_docs()
        return 0

    if args.command == "dashboard":
        start_dashboard()
        return 0

    if args.command == "test":
        run_tests()
        return 0

    return 0


def list_products():
    """List all products"""
    print("Product Forge - Products")
    print("=" * 40)
    products_dir = Path("products")
    if products_dir.exists():
        for p in sorted(products_dir.iterdir()):
            if p.is_dir():
                print(f"  - {p.name}")
    else:
        print("  No products found")


def run_pipeline(product_name, simple=False):
    """Run the pipeline for a product"""
    print(f"Product Forge - Running pipeline for: {product_name}")
    if simple:
        print("Mode: Simple")
    else:
        print("Mode: Advanced")

    # Import and run the pipeline orchestrator
    try:
        from core.global_orchestrator import GlobalOrchestrator
        orch = GlobalOrchestrator(product_name)
        orch.run()
    except ImportError:
        print("Pipeline module not available. Use: python scripts/pipeline.py")
    except Exception as e:
        print(f"Error: {e}")


def generate_docs():
    """Generate workflow documentation"""
    print("Product Forge - Generating Documentation")
    try:
        from core.workflow_docs import WorkflowDocumentationGenerator
        from core.pdf_generator import PDFGenerator

        docs_dir = Path("dashboard/docs")
        docs_dir.mkdir(parents=True, exist_ok=True)

        gen = WorkflowDocumentationGenerator()
        gen.docs_dir = docs_dir
        files = gen.save_all_documentation()

        pdf_gen = PDFGenerator()
        for f in files:
            if f.endswith(".html"):
                html_content = Path(f).read_text(encoding="utf-8")
                pdf_path = Path(f).with_suffix(".pdf")
                pdf_gen.html_to_pdf(html_content, pdf_path)

        print(f"Generated {len(files)} documentation files")
    except Exception as e:
        print(f"Error generating docs: {e}")


def start_dashboard():
    """Start the dashboard API server (new dashboard)."""
    print("Product Forge - Starting Dashboard API")
    try:
        import uvicorn
        from dashboard.api.app import app
        uvicorn.run(app, host="0.0.0.0", port=int(__import__("os").getenv("DASHBOARD_API_PORT", "3001")))
    except ImportError:
        print("Dashboard API not available (install fastapi/uvicorn)")
    except Exception as e:
        print(f"Error: {e}")


def run_tests():
    """Run the test suite"""
    import subprocess
    print("Product Forge - Running Tests")
    result = subprocess.run(
        ["python", "-m", "pytest", "test-framework/tests/", "-v"],
        capture_output=False
    )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
