#!/usr/bin/env python
"""
Product Forge - Self-Contained Installer
One-command installation for any system
"""
import sys
import subprocess
import os
import platform
import urllib.request
from pathlib import Path


def run_cmd(cmd, check=True):
    """Run command and return result"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
        return result
    except Exception as e:
        print(f"Error running: {cmd}")
        print(f"  {e}")
        return None


def main():
    print("=" * 60)
    print("Product Forge - Self-Contained Installer")
    print("=" * 60)
    print()

    # Check Python version
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print(f"ERROR: Python 3.10+ required. Current: {version.major}.{version.minor}")
        sys.exit(1)
    print(f"Python {version.major}.{version.minor}.{version.micro} - OK")

    # Install core dependencies
    print("\n1. Installing core dependencies...")
    run_cmd(f"{sys.executable} -m pip install fastapi>=0.104.0 uvicorn>=0.24.0 pydantic>=2.0.0")

    # Install optional PDF dependencies
    print("\n2. Installing PDF generation dependencies...")
    run_cmd(f"{sys.executable} -m pip install weasyprint playwright", check=False)

    # Install the package from local wheel/sdist
    print("\n3. Installing Product Forge package...")
    
    # Find the package file
    dist_dir = Path(__file__).parent / "dist"
    if not dist_dir.exists():
        # Try to find from current directory
        dist_dir = Path("dist")
    
    wheel_files = list(dist_dir.glob("*.whl"))
    if not wheel_files:
        # Try to find sdist
        wheel_files = list(dist_dir.glob("*.tar.gz"))
    
    if not wheel_files:
        print("ERROR: No package files found in dist/")
        print("Please run: python setup.py sdist bdist_wheel")
        sys.exit(1)
    
    pkg_file = wheel_files[0]
    print(f"  Installing: {pkg_file.name}")
    run_cmd(f"{sys.executable} -m pip install {pkg_file}")

    # Verify installation
    print("\n4. Verifying installation...")
    result = run_cmd(f"{sys.executable} -c \"import core.main; print('Core OK')\"")
    if result and result.returncode == 0:
        print("  Core modules: OK")
    else:
        print("  Core modules: FAILED")
        sys.exit(1)

    # Check CLI
    print("\n5. Checking CLI command...")
    if platform.system() == "Windows":
        scripts_dir = Path(sys.prefix) / "Scripts"
    else:
        scripts_dir = Path(sys.prefix) / "bin"
    
    cli_path = scripts_dir / ("productforge.exe" if platform.system() == "Windows" else "productforge")
    if cli_path.exists():
        print(f"  CLI installed: {cli_path}")
    else:
        print(f"  CLI at: {cli_path} (may need PATH update)")

    print("\n" + "=" * 60)
    print("INSTALLATION COMPLETE!")
    print("=" * 60)
    print()
    print("NEXT STEPS:")
    print("  1. Start dashboard:")
    if platform.system() == "Windows":
        print("     productforge dashboard")
    else:
        print("     productforge dashboard")
    print()
    print("  2. Open browser: http://localhost:3001")
    print()
    print("  3. Run pipeline:")
    print("     productforge run myworld")
    print()
    print("  4. Generate documentation:")
    print("     productforge docs")
    print()
    print("  5. Run tests:")
    print("     productforge test")
    print()
    print("DOCUMENTATION: README.md")
    print("HELP: productforge help")
    print()


if __name__ == "__main__":
    main()