"""PFSSOT-P7 (BI-PF-0368): runtime-neutral worker adapter contract (OpenCode first)."""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import worker_adapters as wa  # noqa: E402
from core.paths import PRODUCTS_DIR  # noqa: E402

_PROJ = "_test_pfssot_p7"


def _clean():
    shutil.rmtree(os.path.join(str(PRODUCTS_DIR), _PROJ), ignore_errors=True)


def test_contract_and_registry():
    assert set(wa.ADAPTER_OPS) == {"register", "heartbeat", "get_status", "accept_assignment",
                                   "start", "pause", "cancel", "report_result", "disconnect"}
    runtimes = {a["runtime"] for a in wa.list_adapters()}
    assert {"opencode", "command", "native"} <= runtimes            # OpenCode is first, not only
    assert wa.resolve("opencode").runtime == "opencode"
    assert wa.resolve("nope") is None


def test_command_adapter_full_cycle():
    _clean()
    try:
        ad = wa.resolve("command")
        wid = ad.register("project", _PROJ, capabilities=["python"])["worker_id"]
        assert ad.accept_assignment("project", _PROJ, wid, "ASG-1")["status"] == "BUSY"
        wt = os.path.join(str(PRODUCTS_DIR), _PROJ, "wt")
        os.makedirs(wt, exist_ok=True)
        out = ad.start("project", _PROJ, wid, worktree=wt,
                       command=[sys.executable, "-c", "print('ok')"])
        assert out["ok"] is True and out["status"] == "pr_ready"
        assert ad.report_result("project", _PROJ, wid, {"task_id": "BI-X"})["status"] == "IDLE"
    finally:
        _clean()


def test_native_is_declared_not_routed():
    ad = wa.resolve("native")
    res = ad.start("project", _PROJ, "w", "", "")
    assert res["status"] == "native"                                # agents stay native (doc §43d)
    assert "pipeline executor" in res["output"]


def test_opencode_adapter_degrades_without_binary():
    ad = wa.resolve("opencode")
    if not ad.available():
        res = ad.start("project", _PROJ, "w", objective="x", worktree=".")
        assert res["ok"] is False and res["status"] == "blocked"    # optional, never a dependency
