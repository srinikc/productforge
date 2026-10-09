"""BI-PF-0564: allocator defaults to the reachable local API; explicit PF_API_URL wins; off disables."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from core import id_allocator as ia  # noqa: E402


def test_api_base_precedence(monkeypatch):
    monkeypatch.setenv("PF_ID_ALLOC_API", "on")
    monkeypatch.setenv("PF_API_URL", "http://explicit:1")
    assert ia._api_base() == "http://explicit:1"          # explicit wins
    monkeypatch.delenv("PF_API_URL", raising=False)
    monkeypatch.setattr(ia, "_up", lambda b: True)         # pretend the local API is up
    ia._API_CACHE["base"] = None
    ia._API_CACHE["at"] = 0.0
    assert ia._api_base().startswith("http://127.0.0.1:8000")
    monkeypatch.setenv("PF_ID_ALLOC_API", "off")           # disabled -> local blocks only
    assert ia._api_base() == ""


def test_remote_reserve_used_when_reachable(monkeypatch):
    monkeypatch.setenv("PF_ID_ALLOC_API", "on")
    monkeypatch.setattr(ia, "_api_base", lambda: "http://api")
    import requests

    def fake_post(url, json=None, headers=None, timeout=None):
        class Resp:
            status_code = 200

            def json(self):
                return {"data": {"start": 1000, "end": 1099}}
        return Resp()

    monkeypatch.setattr(requests, "post", fake_post)
    assert ia._reserve_remote("product_forge", None, 100) == {"start": 1000, "end": 1099}


def test_local_fallback_when_unreachable(monkeypatch):
    monkeypatch.setattr(ia, "_api_base", lambda: "http://down")
    import requests
    monkeypatch.setattr(requests, "post", lambda *a, **k: (_ for _ in ()).throw(ConnectionError()))
    assert ia._reserve_remote("product_forge", None, 100) is None
