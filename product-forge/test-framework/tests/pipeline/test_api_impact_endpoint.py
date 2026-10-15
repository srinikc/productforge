"""BI-PF-1406: the api-impact write endpoint is wired (API-first decision recording is API-only)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
os.environ.setdefault("API_ALLOW_ANON", "1")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import app  # noqa: E402

_PATH = "/api/v1/backlog/items/{item_id}/api-impact"


def test_api_impact_route_is_wired():
    spec = TestClient(app).get("/openapi.json").json()
    assert _PATH in spec["paths"]
    assert "post" in spec["paths"][_PATH]
