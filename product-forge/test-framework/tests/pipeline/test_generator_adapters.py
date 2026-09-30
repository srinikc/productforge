"""BI-0188: generator-model adapters (catalog, license gating, fail-closed, modality union)."""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import generator_adapters as ga  # noqa: E402
from core import modality as md  # noqa: E402


def test_catalog_has_license_and_open_weights():
    gens = ga.list_generators()
    assert gens, "generator catalog empty"
    for g in gens:
        assert "license" in g and g["license"], g["id"]
        assert "open_weights" in g and "free" in g and "requires_key" in g
        assert g.get("provider_kind") in ("direct", "aggregator", "self-host")


def test_selfhost_selectable_without_key_and_paid_fail_closed():
    # self-host (requires_key=False) is always eligible even with no credentials
    img = ga.eligible("image-gen")
    assert any(g["provider"] == "self-host" for g in img)
    # selection prefers key-less self-host
    assert ga.select("image-gen")["provider"] == "self-host"
    # a kind with only paid providers and no keys => no eligible => fail-closed
    # (tts has a self-host kokoro, so build an explicitly impossible kind)
    assert ga.select("nonexistent-kind") is None
    assert ga.generate("nonexistent-kind", {"prompt": "x"})["error"] == "no_generator_available"


def test_modality_union_makes_generators_needed_zero():
    # once a generator registers an output modality, models_for_output is non-empty
    assert ga.models_for_output("video")
    assert "video" not in md.generators_needed(["video"])
    assert "3d" not in md.generators_needed(["3d"])


def test_generate_persists_job_and_is_not_fabricated():
    from core.paths import ROOT
    d = str(Path(ROOT) / "products" / "_test_bi_0188")
    try:
        res = ga.generate("image-gen", {"prompt": "a cat"}, d)
        assert res["ok"] is True
        job = res["job"]
        assert "job_id" in job and job["state"] in ("succeeded", "running")
        # transport not configured => no fabricated artifact
        assert job.get("artifact_ref", "") == ""
        # persisted in the project job store
        st = ga.status(d, job["job_id"])
        assert st and st["job_id"] == job["job_id"]
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_cost_uses_billing_unit():
    c = ga.cost("openai-images", units=3)
    assert c["billing_unit"] == "image" and c["usd"] == round(0.04 * 3, 6)
