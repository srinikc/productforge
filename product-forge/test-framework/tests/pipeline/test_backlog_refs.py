"""Tests for scope-qualified backlog refs (BI-0082)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import core.backlog as backlog  # noqa: E402


def test_qualify_product_forge():
    assert backlog.qualify("product_forge", None, "BI-0042") == "product_forge:BI-0042"


def test_qualify_project():
    assert backlog.qualify("project", "ProductForge-Dashboard", "BI-0015") == \
        "project:ProductForge-Dashboard:BI-0015"


def test_parse_ref_roundtrip():
    assert backlog.parse_ref("product_forge:BI-0042") == ("product_forge", None, "BI-0042")
    assert backlog.parse_ref("project:ProductForge-Dashboard:BI-0015") == \
        ("project", "ProductForge-Dashboard", "BI-0015")


def test_parse_unqualified():
    scope, project, eid = backlog.parse_ref("BI-0042")
    assert scope == "" and eid == "BI-0042"


def test_get_by_ref_resolves_product_forge():
    item = backlog.get_by_ref("product_forge:BI-0042")
    assert item is None or item["id"] == "BI-0042"
