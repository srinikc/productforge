"""Single local pre-check gate (BI-0205): branch -> gates -> review.

Runs the same checks CI enforces (compile, structure audit, matrix, secrets, tests) so a PR is
green before it is opened. Exit nonzero if any step fails. Run from `product-forge/`:
    python scripts/dev/precheck.py
"""
import os
import subprocess
import sys

# Run from product-forge/ (see docs/PR-WORKFLOW.md); resolve ROOT from core.paths, never re-derive.
if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())
from core.paths import ROOT as _PF_ROOT  # noqa: E402

_ROOT = str(_PF_ROOT)


def _steps():
    return [
        ("compile", [sys.executable, "-m", "compileall", "-q", "core", "scripts", "dashboard", "api"]),
        ("wired-audit", [sys.executable, "scripts/dev/wired_audit.py"]),
        ("workflow-matrix", [sys.executable, "scripts/dev/workflow_matrix_check.py"]),
        ("api-contract", [sys.executable, "scripts/dev/api_contract_check.py"]),
        ("engineering-flow", [sys.executable, "scripts/dev/engineering_flow_check.py"]),
        ("task-contract", [sys.executable, "scripts/dev/task_contract_check.py"]),
        ("scheduler", [sys.executable, "scripts/dev/scheduler_check.py"]),
        ("backlog-e2e", [sys.executable, "scripts/dev/e2e_backlog_check.py"]),
        ("docs-fresh", [sys.executable, "scripts/dev/check_docs_fresh.py"]),
        ("secret-scan", [sys.executable, "scripts/dev/secret_scan.py"]),
        ("pipeline-tests", [sys.executable, "-m", "pytest", "test-framework/tests/pipeline",
                            "-q", "-o", "addopts="]),
    ]


def main(argv=None) -> int:
    rc = 0
    for name, cmd in _steps():
        print(f"\n=== precheck: {name} ===", flush=True)
        try:
            r = subprocess.run(cmd, cwd=_ROOT)
        except FileNotFoundError as e:
            print(f"[SKIP] {name}: {e}")
            continue
        if r.returncode != 0:
            print(f"[FAIL] {name} (exit {r.returncode})")
            rc = 1
    print("\nprecheck:", "PASS" if rc == 0 else "FAIL")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
