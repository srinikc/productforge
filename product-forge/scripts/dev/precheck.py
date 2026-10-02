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
        ("api-governance", [sys.executable, "scripts/dev/api_governance_check.py"]),
        # keep generated API docs in lockstep with the API surface, then verify freshness
        ("api-docs-regen", [sys.executable, "scripts/dev/api_docs_check.py", "--write"]),
        ("api-docs", [sys.executable, "scripts/dev/api_docs_check.py"]),
        ("engineering-flow", [sys.executable, "scripts/dev/engineering_flow_check.py"]),
        ("task-contract", [sys.executable, "scripts/dev/task_contract_check.py"]),
        ("scheduler", [sys.executable, "scripts/dev/scheduler_check.py"]),
        ("vcs-worktree", [sys.executable, "scripts/dev/vcs_worktree_check.py"]),
        ("worker", [sys.executable, "scripts/dev/worker_check.py"]),
        ("validation-engine", [sys.executable, "scripts/dev/validation_engine_check.py"]),
        ("feature-pr", [sys.executable, "scripts/dev/feature_pr_check.py"]),
        ("reservations", [sys.executable, "scripts/dev/reservations_check.py"]),
        ("merge-gate", [sys.executable, "scripts/dev/merge_gate_check.py"]),
        ("dogfood", [sys.executable, "scripts/dev/dogfood_check.py"]),
        ("release", [sys.executable, "scripts/dev/release_check.py"]),
        ("github", [sys.executable, "scripts/dev/github_check.py"]),
        ("store-contract", [sys.executable, "scripts/dev/store_check.py"]),
        ("lint", [sys.executable, "scripts/dev/lint_check.py"]),
        ("intent-trace", [sys.executable, "scripts/dev/intent_trace_check.py"]),
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
