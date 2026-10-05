"""PFSSOT-P6 (BI-PF-0367): minimal worker registry + heartbeat + lifecycle (runtime-neutral)."""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import worker_registry as wr  # noqa: E402
from core.paths import PRODUCTS_DIR  # noqa: E402

_PROJ = "_test_pfssot_p6"


def _clean():
    shutil.rmtree(os.path.join(str(PRODUCTS_DIR), _PROJ), ignore_errors=True)


def test_register_heartbeat_and_slots():
    _clean()
    try:
        r = wr.register("project", _PROJ, runtime="opencode", capabilities=["python"], role="implement")
        assert r["worker_id"] and r["status"] == "ONLINE"
        assert [s["slot_id"] for s in wr.available_slots("project", _PROJ)] == [f"reg:{r['worker_id']}"]
        hb = wr.heartbeat("project", _PROJ, r["worker_id"], status="BUSY")
        assert hb["ok"] and hb["status"] == "BUSY"
        # BUSY is not an available slot
        assert wr.available_slots("project", _PROJ) == []
    finally:
        _clean()


def test_stale_derived_from_heartbeat_age():
    _clean()
    try:
        r = wr.register("project", _PROJ, runtime="cli", capabilities=["python"])
        st = wr._read("project", _PROJ)
        st["workers"][r["worker_id"]]["last_heartbeat"] = "2000-01-01T00:00:00"
        wr._write("project", _PROJ, st)
        assert wr.get("project", _PROJ, r["worker_id"])["status"] == "STALE"
    finally:
        _clean()


def test_unregister_and_revoke():
    _clean()
    try:
        r = wr.register("project", _PROJ, runtime="opencode")
        assert wr.unregister("project", _PROJ, r["worker_id"])["removed"] is True
        assert wr.get("project", _PROJ, r["worker_id"]) is None
        r2 = wr.register("project", _PROJ, runtime="opencode")
        assert wr.unregister("project", _PROJ, r2["worker_id"], revoke=True)["revoked"] is True
        assert wr.get("project", _PROJ, r2["worker_id"])["status"] == "OFFLINE"
    finally:
        _clean()


def test_invalid_status_rejected():
    _clean()
    try:
        r = wr.register("project", _PROJ, runtime="opencode")
        try:
            wr.set_status("project", _PROJ, r["worker_id"], "BOGUS")
            raise AssertionError("bad status should raise")
        except ValueError:
            pass
    finally:
        _clean()
