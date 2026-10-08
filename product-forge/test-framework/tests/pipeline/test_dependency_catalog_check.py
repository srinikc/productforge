"""BI-PF-0443: dependency-catalog completeness hook - parsing, aliases, missing detection."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from core import tool_catalog  # noqa: E402
from scripts.dev import dependency_catalog_check as d  # noqa: E402


def test_parse_manifests():
    assert "fastapi" in d.parse_toml_deps('[project]\ndependencies = [\n"fastapi>=0.104.0",\n]')
    assert d.parse_go_mod("require (\n\tgithub.com/jackc/pgx/v5 v5.11.0\n\tgithub.com/x/y v1 // indirect\n)") \
        == {"github.com/jackc/pgx/v5"}
    assert d.parse_package_json('{"dependencies": {"@opencode-ai/plugin": "1"}}') == {"@opencode-ai/plugin"}
    assert "requests" in d.parse_requirements("requests>=2.0\n# comment\n-r other.txt\n")


def test_catalog_alias_and_missing_detection():
    assert tool_catalog.lookup("github.com/jackc/pgx/v5") is not None   # via manifest_names
    assert tool_catalog.lookup("fastapi") is not None
    assert d.missing_from_catalog(["fastapi", "totally-unlisted-lib-xyz"]) == ["totally-unlisted-lib-xyz"]
