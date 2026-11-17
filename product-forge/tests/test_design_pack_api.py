import os
import sys
from pathlib import Path
os.environ.setdefault("PF_HIL_TOKEN", "hil-tok")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_design_pack_route_published():
    from api.app import app
    assert "/api/v1/backlog/items/{item_id}/design-pack" in app.openapi()["paths"]


def test_design_pack_requires_auth(monkeypatch):
    monkeypatch.delenv("PF_API_TOKEN", raising=False)
    monkeypatch.delenv("API_TOKEN", raising=False)
    monkeypatch.setenv("API_ALLOW_ANON", "0")
    from fastapi.testclient import TestClient
    from api.app import app
    r = TestClient(app).post("/api/v1/backlog/items/BI-PF-1544/design-pack", json={})
    assert r.status_code == 401


def test_design_pack_rejects_malformed(monkeypatch):
    monkeypatch.setenv("API_ALLOW_ANON", "1")
    from fastapi.testclient import TestClient
    from api.app import app
    r = TestClient(app).post("/api/v1/backlog/items/BI-PF-1544/design-pack",
                             headers={"X-Roles": "operator"}, json={"design_pack": []})
    assert r.status_code == 400
