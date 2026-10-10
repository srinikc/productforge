"""Single local pre-check gate (BI-0205): branch -> gates -> review.

Runs the same checks CI enforces (compile, structure audit, matrix, secrets, tests) so a PR is
green before it is opened. Exit nonzero if any step fails. Run from `product-forge/`:
    python scripts/dev/precheck.py                 # changed-scoped tests (fast; default)
    python scripts/dev/precheck.py --full          # full test suite + validation/lifecycle (merge/CI)
    python scripts/dev/precheck.py --release       # --full + periodic full-tree sweeps (pre-release only)
    python scripts/dev/precheck.py --scope a,b      # explicit test-name substrings

Tiers (BI-PF-0385): the secret scan is **diff-scoped** by default (changed vs develop) so a merge/CI never
walks the whole tree; the full-tree sweep runs only under `--release` (a few times before a release). The
`wired-audit` advisory sub-audits are skipped in the fast tier (`--fast`).

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


def _changed_paths():
    return [c.replace("\\", "/") for c in _changed_files()]


# Each gate: (name, cmd, tier, area)  tier in {"fast","deep"}; area = list of path substrings OR None
# (None = always run in its tier). Fast tier = per-change/per-phase; deep tier = merge/CI (`--full`).
_GATES = [
    ("compile", ["-m", "compileall", "-q", "core", "scripts", "dashboard", "api"], "fast", None),
    ("pycompat", ["scripts/dev/pycompat_check.py"], "fast", None),
    ("ci-cd-gates", ["scripts/dev/ci_cd_gates_check.py"], "fast", None),
    ("wired-audit", ["scripts/dev/wired_audit.py"], "fast", None),
    ("store-contract", ["scripts/dev/store_check.py"], "fast", None),
    ("lint", ["scripts/dev/lint_check.py"], "fast", None),
    ("secret-scan", ["scripts/dev/secret_scan.py"], "fast", None),
    ("workflow-matrix", ["scripts/dev/workflow_matrix_check.py"], "fast", None),
    ("api-contract", ["scripts/dev/api_contract_check.py"], "fast", ["api/"]),
    ("api-governance", ["scripts/dev/api_governance_check.py"], "fast", ["api/"]),
    ("api-docs-regen", ["scripts/dev/api_docs_check.py", "--write"], "fast", ["api/"]),
    ("api-docs", ["scripts/dev/api_docs_check.py"], "fast", ["api/"]),
    ("engineering-flow", ["scripts/dev/engineering_flow_check.py"], "fast", ["config/engineering-flow.json"]),
    ("task-contract", ["scripts/dev/task_contract_check.py"], "fast", ["task_contract", "core/task"]),
    ("scheduler", ["scripts/dev/scheduler_check.py"], "fast", ["scheduler"]),
    ("lease", ["scripts/dev/lease_check.py"], "fast", ["job_manager", "lease"]),
    ("single-path", ["scripts/dev/single_path_check.py"], "fast", ["enhance", "worker"]),
    ("vcs-worktree", ["scripts/dev/vcs_worktree_check.py"], "fast", ["vcs"]),
    ("worker", ["scripts/dev/worker_check.py"], "fast", ["core/worker"]),
    ("reservations", ["scripts/dev/reservations_check.py"], "fast", ["reservations", "shared-paths"]),
    ("packaging", ["scripts/dev/packaging_check.py"], "fast", ["packaging"]),
    ("tool-catalog", ["scripts/dev/tool_catalog_check.py"], "fast", None),
    ("dependency-catalog", ["scripts/dev/dependency_catalog_check.py"], "fast", None),
    ("backlog-reconcile", ["scripts/dev/backlog_id_reconcile.py", "--write"], "fast", ["backlog"]),
    ("backlog-context", ["scripts/dev/backlog_context_check.py"], "fast", ["backlog"]),
    ("backlog-ids", ["scripts/dev/backlog_id_audit.py"], "fast", ["backlog"]),
    ("backlog-epic", ["scripts/dev/backlog_epic_audit.py"], "fast", ["backlog"]),
    ("grooming", ["scripts/dev/grooming_check.py"], "fast", ["grooming"]),
    ("github", ["scripts/dev/github_check.py"], "fast", ["github"]),
    ("dogfood-run", ["scripts/dev/dogfood_run_check.py"], "fast", ["dogfood", "dogfood_run", "api"]),
    ("pf-surface", ["scripts/dev/pf_surface_check.py"], "fast", None),
    ("wg-surface", ["scripts/dev/wg_surface_check.py"], "fast", None),
    ("global-commands", ["scripts/dev/sync_global_commands.py", "--check"], "fast", None),
    ("wg-go", ["scripts/dev/wg_go_check.py"], "fast", ["workergrid", "wg"]),
    ("pidl", ["scripts/dev/pidl_check.py"], "fast", ["pidl"]),
    ("pidl-gate", ["scripts/dev/pidl_gate_check.py"], "fast", ["pidl", "close_loop"]),
    ("pidl-synthesis", ["scripts/dev/pidl_synthesis_check.py"], "fast", ["pidl", "scheduler", "close_loop"]),
    ("pidl-trace", ["scripts/dev/pidl_trace_check.py"], "fast", ["pidl", "close_loop", "learning"]),
    ("staleness", ["scripts/dev/staleness_check.py"], "fast", ["grooming", "scheduler", "backlog"]),
    ("intent-trace", ["scripts/dev/intent_trace_check.py"], "fast", None),
    ("docs-fresh", ["scripts/dev/check_docs_fresh.py"], "fast", None),
    ("artifact-map", ["scripts/dev/gen_artifact_map.py", "--check"], "fast", None),
    ("review-focus", ["scripts/dev/gen_review_focus.py", "--check"], "fast", None),
    ("review-static", ["scripts/dev/review_static_check.py"], "fast", None),
    ("compliance-register", ["scripts/dev/compliance_register_check.py", "--check"], "fast", None),
    # deep tier - real validation/lifecycle work; merge/CI only
    ("validation-engine", ["scripts/dev/validation_engine_check.py"], "deep", None),
    ("feature-pr", ["scripts/dev/feature_pr_check.py"], "deep", None),
    ("merge-gate", ["scripts/dev/merge_gate_check.py"], "deep", None),
    ("dogfood", ["scripts/dev/dogfood_check.py"], "deep", None),
    ("dogfood-replay", ["scripts/dev/dogfood_replay_check.py"], "deep", None),
    ("dogfood-schedule", ["scripts/dev/dogfood_schedule_check.py"], "deep", None),
    ("repo-setup", ["scripts/dev/repo_setup_check.py"], "deep", None),
    ("rate-budget", ["scripts/dev/rate_budget_check.py"], "fast", None),
    ("release", ["scripts/dev/release_check.py"], "deep", None),
    ("final-audit", ["scripts/dev/final_audit_check.py"], "deep", None),
    ("backlog-e2e", ["scripts/dev/e2e_backlog_check.py"], "deep", None),
    # release tier - periodic/on-demand heavy sweeps; run before a release, NOT every merge/CI
    ("secret-scan-all", ["scripts/dev/secret_scan.py", "--all"], "release", None),
]


def _area_touched(area, changed):
    if not area:
        return True
    return any(any(a in c for a in area) for c in changed)


def _steps(full: bool, scope_csv: str, release: bool = False):
    changed = _changed_paths()
    steps = []
    for name, cmd, tier, area in _GATES:
        if tier == "deep" and not full:
            continue  # heavy validation/lifecycle gates -> merge/CI (--full)
        if tier == "release" and not release:
            continue  # periodic full-tree sweeps -> release only (--release)
        if tier == "fast" and not _area_touched(area, changed) and not full:
            continue  # skip unrelated area gates in the fast tier
        cmd_list = [sys.executable, *cmd]
        if name == "wired-audit" and not full:
            cmd_list.append("--fast")  # skip advisory sub-audits in the per-phase tier
        steps.append((name, cmd_list))
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
    release = "--release" in argv
    full = "--full" in argv or release
    scope_csv = ""
    for i, a in enumerate(argv):
        if a == "--scope" and i + 1 < len(argv):
            scope_csv = argv[i + 1]
        elif a.startswith("--scope="):
            scope_csv = a.split("=", 1)[1]
    tier = "release" if release else ("full" if full else "fast")
    print(f"[precheck] tier={tier} (fast = core+area gates+scoped tests; --full = +validation/lifecycle "
          f"+ full suite; --release = +periodic full-tree sweeps)")
    if not full:
        tests = _scoped_tests(scope_csv)
        print(f"[precheck] changed-scoped tests: {len(tests)} file(s) "
              f"(use --full for the complete suite)" if tests else
              "[precheck] no scope match -> running full test suite")
    import time as _time
    rc = 0
    timings = []
    t_all = _time.time()
    for name, cmd in _steps(full, scope_csv, release):
        print(f"\n=== precheck: {name} ===", flush=True)
        t0 = _time.time()
        try:
            r = subprocess.run(cmd, cwd=_ROOT)
        except FileNotFoundError as e:
            print(f"[SKIP] {name}: {e}")
            continue
        dt = _time.time() - t0
        timings.append((name, dt, r.returncode))
        if r.returncode != 0:
            print(f"[FAIL] {name} (exit {r.returncode}, {dt:.1f}s)")
            rc = 1
    total = _time.time() - t_all
    print(f"\nprecheck: {'PASS' if rc == 0 else 'FAIL'} (tier={tier}, {total:.1f}s, {len(timings)} gates)")
    slow = sorted(timings, key=lambda x: -x[1])[:5]
    print("[precheck] slowest: " + ", ".join(f"{n}={d:.1f}s" for n, d, _ in slow))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
