"""BI-PF-0355: the generated API reference surface (JSON + HTML + render)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
os.environ.setdefault("API_ALLOW_ANON", "1")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.app import app  # noqa: E402


@pytest.fixture()
def client():
    return TestClient(app)


def test_apidocs_json(client):
    r = client.get("/api/v1/apidocs." + "json")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["path_count"] > 0 and d["operation_count"] > 0
    assert any(g["tag"] == "health" for g in d["groups"])


def test_apidocs_html(client):
    r = client.get("/api/v1/apidocs")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Search endpoints" in r.text and "API Reference" in r.text


def test_apidocs_render_html_and_bad_format(client):
    r = client.post("/api/v1/apidocs/render", json={"format": "html"})
    assert r.status_code == 200
    assert r.json()["data"]["format"] == "html"
    bad = client.post("/api/v1/apidocs/render", json={"format": "docx"})
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "VALIDATION_FAILED"
