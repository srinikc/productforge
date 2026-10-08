"""BI-0211: tool/SDK/vendor catalog - decision table, gate, and read API."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from core import tool_catalog  # noqa: E402


def test_license_class_decision_table():
    assert tool_catalog.license_class("MIT") == "permissive"
    assert tool_catalog.license_class("Apache-2.0") == "permissive"
    assert tool_catalog.license_class("GPL-2.0") == "strong-copyleft"
    assert tool_catalog.license_class("AGPL-3.0") == "network-copyleft"
    assert tool_catalog.license_class("who-knows") == "restricted"   # fail-closed
    assert tool_catalog.class_bundle_allowed("permissive") is True
    assert tool_catalog.class_bundle_allowed("network-copyleft") is False


def test_seed_catalog_is_consistent():
    assert tool_catalog.validate() == []
    who = tool_catalog.lookup("whoogle")
    assert who and who["license_class"] == "permissive"
    assert tool_catalog.lookup("nope") is None


def test_gate_blocks_non_bundleable_bundled_entry(tmp_path, monkeypatch):
    bad = {"entries": [
        {"name": "gpl-widget", "kind": "python-lib", "license_id": "GPL-3.0",
         "license_class": "strong-copyleft", "bundle_allowed": False, "bundled": True, "source": "pypi"},
    ]}
    p = tmp_path / "tool-catalog.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    monkeypatch.setattr(tool_catalog, "OUT", str(p))
    probs = tool_catalog.validate()
    assert any("bundled but" in x for x in probs), probs
    from scripts.dev import tool_catalog_check
    assert tool_catalog_check.main() == 1


def test_catalog_api(monkeypatch):
    monkeypatch.setenv("API_ALLOW_ANON", "1")
    from fastapi.testclient import TestClient
    from api.app import app
    c = TestClient(app)
    r = c.get("/api/v1/tools/catalog")
    assert r.status_code == 200 and r.json()["data"]["count"] >= 5, r.text
    r2 = c.get("/api/v1/tools/catalog/whoogle")
    assert r2.status_code == 200 and r2.json()["data"]["name"] == "whoogle", r2.text
    r3 = c.get("/api/v1/tools/catalog/does-not-exist")
    assert r3.status_code == 404, r3.text
