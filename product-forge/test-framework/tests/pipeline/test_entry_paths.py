"""Retrofit R1: entry-path contract.

Intake is an external-ingestion path only; engineering work uses the direct Task/Work entry and never routes
through Intake. Guards: two independent paths, no intake-owned engineering step, and no direct pipeline
executor inside the intake router.
"""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import paths as _paths  # noqa: E402


def _force_rmtree(p) -> None:
    p = Path(p)
    if not p.exists():
        return
    for root, _dirs, files in os.walk(p, topdown=False):
        for name in files:
            try:
                os.chmod(os.path.join(root, name), 0o700)
            except Exception:
                pass
    shutil.rmtree(p, ignore_errors=True)


def test_engineering_flow_has_two_independent_entry_paths():
    from core import engineering_flow as ef
    res = ef.validate()
    assert res["ok"], res["errors"]
    assert ef.external_ingestion(), "external ingestion path must be represented separately"
    eng = ef.flow()
    assert eng and eng[0]["id"] == "task_contract", "engineering flow must start at the direct entry"
    assert all(s.get("owner") != "core/intake.py" for s in eng), \
        "engineering flow must not contain an intake-owned step"


def test_intent_router_enqueues_instead_of_executing():
    src = (Path(_paths.ROOT) / "core" / "intent_router.py").read_text(encoding="utf-8")
    assert "PipelineExecutor" not in src, "intake must not instantiate a pipeline executor directly"
    assert "execute_pipeline" not in src, "intake must not execute a pipeline directly"
    assert "run_entry" in src, "intake execution must go through the canonical run entry"


def test_direct_task_work_completes_without_intake():
    from core import task_contract
    name = "_test_entry_paths"
    d = Path(_paths.PRODUCTS_DIR) / name
    _force_rmtree(d)
    d.mkdir(parents=True, exist_ok=True)
    try:
        it = task_contract.create("project", name,
                                  {"title": "t", "objective": "o", "acceptance_criteria": ["a"]})
        assert it["task_id"].startswith("TC-")
        assert task_contract.get("project", name, it["task_id"])["objective"] == "o"
        # no conversation / intake record is required to create or read an engineering task
    finally:
        _force_rmtree(d)
