"""PFSSOT-P9 (BI-PF-0371): automatic dispatch (configurable, default off)."""
import contextlib
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
os.environ.setdefault("PF_OFFLINE", "1")

from core import backlog, dispatcher, grooming, job_manager, worker_registry  # noqa: E402
from core.paths import PRODUCTS_DIR  # noqa: E402

_PROJ = "_test_pfssot_p9"


def _clean():
    shutil.rmtree(os.path.join(str(PRODUCTS_DIR), _PROJ), ignore_errors=True)
    with contextlib.suppress(Exception):
        c = job_manager._db()
        c.execute("DELETE FROM jobs WHERE project=?", (_PROJ,))
        c.commit()
        c.close()


def test_default_off():
    _clean()
    try:
        assert dispatcher.enabled() is False           # WORKER_AUTO_DISPATCH default 0
        r = dispatcher.tick("project", _PROJ)
        assert r["ran"] is False and "disabled" in r["reason"]
    finally:
        _clean()


def test_forced_tick_assigns_to_available_worker():
    _clean()
    try:
        worker_registry.register("project", _PROJ, runtime="command", capabilities=["python"])
        iid = backlog.add_epic("project", _PROJ, "Feature X", tag="TST")["id"]
        grooming.decide("project", _PROJ, iid, "APPROVE")
        r = dispatcher.tick("project", _PROJ, force=True)
        assert r["ran"] is True and r["assigned"] and r["assigned"][0]["item"] == iid
        # second pass: nothing left (item already claimed)
        assert dispatcher.tick("project", _PROJ, force=True)["assigned"] == []
    finally:
        _clean()


def test_no_worker_no_assignment():
    _clean()
    try:
        iid = backlog.add_epic("project", _PROJ, "Feature Y", tag="TST")["id"]
        grooming.decide("project", _PROJ, iid, "APPROVE")
        r = dispatcher.tick("project", _PROJ, force=True)
        assert r["ran"] is True and r["assigned"] == []
    finally:
        _clean()


def test_integration_disabled_is_noop(monkeypatch):
    monkeypatch.setenv("WORKER_INTEGRATION_ENABLED", "0")
    r = dispatcher.tick("project", _PROJ, force=True)
    assert r["ran"] is False and "integration disabled" in r["reason"]
