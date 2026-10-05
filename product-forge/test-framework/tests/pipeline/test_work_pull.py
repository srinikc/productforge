"""PFSSOT-P8 (BI-PF-0369): manual work pull (first e2e milestone)."""
import contextlib
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
os.environ.setdefault("PF_OFFLINE", "1")

from core import backlog, grooming, job_manager, work_pull  # noqa: E402
from core.paths import PRODUCTS_DIR  # noqa: E402

_PROJ = "_test_pfssot_p8"


def _clean():
    shutil.rmtree(os.path.join(str(PRODUCTS_DIR), _PROJ), ignore_errors=True)
    with contextlib.suppress(Exception):
        c = job_manager._db()
        c.execute("DELETE FROM jobs WHERE project=?", (_PROJ,))
        c.commit()
        c.close()


def _eligible(title="Add CSV export"):
    iid = backlog.add_epic("project", _PROJ, title, tag="TST")["id"]
    grooming.decide("project", _PROJ, iid, "APPROVE")
    return iid


def test_pull_returns_assignment_package():
    _clean()
    try:
        iid = _eligible()
        r = work_pull.pull("project", _PROJ, runtime="command")
        assert r["assigned"] is True
        pkg = r["package"]
        assert pkg["task"]["item_id"] == iid
        assert pkg["worker_id"] and pkg["lease_id"] and pkg["lease_expires_at"]
        assert pkg["contract_status"] == "OK"          # contract is valid (deliverables non-empty)
        # the stored analysis travels with the assignment (pickup = execute, not re-architect)
        assert pkg["task"]["analysis"]["status"] == "COMPLETE"
    finally:
        _clean()


def test_no_double_pull():
    _clean()
    try:
        _eligible()
        assert work_pull.pull("project", _PROJ, runtime="command")["assigned"] is True
        r2 = work_pull.pull("project", _PROJ, runtime="command")
        assert r2["assigned"] is False
    finally:
        _clean()


def test_pull_requires_registered_worker():
    _clean()
    try:
        assert work_pull.pull("project", _PROJ)["assigned"] is False   # no worker_id / runtime
    finally:
        _clean()


def test_start_via_command_adapter():
    _clean()
    try:
        iid = _eligible()
        work_pull.pull("project", _PROJ, runtime="command")
        wt = os.path.join(str(PRODUCTS_DIR), _PROJ, "wt")
        os.makedirs(wt, exist_ok=True)
        st = work_pull.start("project", _PROJ, iid, worktree=wt,
                             command=[sys.executable, "-c", "print('ok')"])
        assert st["ok"] and st["adapter"] == "command" and st["result"]["status"] == "pr_ready"
    finally:
        _clean()
