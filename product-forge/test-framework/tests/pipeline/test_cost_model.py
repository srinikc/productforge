"""BI-0194: per-unit cost model — media per-unit pricing; text path unchanged; strategy integration."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import cost_model as C  # noqa: E402


def test_schema_exposes_billing_units():
    s = C.schema()
    assert "image" in s["units"] and "second" in s["units"] and "mesh" in s["units"]
    assert s["formula"] == "cost = unit_price x units"
    assert isinstance(s["generators"], list)


def test_media_projection_reflects_per_unit_pricing():
    gens = C._generators()
    # pick a media generator with a positive unit price if any; else any media generator
    target = next((g for g, v in gens.items()
                   if v.get("billing_unit") in ("image", "second", "char", "track", "mesh")), None)
    assert target, "expected media generators"
    p = C.unit_price(target)
    assert p["billing_unit"] in ("image", "second", "char", "track", "mesh")
    proj = C.project("products/_t_cost", {target: 10})
    assert proj["has_media"] is True
    assert proj["media_cost"] == round(p["unit_price"] * 10, 6)
    assert proj["free_paid_mix"]["paid_units"] + proj["free_paid_mix"]["free_units"] == 10


def test_text_projection_unchanged_without_media():
    proj = C.project("products/_t_cost_text", {})
    assert proj["has_media"] is False
    assert proj["media_cost"] == 0.0
    assert proj["total_cost"] == proj["text_cost"]


def test_estimate_is_unit_price_times_units():
    e = C.estimate("nope-not-real", 5)
    assert e["cost"] == round(e["unit_price"] * 5, 6)


def test_strategy_assess_exposes_cost_projection(tmp_path):
    from core import model_strategy as M
    rep = M.assess(str(tmp_path), phase="b")
    assert "cost_projection" in rep
    assert "assignments" in rep
    for a in rep["assignments"]:
        assert "unit_price" in a and "projected_cost" in a
