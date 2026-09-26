"""BI-0216: product one-stop page read model.

Proves the SAME read model serves a plain text product and a multi-modal one
(media/BOM sections empty vs present). Uses a scratch project under products/.
"""
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from core import product_page as pp  # noqa: E402
from core.paths import PRODUCTS_DIR  # noqa: E402

PROJ = "_test_product_page"


@pytest.fixture()
def scratch():
    d = PRODUCTS_DIR / PROJ
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_text_only_project_has_empty_media_sections(scratch):
    (scratch / "pipeline-state.json").write_text(
        json.dumps({"stages": {"0": {"status": "completed"}, "1": {"status": "completed"}}}),
        encoding="utf-8")
    (scratch / "budget.json").write_text(
        json.dumps({"state": {"total_used": 100, "total_max": 1000}}), encoding="utf-8")
    sd = scratch / "artifacts" / "1 - Design"
    sd.mkdir(parents=True)
    (sd / "design-output.md").write_text("# design", encoding="utf-8")
    (scratch / "quality-gate.json").write_text(
        json.dumps({"passed": False, "checks": [], "reasons": ["compileall"]}), encoding="utf-8")

    assert pp.lifecycle(PROJ) == "designing"
    page = pp.page(PROJ)
    for k in ("identity", "lifecycle", "progress", "features", "artifacts",
              "quality", "cost", "bom", "releases", "activity"):
        assert k in page
    assert page["bom"]["available"] is False          # text-only: no BOM/media
    assert page["artifacts"]["count"] >= 1
    assert page["cost"]["total_used"] == 100
    assert page["quality"]["passed"] is False


def test_media_project_exposes_bom_and_built_lifecycle(scratch):
    (scratch / "quality-gate.json").write_text(
        json.dumps({"passed": True, "checks": [{"name": "compileall", "passed": True}], "reasons": []}),
        encoding="utf-8")
    b = scratch / "artifacts" / "9 - Package"
    b.mkdir(parents=True)
    (b / "BOM.json").write_text(json.dumps({"components": [
        {"name": "FLUX.1-schnell", "size_mb": 6000, "license": "Apache-2.0"}]}), encoding="utf-8")

    assert pp.lifecycle(PROJ) == "built"
    bom = pp.bom(PROJ)
    assert bom["available"] is True
    assert bom["bom"]["components"][0]["license"] == "Apache-2.0"


def test_registry_identity_and_links(scratch):
    (scratch / "product.json").write_text(json.dumps({
        "name": "Helios Reels", "owner": "A. Rao", "lifecycle": "live",
        "links": {"launch": "https://app.example.com"}}), encoding="utf-8")
    ident = pp.identity(PROJ)
    assert ident["name"] == "Helios Reels"
    assert ident["lifecycle"] == "live"
    assert ident["links"]["launch"] == "https://app.example.com"
