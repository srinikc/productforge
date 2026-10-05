"""Single local pre-check gate (BI-0205): branch -> gates -> review.

Runs the same checks CI enforces (compile, structure audit, matrix, secrets, tests) so a PR is
green before it is opened. Exit nonzero if any step fails. Run from `product-forge/`:
    python scripts/dev/precheck.py                 # changed-scoped tests (fast; default)
    python scripts/dev/precheck.py --full          # full test suite (CI / merge / release)
    python scripts/dev/precheck.py --scope a,b      # explicit test-name substrings

Test scoping (BI-PF-0382): by DEFAULT the test step runs only the tests affected by CHANGED files
(`core/z.py` -> `test_z.py` + any test importing `core.z`), plus a small foundation smoke set. This
keeps everyday gates fast (~1 min). CI and merge/release run `--full` for the complete ~831-test suite.
The real-idea end-to-end remains the separate DOGFOOD lifecycle (dry in precheck).
"""
import os
import subprocess
import sys

# Run from product-forge/ (see docs/PR-WORKFLOW.md); resolve ROOT from core.paths, never re-derive.
if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())
from core.paths import ROOT as _PF_ROOT  # noqa: E402

_ROOT = str(_PF_ROOT)
_TEST_DIR = "test-framework/tests/pipeline"
_INTEGRATION = "develop"
# always-run smoke tests (core contracts) so a scoped run still exercises the spine
_SMOKE = ("test_api_foundation.py", "test_backlog_refs.py", "test_main.py")


def _git(*args):
    try:
        r = subprocess.run(["git", *args], cwd=_ROOT, capture_output=True, text=True)
        return (r.stdout or "").strip()
    except Exception:
        return ""


def _changed_files():
    files = set()
    base = _git("merge-base", _INTEGRATION, "HEAD")
    if base:
        for ln in _git("diff", "--name-only", base, "HEAD").splitlines():
            files.add(ln.strip())
    for ln in _git("diff", "--name-only", "HEAD").splitlines():
        files.add(ln.strip())
    return sorted(f for f in files if f)


def _scoped_tests(scope_csv: str = "") -> list[str]:
    """Test files (relative) affected by the changed files; empty => caller should not scope."""
    td = os.path.join(_ROOT, _TEST_DIR)
    if not os.path.isdir(td):
        return []
    all_tests = [f for f in os.listdir(td) if f.startswith("test_") and f.endswith(".py")]
    if scope_csv:
        wanted = [s.strip() for s in scope_csv.split(",") if s.strip()]
        return sorted(f"{_TEST_DIR}/{t}" for t in all_tests if any(w in t for w in wanted))
    changed = _changed_files()
    core_mods = {os.path.splitext(os.path.basename(c))[0] for c in changed
                 if c.replace("\\", "/").startswith("product-forge/core/") or c.startswith("core/")}
    test_mods = {os.path.splitext(os.path.basename(c))[0] for c in changed
                 if c.replace("\\", "/").endswith(".py") and "_test" in os.path.basename(c)
                 or c.replace("\\", "/").startswith(f"{_TEST_DIR}/")}
    picked: set[str] = set(_SMOKE)
    for t in all_tests:
        stem = t[len("test_"):-3]
        if stem in core_mods or any(m == stem or m in stem or stem in m for m in core_mods):
            picked.add(t)
    # tests whose filename matches a changed test module exactly
    for t in all_tests:
        if os.path.splitext(t)[0] in test_mods:
            picked.add(t)
    # tests that import a changed core module (grep)
    if core_mods:
        for t in all_tests:
            try:
                with open(os.path.join(td, t), encoding="utf-8", errors="ignore") as f:
                    text = f.read()
            except Exception:
                continue
            if any((f"import {m}") in text or (f"core.{m}") in text for m in core_mods):
                picked.add(t)
    return sorted(f"{_TEST_DIR}/{t}" for t in picked)


def _steps(full: bool, scope_csv: str):
    steps = [
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
        ("lease", [sys.executable, "scripts/dev/lease_check.py"]),
        ("worker-registry", [sys.executable, "scripts/dev/worker_registry_check.py"]),
        ("vcs-worktree", [sys.executable, "scripts/dev/vcs_worktree_check.py"]),
        ("worker", [sys.executable, "scripts/dev/worker_check.py"]),
        ("validation-engine", [sys.executable, "scripts/dev/validation_engine_check.py"]),
        ("feature-pr", [sys.executable, "scripts/dev/feature_pr_check.py"]),
        ("reservations", [sys.executable, "scripts/dev/reservations_check.py"]),
        ("merge-gate", [sys.executable, "scripts/dev/merge_gate_check.py"]),
        ("dogfood", [sys.executable, "scripts/dev/dogfood_check.py"]),
        ("release", [sys.executable, "scripts/dev/release_check.py"]),
        ("packaging", [sys.executable, "scripts/dev/packaging_check.py"]),
        ("grooming", [sys.executable, "scripts/dev/grooming_check.py"]),
        ("final-audit", [sys.executable, "scripts/dev/final_audit_check.py"]),
        ("github", [sys.executable, "scripts/dev/github_check.py"]),
        ("store-contract", [sys.executable, "scripts/dev/store_check.py"]),
        ("lint", [sys.executable, "scripts/dev/lint_check.py"]),
        ("intent-trace", [sys.executable, "scripts/dev/intent_trace_check.py"]),
        ("backlog-e2e", [sys.executable, "scripts/dev/e2e_backlog_check.py"]),
        ("docs-fresh", [sys.executable, "scripts/dev/check_docs_fresh.py"]),
        ("secret-scan", [sys.executable, "scripts/dev/secret_scan.py"]),
    ]
    if full:
        steps.append(("pipeline-tests-full",
                      [sys.executable, "-m", "pytest", _TEST_DIR, "-q", "-o", "addopts="]))
    else:
        tests = _scoped_tests(scope_csv)
        if tests:
            steps.append(("tests-scoped", [sys.executable, "-m", "pytest", *tests, "-q", "-o", "addopts="]))
        else:
            steps.append(("pipeline-tests-full",
                          [sys.executable, "-m", "pytest", _TEST_DIR, "-q", "-o", "addopts="]))
    return steps


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    full = "--full" in argv
    scope_csv = ""
    for i, a in enumerate(argv):
        if a == "--scope" and i + 1 < len(argv):
            scope_csv = argv[i + 1]
        elif a.startswith("--scope="):
            scope_csv = a.split("=", 1)[1]
    if not full:
        tests = _scoped_tests(scope_csv)
        print(f"[precheck] changed-scoped tests: {len(tests)} file(s) "
              f"(use --full for the complete suite)" if tests else
              "[precheck] no scope match -> running full test suite")
    rc = 0
    for name, cmd in _steps(full, scope_csv):
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
