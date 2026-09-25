#!/usr/bin/env python
"""
Product Forge - Multi-Agent Multi-Project System

Installation and setup script for Product Forge.
"""
import sys
import subprocess
import platform
from pathlib import Path


def check_python_version():
    """Check if Python version is compatible"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print(f"ERROR: Python 3.10+ required. Current version: {version.major}.{version.minor}")
        return False
    print(f"Python version: {version.major}.{version.minor}.{version.micro} - OK")
    return True


def install_dependencies():
    """Install required dependencies"""
    print("\nInstalling dependencies...")
    dependencies = [
        "fastapi>=0.104.0",
        "uvicorn>=0.24.0",
        "pydantic>=2.0.0",
    ]

    for dep in dependencies:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep])
            print(f"  Installed: {dep}")
        except subprocess.CalledProcessError as e:
            print(f"  Failed to install {dep}: {e}")
            return False

    return True


def install_optional_dependencies():
    """Install optional dependencies for PDF generation"""
    print("\nInstalling optional dependencies (PDF generation)...")
    optional_deps = [
        "weasyprint",
        "playwright",
    ]

    for dep in optional_deps:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep])
            print(f"  Installed: {dep}")
        except subprocess.CalledProcessError as e:
            print(f"  Warning: Failed to install {dep}: {e}")

    return True


def run_pip_install():
    """Run pip install"""
    print("\nRunning pip install...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", "."])
        print("  Package installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  Failed to install package: {e}")
        return False


def verify_installation():
    """Verify the installation"""
    print("\nVerifying installation...")

    # Check core modules
    core_modules = [
        "core.workflow_docs",
        "core.pdf_generator",
        "core.main",
    ]

    all_ok = True
    for module in core_modules:
        try:
            __import__(module)
            print(f"  OK: {module}")
        except ImportError as e:
            print(f"  FAIL: {module} - {e}")
            all_ok = False

    # Check dashboard
    dashboard_path = Path("pipeline_dashboard/index.html")
    if dashboard_path.exists():
        print(f"  OK: Dashboard (index.html)")
    else:
        print(f"  FAIL: Dashboard not found")
        all_ok = False

    # Check docs directory
    docs_dir = Path("pipeline_dashboard/docs")
    if docs_dir.exists():
        pdf_count = len(list(docs_dir.glob("*.pdf")))
        html_count = len(list(docs_dir.glob("*.html")))
        drawio_count = len(list(docs_dir.glob("*.drawio")))
        print(f"  OK: Generated docs ({pdf_count} PDFs, {html_count} HTML, {drawio_count} Draw.io)")
    else:
        print(f"  WARNING: Docs directory not found (run productforge docs first)")

    return all_ok


def main():
    """Main installation function"""
    print("=" * 60)
    print("Product Forge - Multi-Agent Multi-Project System")
    print("=" * 60)

    # Check Python version
    if not check_python_version():
        sys.exit(1)

    # Install dependencies
    if not install_dependencies():
        print("\nERROR: Failed to install dependencies")
        sys.exit(1)

    # Install optional dependencies
    install_optional_dependencies()

    # Install package
    if not run_pip_install():
        print("\nERROR: Failed to install package")
        sys.exit(1)

    # Verify installation
    if not verify_installation():
        print("\nWARNING: Some components may not be properly installed")

    print("\n" + "=" * 60)
    print("Installation Complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Start dashboard: productforge dashboard")
    print("  2. Open browser: http://localhost:3001")
    print("  3. Run pipeline: productforge run myworld")
    print("  4. Generate docs: productforge docs")
    print("  5. Run tests: productforge test")
    print("\nFor more help: productforge help")
    print("Documentation: README.md")


if __name__ == "__main__":
    main()
