"""BI-PF-0462: collision-safe backlog id allocation (reserve blocks; API authority; backlog integration)."""
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from core import backlog, id_allocator as ia  # noqa: E402
from core.paths import PRODUCTS_DIR  # noqa: E402


def test_blocks_are_disjoint(tmp_path, monkeypatch):
    monkeypatch.setattr(ia, "OUT", str(tmp_path / ("b" + ".json")))
    a = ia.reserve("product_forge", None, size=10, session="A")
    b = ia.reserve("product_forge", None, size=10, session="B")
    assert a["end"] < b["start"], (a, b)          # two sessions never share a block


def test_alloc_within_block_and_rollover(tmp_path, monkeypatch):
    monkeypatch.setattr(ia, "OUT", str(tmp_path / ("b" + ".json")))
    monkeypatch.setenv("PF_ID_BLOCK_SIZE", "2")
    ns = [ia.alloc("product_forge", None, session="A") for _ in range(5)]
    assert ns == sorted(set(ns)) and len(set(ns)) == 5   # unique + increasing across rollover


def test_backlog_add_uses_allocator(tmp_path, monkeypatch):
    monkeypatch.setattr(ia, "OUT", str(tmp_path / ("b" + ".json")))
    monkeypatch.setenv("PF_SESSION_ID", "S1")
    P = "_test_idalloc"
    shutil.rmtree(os.path.join(str(PRODUCTS_DIR), P), ignore_errors=True)
    try:
        a = backlog.add_epic("project", P, title="first distinct item here")
        b = backlog.add_epic("project", P, title="second distinct item here")
        assert a["id"] != b["id"]
    finally:
        shutil.rmtree(os.path.join(str(PRODUCTS_DIR), P), ignore_errors=True)


def test_api_reserve_endpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(ia, "OUT", str(tmp_path / ("b" + ".json")))
    monkeypatch.setenv("API_ALLOW_ANON", "1")
    from fastapi.testclient import TestClient
    from api.app import app
    c = TestClient(app)
    r = c.post("/api/v1/backlog/ids:reserve", json={"scope": "product_forge", "size": 10})
    assert r.status_code == 200 and r.json()["data"]["start"] >= 1, r.text
