#!/usr/bin/env python
"""
Product Forge - Self-Contained Installation
Complete multi-agent multi-project system installer

This installer sets up EVERYTHING needed for Product Forge:
- Core Python modules (orchestration, security, tracking)
- Dashboard UI (web interface)
- Pipeline orchestration (/pipeline command)
- 17 agent definitions (for opencode CLI integration)
- Documentation (PDF, HTML, Draw.io)
- Test suite (371 tests)

MODES OF OPERATION:

MODE 1: STANDALONE (Dashboard + Orchestration)
  ✅ Dashboard at http://localhost:3001
  ✅ CLI commands (productforge list, docs, test, health)
  ✅ Project tracking and state management
  ✅ Workflow documentation generation
  ✅ NO opencode CLI required
  ✅ Install: pip install -e .

MODE 2: FULL AGENT EXECUTION (Includes agent runtime)
  ✅ Everything in MODE 1
  ✅ 17-agent pipeline execution
  ✅ LLM model integration and switching
  ✅ Agent task delegation and checkpoint system
  ✅ Model tier switching (/models recommended/cheap/etc.)
  ✅ Requires opencode CLI: pip install opencode
  ✅ Install: pip install -e . THEN pip install opencode

DEFAULT: MODE 1 (Standalone - works immediately after install)

If you want full agent execution, run step 2 after step 1.
"""

import subprocess
import sys
import platform
from pathlib import Path


def print_header():
    print("=" * 70)
    print("Product Forge - Multi-Agent Multi-Project System")
    print("=" * 70)
    print()


def print_mode_info():
    print("INSTALLATION MODES:")
    print("-" * 70)
    print("MODE 1: STANDALONE (Recommended for most users)")
    print("  - Dashboard + Orchestration + Tracking")
    print("  - Dashboard: http://localhost:3001")
    print("  - CLI: productforge list, docs, test, help")
    print("  - Pipeline: /pipeline list, health, checkpoints, dlq")
    print("  - NO opencode CLI required")
    print("  - Best for: Project management, monitoring, docs")
    print()
    print("MODE 2: FULL AGENT EXECUTION")
    print("  - Everything in MODE 1")
    print("  - 17-agent pipeline execution")
    print("  - LLM model switching (/models recommended/cheap/etc.)")
    print("  - Agent task delegation")
    print("  - Requires: pip install opencode")
    print("  - Best for: Actual agent workflow execution")
    print()


def install_core():
    """Install core dependencies"""
    print("1. Installing core Python dependencies...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", "."],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  FAILED: {result.stderr}")
        return False
    print("  ✓ Core package installed")
    return True


def install_pdf_deps():
    """Install PDF generation dependencies"""
    print("2. Installing PDF generation dependencies...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "weasyprint", "playwright"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  Warning: {result.stderr}")
    else:
        print("  ✓ PDF generation enabled")
    return True


def install_opencode():
    """Install opencode CLI for agent execution"""
    print("3. Installing opencode CLI (for full agent execution)...")
    print("   This is REQUIRED for MODE 2 only.")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "opencode"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  Warning: opencode install failed - {result.stderr[:200]}")
        print("   This is OK if you only want MODE 1 (Standalone).")
    else:
        print("  ✓ opencode CLI installed")
    return True


def verify_installation():
    """Verify the installation"""
    print("4. Verifying installation...")
    
    # Check core modules
    core_ok = True
    try:
        import core.main
        print("  ✓ Core modules: OK")
    except ImportError:
        print("  ✗ Core modules: FAILED")
        core_ok = False
    
    # Check dashboard
    dashboard_path = Path("pipeline_dashboard/index.html")
    if dashboard_path.exists():
        print("  ✓ Dashboard: OK")
    else:
        print("  ✗ Dashboard: FAILED")
        core_ok = False
    
    # Check agent files
    agents_dir = Path(".opencode/agent")
    if agents_dir.exists():
        agent_count = len(list(agents_dir.glob("*.md")))
        print(f"  ✓ Agent definitions: {agent_count} agents found")
    else:
        print("  ✗ Agent definitions: FAILED")
        core_ok = False
    
    # Check pipeline script
    pipeline_script = Path("scripts/pipeline.py")
    if pipeline_script.exists():
        print("  ✓ Pipeline script: OK")
    else:
        print("  ✗ Pipeline script: FAILED")
        core_ok = False
    
    return core_ok


def main():
    print_header()
    print_mode_info()
    
    # Step 1: Install core package
    print("=" * 70)
    print("STEP 1: Installing Product Forge Package")
    print("=" * 70)
    if not install_core():
        print("\nERROR: Failed to install core package")
        sys.exit(1)
    
    # Step 2: Install PDF dependencies
    print("\n" + "=" * 70)
    print("STEP 2: Installing PDF Generation Dependencies")
    print("=" * 70)
    install_pdf_deps()
    
    # Step 3: Ask about opencode CLI
    print("\n" + "=" * 70)
    print("STEP 3: opencode CLI Installation")
    print("=" * 70)
    print("This determines your mode:")
    print("  MODE 1: Skip opencode CLI (Standalone)")
    print("  MODE 2: Install opencode CLI (Full Agent Execution)")
    print()
    
    while True:
        choice = input("Install opencode CLI now? (y/n, default=y): ").strip().lower()
        if choice in ('', 'y'):
            install_opencode()
            break
        elif choice == 'n':
            print("\n✓ Skipping opencode CLI installation")
            print("   You can install later with: pip install opencode")
            break
        else:
            print("  Please enter 'y' or 'n'")
    
    # Step 4: Verify
    print("\n" + "=" * 70)
    print("STEP 4: Verifying Installation")
    print("=" * 70)
    if verify_installation():
        print("\n✓ Installation complete!")
    else:
        print("\n⚠ Installation completed with some issues")
    
    print("\n" + "=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print("MODE 1 - STANDALONE:")
    print("  1. Start dashboard: productforge dashboard")
    print("  2. Open browser: http://localhost:3001")
    print("  3. Run pipeline: productforge list")
    print()
    print("MODE 2 - FULL AGENT EXECUTION (after opencode install):")
    print("  1. Start dashboard: productforge dashboard")
    print("  2. Full pipeline: /pipeline new <idea>")
    print("  3. Model switching: /models recommended")
    print()
    print("DOCUMENTATION: README.md")
    print("HELP: productforge help")
    print("PIPELINE HELP: /pipeline help")


if __name__ == "__main__":
    main()