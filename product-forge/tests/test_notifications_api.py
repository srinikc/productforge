import os
os.environ.setdefault("API_ALLOW_ANON", "1")
from fastapi.testclient import TestClient
from api.app import app


def test_notification_stored():
    r = TestClient(app).post("/api/v1/notifications", headers={"X-Roles": "operator"},
        json={"project": "product_forge", "title": "t", "message": "m", "priority": "high"})
    assert r.status_code == 200
    assert r.json()["data"]["stored"] is True


def test_notification_rejects_bad_priority():
    r = TestClient(app).post("/api/v1/notifications", headers={"X-Roles": "operator"},
        json={"project": "product_forge", "title": "t", "message": "m", "priority": "urgent"})
    assert r.status_code == 400
