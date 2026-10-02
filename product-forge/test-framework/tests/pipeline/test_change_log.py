"""Engineering change log: append-only drift + corrective-action records, live entries, API."""
import contextlib
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
os.environ.setdefault("API_ALLOW_ANON", "1")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.app import app  # noqa: E402
from core import change_log as _cl  # noqa: E402
from core import paths as _paths  # noqa: E402

_SCRATCH = "_test_change_log"


def _force_rmtree(p) -> None:
    p = Path(p)
    if not p.exists():
        return
    for root, _dirs, files in os.walk(p, topdown=False):
        for name in files:
            with contextlib.suppress(Exception):
                os.chmod(os.path.join(root, name), 0o700)
    shutil.rmtree(p, ignore_errors=True)


@pytest.fixture()
def client():
    return TestClient(app)


def test_change_log_append_and_read(tmp_path):
    d = Path(_paths.PRODUCTS_DIR) / _SCRATCH
    _force_rmtree(d)
    d.mkdir(parents=True, exist_ok=True)
    try:
        r = _cl.record("project", _SCRATCH, kind="drift", summary="openapi drift",
                       detected_by="test", before="a", after="b", action="regenerated",
                       commit="abc123", revert_ref="abc123")
        assert r and r["id"].startswith("CHG-")
        recs = _cl.list_records("project", _SCRATCH)
        assert len(recs) == 1 and recs[0]["summary"] == "openapi drift"
        # invalid kind normalizes; missing summary -> None
        assert _cl.record("project", _SCRATCH, kind="bogus", summary="x")["kind"] == "correction"
        assert _cl.record("project", _SCRATCH, summary="") is None
    finally:
        _force_rmtree(d)


def test_change_log_live_has_entries():
    recs = _cl.list_records("product_forge")
    assert recs, "expected seeded engineering change records"
    assert any(r.get("kind") == "drift" for r in recs)


def test_change_api(client):
    r = client.get("/api/v1/changes", params={"scope": "product_forge"})
    assert r.status_code == 200
    assert isinstance(r.json()["data"], list)
    r2 = client.get("/api/v1/changes/kinds")
    assert r2.status_code == 200
    assert "drift" in r2.json()["data"]["kinds"]
