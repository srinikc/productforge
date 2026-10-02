"""ENG-10: release readiness / gate API (fail-closed)."""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
os.environ.setdefault("API_ALLOW_ANON", "1")

import contextlib

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.app import app  # noqa: E402
from core import paths as _paths  # noqa: E402

_SCRATCH = "_test_release_api"


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


@pytest.fixture()
def empty_project():
    d = Path(_paths.PRODUCTS_DIR) / _SCRATCH
    _force_rmtree(d)
    d.mkdir(parents=True, exist_ok=True)
    yield _SCRATCH
    _force_rmtree(d)


def test_gate_blocked_on_empty_candidate(client, empty_project):
    r = client.get("/api/v1/release/gate", params={"scope": "project", "project": empty_project})
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["can_release"] is False
    assert d["decision"] == "blocked"
    assert {"release_validation", "build", "packaging_bom", "deployment", "merge_gate"}.issubset(d["items"])


def test_readiness_blocked_on_empty_candidate(client, empty_project):
    r = client.get("/api/v1/release/readiness", params={"scope": "project", "project": empty_project})
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["can_release"] is False
    assert d["unmet"]


def test_gate_statuses_closed_set(client, empty_project):
    r = client.get("/api/v1/release/gate", params={"scope": "project", "project": empty_project})
    items = r.json()["data"]["items"]
    allowed = {"pass", "fail", "unknown", "skip"}
    assert all(v["status"] in allowed for v in items.values())


def test_record_evidence(client, empty_project):
    r = client.post("/api/v1/release/gate",
                    json={"scope": "project", "project": empty_project, "record": True})
    assert r.status_code == 200, r.text
    ev = Path(_paths.PRODUCTS_DIR) / empty_project / "validation" / "release-evidence.jsonl"
    assert ev.exists()
    rows = [ln for ln in ev.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert rows and '"decision": "blocked"' in rows[-1]
