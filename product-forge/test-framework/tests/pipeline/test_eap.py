"""A4 (BI-PF-0397): EAP (Edition/Artifact Package) delivery/build manifest - build, validate, compatibility.

The EAP is the authoritative BUILD-TIME manifest of what goes into an edition's package (it composes the
canonical contracts + entitlement + SBOM + versioning/compatibility). It is not shipped to customers.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from core import packaging as P  # noqa: E402


def test_eap_build_composes_contracts_and_edition():
    e = P.eap_build("product_forge", "", "enterprise")
    assert e["schema"] == P.EAP_SCHEMA and e["eap_version"] == P.EAP_VERSION
    assert e["edition"] == "enterprise" and e["tier"] == "enterprise"
    assert e["deploy_target"] == "kubernetes"
    assert set(P.EAP_CONTRACTS) <= set(e["contracts"])
    assert (e["entitlement"] or {}).get("tier") == "enterprise"


def test_eap_validate_ok_and_fail_closed():
    v = P.eap_validate(P.eap_build("product_forge", "", "community"))
    assert v["valid"], v
    bad = dict(P.eap_build("product_forge", "", "community"), eap_version="9.9")  # unknown version
    bv = P.eap_validate(bad)
    assert not bv["valid"] and "eap_version:unknown" in bv["unmet"]
    assert not P.eap_validate({})["valid"]           # empty -> fail-closed
    assert not P.eap_validate({"schema": P.EAP_SCHEMA})["valid"]


def test_eap_compatibility():
    e = P.eap_build("product_forge", "", "community")
    assert P.eap_compatible(e)["compatible"] is True
    assert P.eap_compatible(dict(e, compatible_with=["0.x"]))["compatible"] is False
    assert P.eap_compatible(e, target_version="1.0")["compatible"] is True


def test_sample_eap_fixture_validates():
    fx = ROOT / "test-framework" / "tests" / "fixtures" / "contracts" / "sample-product" / "sample.eap"
    eap = json.load(open(fx, encoding="utf-8"))
    assert eap["schema"] == P.EAP_SCHEMA
    assert P.eap_validate(eap)["valid"], P.eap_validate(eap)
    assert P.eap_compatible(eap)["compatible"] is True
