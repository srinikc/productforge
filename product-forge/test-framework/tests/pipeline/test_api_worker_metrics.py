"""Worker timing / human-wait / token-cost metrics (reused owners)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
os.environ.setdefault("API_ALLOW_ANON", "1")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.app import app  # noqa: E402
from core import worker  # noqa: E402


@pytest.fixture()
def client():
    return TestClient(app)


def test_worker_metrics_shape(client):
    r = client.get("/api/v1/workers/metrics", params={"scope": "product_forge"})
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    for k in ("duration_ms", "wait_ms", "total_ms", "input_tokens", "output_tokens", "cost", "by_worker"):
        assert k in d


def test_run_time_cost_endpoint(client):
    r = client.get("/api/v1/runs/time-cost", params={"project": "_nonexistent_project_xyz"})
    assert r.status_code in (200, 404), r.text


def test_run_totals_separates_wait_from_duration():
    tot = worker.run_totals("project", "_probe_totals")
    assert tot["total_ms"] == tot["duration_ms"] + tot["wait_ms"]


def test_usage_extraction_and_cost():
    u = worker._extract_usage({"usage": {"input_tokens": 100, "output_tokens": 50, "model": "m"}})
    assert u["input_tokens"] == 100 and u["output_tokens"] == 50
    assert u["cost"] >= 0.0
    m = worker.WorkerResult(task_id="t")
    m.timing = {"duration_ms": 10, "wait_ms": 5}
    assert m.metrics()["total_ms"] == 15
