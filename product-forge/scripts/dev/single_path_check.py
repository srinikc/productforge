"""Gate: one submission path (JobManager) + the worker/scheduler layer is DECOUPLED out of PF.

1. SINGLE SUBMISSION PATH: only sanctioned entries construct PipelineExecutor and run it. Any NEW direct
   ``PipelineExecutor(...).execute_pipeline()`` outside the allowlist is a bypass (fail-closed for NEW).
2. DECOUPLED: the worker/scheduler layer (worker_registry, worker_adapters, work_pull, dispatcher) must NOT
   exist in ``core/`` and must not be imported by core - it lives in the external WorkerGrid component
   (ADR-0002). See ``docs/WORKERGRID-DESIGN.md``.

Baseline-aware: pre-existing direct-executor call sites are allowlisted; NEW offenders fail.
Run: ``python scripts/dev/single_path_check.py``.
"""
import os
import re
import sys

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

FAILS = []

# sanctioned direct-executor entries (the CLI adapter + the executor's own module + the guarded helper)
_ALLOW = {
    "core/pipeline_executor.py",   # the engine itself + its convenience fn (guarded by run-lock)
    "scripts/run_pipeline.py",     # CLI adapter (registers/finishes a JobManager job)
}
# worker-layer modules that must NOT exist in PF core (decoupled into WorkerGrid)
_WORKER_LAYER = ("worker_registry", "worker_adapters", "work_pull", "dispatcher")


def _check(cond, msg):
    if not cond:
        FAILS.append(msg)


def _iter_py(root):
    for dp, _dn, fn in os.walk(os.path.join(_ROOT, root)):
        if "__pycache__" in dp or "node_modules" in dp:
            continue
        for f in fn:
            if f.endswith(".py"):
                yield os.path.join(dp, f).replace("\\", "/").replace(_ROOT.replace("\\", "/") + "/", "")


def main() -> int:
    # 1) single submission path - the BYPASS is running the pipeline directly (execute_pipeline()).
    _exec_re = re.compile(r"\.execute_pipeline\(\)")
    offenders = []
    for rel in list(_iter_py("core")) + list(_iter_py("scripts")):
        rel_norm = rel.replace("\\", "/")
        if rel_norm in _ALLOW or rel_norm.startswith("scripts/"):
            continue  # scripts/ = CLI/tooling; scripts/dev/ = dev/tests
        try:
            with open(os.path.join(_ROOT, rel), encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except Exception:
            continue
        if _exec_re.search(text):
            offenders.append(rel_norm)
    if offenders:
        for o in offenders:
            FAILS.append(f"direct PipelineExecutor/execute_pipeline outside the allowlist: {o}")

    # 2) decoupled - the worker/scheduler layer must be ABSENT from PF core
    for mod in _WORKER_LAYER:
        _check(not os.path.exists(os.path.join(_ROOT, "core", f"{mod}.py")),
               f"core/{mod}.py must NOT exist (decoupled into WorkerGrid)")

    # 3) core must not import the (removed) worker layer
    for rel in _iter_py("core"):
        rel_norm = rel.replace("\\", "/")
        try:
            with open(os.path.join(_ROOT, rel), encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except Exception:
            continue
        for mod in _WORKER_LAYER:
            if f"import {mod}" in text or f"core.{mod}" in text:
                FAILS.append(f"core module {rel_norm} imports removed worker layer '{mod}'")

    if FAILS:
        print("single-path: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("single-path: OK (one submission path; worker/scheduler layer decoupled into WorkerGrid)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
