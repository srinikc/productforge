"""REL-0: packaging manifest API (editions, validate, fail-closed)."""
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
from core import paths as _paths  # noqa: E402

_SCRATCH = "_test_packaging_api"


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
def project():
    d = Path(_paths.PRODUCTS_DIR) / _SCRATCH
    _force_rmtree(d)
    d.mkdir(parents=True, exist_ok=True)
    yield _SCRATCH
    _force_rmtree(d)


def test_editions(client):
    r = client.get("/api/v1/packaging/editions")
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert set(d["editions"]) == {"community", "enterprise", "saas", "on-prem", "oem"}
    assert "entitlement" in d["distinctions"]


def test_validate_enterprise(client, project):
    r = client.get("/api/v1/packaging/validate",
                   params={"scope": "project", "project": project, "edition": "enterprise"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["valid"] is True


def test_build_persists_manifest(client, project):
    r = client.post("/api/v1/packaging/build",
                    json={"scope": "project", "project": project, "edition": "saas"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["ok"] is True
    assert (Path(_paths.PRODUCTS_DIR) / project / "packaging-manifest.json").exists()


def test_unknown_edition_rejected(client, project):
    r = client.post("/api/v1/packaging/build",
                    json={"scope": "project", "project": project, "edition": "bogus"})
    assert r.status_code in (400, 422), r.text
