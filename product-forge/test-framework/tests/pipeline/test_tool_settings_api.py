"""BI-PF-0439: web_search settings API (API-first) + settings/secret store (key never returned)."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from core import tool_settings  # noqa: E402


def _tmp_store(tmp_path, monkeypatch):
    monkeypatch.setattr(tool_settings, "_SETTINGS", str(tmp_path / "settings.json"))
    monkeypatch.setattr(tool_settings, "_SECRETS", str(tmp_path / "secrets.json"))
    for k in ("PF_WEB_SEARCH_BACKEND", "PF_WEB_SEARCH_URL", "PF_WEB_SEARCH_KEY",
              "BRAVE_SEARCH_API_KEY", "TAVILY_API_KEY"):
        monkeypatch.delenv(k, raising=False)


def test_store_roundtrip_and_key_hidden(tmp_path, monkeypatch):
    _tmp_store(tmp_path, monkeypatch)
    assert tool_settings.effective()["backend"] == "none"
    tool_settings.save(backend="searxng", url="http://127.0.0.1:8888")
    e = tool_settings.effective()
    assert e["backend"] == "searxng" and e["url"].startswith("http") and e["has_key"] is False
    tool_settings.save(api_key="secret123")
    e2 = tool_settings.effective()
    assert e2["has_key"] is True and e2["key"] == "secret123"   # internal readers get the key


def test_env_overrides_store(tmp_path, monkeypatch):
    _tmp_store(tmp_path, monkeypatch)
    tool_settings.save(backend="searxng", url="http://store")
    monkeypatch.setenv("PF_WEB_SEARCH_BACKEND", "brave")
    monkeypatch.setenv("PF_WEB_SEARCH_URL", "http://env")
    e = tool_settings.effective()
    assert e["backend"] == "brave" and e["url"] == "http://env" and e["source"] == "env"


def test_web_search_api_get_put(tmp_path, monkeypatch):
    _tmp_store(tmp_path, monkeypatch)
    monkeypatch.setenv("API_ALLOW_ANON", "1")
    from fastapi.testclient import TestClient
    from api.app import app
    client = TestClient(app)

    r = client.get("/api/v1/tools/web-search")
    assert r.status_code == 200 and r.json()["data"]["backend"] == "none", r.text

    r2 = client.put("/api/v1/tools/web-search",
                    json={"backend": "tavily", "url": "", "api_key": "k-123"})
    assert r2.status_code == 200, r2.text
    d = r2.json()["data"]
    assert d["backend"] == "tavily" and d["has_key"] is True and "k-123" not in r2.text

    r3 = client.put("/api/v1/tools/web-search", json={"backend": "bogus"})
    assert r3.status_code in (400, 422), r3.text
