"""A1 canonical contracts + Go<->Python wire contract (BI-PF-0393).

Verifies (acceptance):
  * every product contract validates against fixture ``sample-product/<contract>.json``;
  * the canonical projection is thin (drops unknown keys) and schema-stamped;
  * a missing required field is rejected (tests that can fail);
  * ``core.bom.contract_view`` emits a valid ``bom`` contract from existing code;
  * the Go host and the Python core exchange a valid payload (Go consumes Python's
    wire-request, Python validates Go's wire-response; required-field shapes match).
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core import bom, contracts  # noqa: E402
from core.paths import ROOT  # noqa: E402

FIX = Path(__file__).resolve().parent.parent / "fixtures" / "contracts"
_JSON = ".json"  # avoid embedding a store-like literal


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _fixture(folder, name):
    return FIX / folder / (name + _JSON)


# ── fixtures validate against the canonical contracts ────────────────────────────
def test_sample_product_fixtures_validate():
    d = FIX / "sample-product"
    files = sorted(d.glob("*" + _JSON))
    assert files, f"no fixtures under {d}"
    present = {p.stem for p in files}
    assert set(contracts.PRODUCT_CONTRACTS) <= present, present
    for p in files:
        res = contracts.validate(p.stem, _load(p))
        assert res["valid"], (p.stem, res["errors"])


def test_sample_wire_fixtures_validate():
    req = _load(_fixture("sample-wire", "wire-request"))
    resp = _load(_fixture("sample-wire", "wire-response"))
    assert contracts.validate("wire-request", req)["valid"]
    assert contracts.validate("wire-response", resp)["valid"]
    # the recorded response matches what the Python core actually emits
    live = contracts.handle_wire(req, host="python")
    assert contracts.validate("wire-response", live)["valid"]
    assert live["result"] == resp["result"]


# ── canonicalization + fail-closed validation ────────────────────────────────────
def test_canonical_is_thin_and_stamped():
    ps = _load(_fixture("sample-product", "product-spec"))
    ps["unknown_key"] = "drop-me"
    c = contracts.canonical("product-spec", ps)
    assert "unknown_key" not in c
    assert c["schema"] == "product-forge/product-spec@1"
    assert contracts.validate("product-spec", c)["valid"]


def test_missing_required_is_rejected():
    ps = _load(_fixture("sample-product", "product-spec"))
    del ps["product_id"]
    assert contracts.validate("product-spec", ps)["valid"] is False


def test_unknown_contract_is_fail_closed():
    assert contracts.validate("not-a-contract", {})["valid"] is False
    resp = contracts.handle_wire(contracts.wire_request("validate", "not-a-contract", {}, id="x"))
    assert resp["ok"] is False and resp["status"] == "error"


def test_schema_export(tmp_path):
    paths = contracts.export_schemas(str(tmp_path))
    assert len(paths) == len(contracts.contract_names())
    for p in paths:
        assert _load(p)["type"] == "object"


# ── runtime wiring: existing code emits a canonical contract ─────────────────────
def test_bom_contract_view(tmp_path):
    proj = tmp_path / "proj"
    pkg = proj / "artifacts" / "9 - Package"
    pkg.mkdir(parents=True)
    (pkg / "app.py").write_text("print(1)\n", encoding="utf-8")
    view = bom.contract_view(str(proj))
    assert view["schema"] == "product-forge/bom@1"
    assert view["project"] == "proj"
    assert contracts.validate("bom", view)["valid"]


# ── Go host <-> Python core exchange ─────────────────────────────────────────────
def _go_bin():
    found = shutil.which("go")
    if found:
        return found
    local = os.path.join(os.environ.get("LOCALAPPDATA", ""), "go", "bin",
                         "go" + (".exe" if os.name == "nt" else ""))
    return local if os.path.exists(local) else None


def _go_call(host, req):
    r = subprocess.run([str(host)], input=json.dumps(req), capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.mark.skipif(_go_bin() is None, reason="go toolchain not installed")
def test_go_host_and_python_core_exchange(tmp_path):
    go = _go_bin()
    go_dir = ROOT / "go" / "contract"
    host = tmp_path / ("contract-host" + (".exe" if os.name == "nt" else ""))
    build = subprocess.run([go, "build", "-o", str(host), "."], cwd=str(go_dir),
                           capture_output=True, text=True, timeout=300)
    assert build.returncode == 0, build.stderr

    # Python core emits a request -> Go host consumes it -> Go emits a response Python validates.
    payload = _load(_fixture("sample-product", "product-spec"))
    req = contracts.wire_request("validate", "product-spec", payload, id="e2e-1", source="python")
    go_resp = _go_call(host, req)
    assert contracts.validate("wire-response", go_resp)["valid"]
    assert go_resp["host"] == "go" and go_resp["ok"] is True
    py_resp = contracts.handle_wire(req, host="python")
    assert go_resp["result"]["valid"] == py_resp["result"]["valid"] is True

    # a bad payload is rejected identically (valid=False on both sides).
    bad = dict(payload)
    bad.pop("product_id", None)
    bad_req = contracts.wire_request("validate", "product-spec", bad, id="e2e-2")
    assert _go_call(host, bad_req)["result"]["valid"] is False
    assert contracts.handle_wire(bad_req)["result"]["valid"] is False

    # shape parity: Go's required fields mirror the Python source of truth for every contract.
    for name in contracts.contract_names():
        desc = _go_call(host, contracts.wire_request("describe", name, id="d-" + name))
        assert contracts.validate("wire-response", desc)["valid"], name
        assert set(desc["result"]["required"]) == set(contracts.required_fields(name)), name

    ping = _go_call(host, contracts.wire_request("ping", id="p-1"))
    assert ping["result"]["version"] == contracts.WIRE_VERSION
    assert ping["result"]["host"] == "go"
