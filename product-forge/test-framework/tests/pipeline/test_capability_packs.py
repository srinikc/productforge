"""BI-0189: capability-pack registry + discovery->enablement profile (fail-closed)."""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import capability_packs as cp  # noqa: E402


def test_catalog_and_defaults():
    keys = [p["key"] for p in cp.list_packs()]
    assert "image" in keys and "video" in keys
    assert cp.view("image")["modality"] == "image"
    assert "image" in cp.defaults()


def test_resolve_maps_required_and_is_fail_closed():
    r = cp.resolve(["image", "video"])
    assert {e["key"] for e in r["enabled"]} == {"image", "video"}
    assert r["warnings"] == []

    # unknown capability => warning, nothing enabled
    bad = cp.resolve(["nope"])
    assert bad["enabled"] == [] and any("unknown" in w for w in bad["warnings"])

    # dependency missing (sensor requires iot-pack) => fail-closed
    dep = cp.resolve(["sensor"])
    assert dep["enabled"] == [] and any("requires" in w for w in dep["warnings"])


def test_required_from_idea_and_profile_roundtrip():
    req = cp.required_from_idea("an app that generates images and video clips")
    assert "image" in req and "video" in req and "text" not in req

    d = Path(cp.os.path.join(str(cp._ROOT), "products", "_test_bi_0189"))
    try:
        prof = cp.persist_required(str(d), "make an image")
        assert "image" in prof["required_capabilities"]
        assert "image" in prof["enabled_packs"]
        assert cp.load_profile(str(d))["enabled_packs"] == prof["enabled_packs"]
        assert [p["key"] for p in cp.active_packs(str(d))] == ["image"]
    finally:
        shutil.rmtree(d, ignore_errors=True)
