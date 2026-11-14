"""A1 canonical contracts + Go<->Python wire contract (BI-PF-0393).

Verifies (acceptance):
  * every product contract validates against fixture ``sample-product/<contract>.json``;
  * the canonical projection is thin (drops unknown keys) and schema-stamped;
  * a missing required field is rejected (tests that can fail);
  * ``core.bom.contract_view`` emits a valid ``bom`` contract from existing code;
  * the Go host and the Python core exchange a valid payload (Go consumes Python's
    wire-request, Python validates Go's wire-response; required-field shapes match).
"""
import hashlib
import hmac
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


# ── eventing SSOT contracts (BI-PF-1267; ADR-0005) ───────────────────────────────
def test_eventing_contracts_present_and_validate():
    for name in contracts.EVENTING_CONTRACTS:
        assert name in contracts.CONTRACTS
    env = {"schema": "product-forge/event-envelope@1", "event_id": "e1",
           "event_type": "run_started", "event_version": "1",
           "occurred_at": "2026-01-01T00:00:00", "seq": 1}
    assert contracts.validate("event-envelope", env)["valid"]
    assert contracts.validate("subscription", {"schema": "product-forge/subscription@1",
                                               "id": "s1", "tenant_id": "t1",
                                               "transport": "webhook", "auth_ref": "secret:1"})["valid"]
    assert contracts.validate("alert-rule", {"schema": "product-forge/alert-rule@1",
                                             "tenant_id": "t1", "event_type": "run_failed",
                                             "channels": ["email"]})["valid"]
    assert contracts.validate("webhook-delivery", {"schema": "product-forge/webhook-delivery@1",
                                                   "delivery_id": "d1", "event_id": "e1",
                                                   "subscription_id": "s1",
                                                   "target_url": "https://example.test/hook"})["valid"]
    # fail-closed: a missing required field is rejected
    assert contracts.validate("subscription", {"schema": "product-forge/subscription@1"})["valid"] is False


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

# BI-PF-1267 strict eventing contracts
def test_eventing_unknown_top_level_field_is_rejected():
    env = {"schema": "product-forge/event-envelope@1", "event_id": "e1",
           "event_type": "run_started", "event_version": "1",
           "occurred_at": "2026-01-01T00:00:00", "seq": 1, "unexpected": "x"}
    assert contracts.validate("event-envelope", env)["valid"] is False


def test_eventing_extensions_are_allowed():
    env = {"schema": "product-forge/event-envelope@1", "event_id": "e1",
           "event_type": "run_started", "event_version": "1",
           "occurred_at": "2026-01-01T00:00:00", "seq": 1,
           "extensions": {"vendor": {"trace": "x"}}}
    assert contracts.validate("event-envelope", env)["valid"] is True


def test_eventing_seq_is_required():
    env = {"schema": "product-forge/event-envelope@1", "event_id": "e1",
           "event_type": "run_started", "event_version": "1",
           "occurred_at": "2026-01-01T00:00:00"}
    assert contracts.validate("event-envelope", env)["valid"] is False


def test_webhook_hmac_is_constant_time_and_fail_closed():
    body = b'{"event_id":"e1"}'
    sig = contracts.webhook_signature(body, "secret")
    assert contracts.verify_webhook_signature(body, sig, "secret") is True
    assert contracts.verify_webhook_signature(body, sig, "wrong") is False
    assert contracts.verify_webhook_signature(body, "", "secret") is False


def test_eventing_header_contract_names():
    assert contracts.WEBHOOK_SIGNATURE_HEADER == "X-PF-Signature"
    assert contracts.WEBHOOK_IDEMPOTENCY_HEADER == "X-PF-Idempotency-Key"


def test_eventing_tenant_and_idempotency_contract():
    assert contracts.validate("subscription", {"schema": "product-forge/subscription@1",
                                               "id": "s1", "transport": "webhook"})["valid"] is False
    body = b'{"event_id":"e1"}'
    sig = contracts.webhook_signature(body, "secret")
    assert contracts.verify_webhook_signature(body, sig, "secret") is True
    assert contracts.webhook_signature(body, "") == ""
    headers = contracts.webhook_headers("e1", body, "secret")
    assert headers[contracts.WEBHOOK_IDEMPOTENCY_HEADER] == "e1"
    assert headers[contracts.WEBHOOK_SIGNATURE_HEADER] == sig


@pytest.mark.skipif(_go_bin() is None, reason="go toolchain not installed")
def test_pfcore_eventing_field_parity(tmp_path):
    go = _go_bin()
    go_dir = ROOT / "go" / "pfcore"
    host = tmp_path / ("pfcore-host" + (".exe" if os.name == "nt" else ""))
    build = subprocess.run([go, "build", "-o", str(host), "."], cwd=str(go_dir),
                           capture_output=True, text=True, timeout=300)
    assert build.returncode == 0, build.stderr
    for name in contracts.EVENTING_CONTRACTS:
        desc = _go_call(host, contracts.wire_request("describe", name, id="d-" + name))
        assert set(desc["result"]["fields"]) == set(contracts.CONTRACTS[name].field_names()), name
        assert set(desc["result"]["required"]) == set(contracts.required_fields(name)), name


def test_metric_and_empty_secret_contract():
    assert contracts.CONTRACT_METRICS["validation_failures"] == "contract_validation_failures_total"
    assert contracts.CONTRACT_METRIC_LABELS["validation_failures"] == ("code",)
    assert contracts.webhook_signature(b"x", "") == ""
    empty_key_sig = "sha256=" + hmac.new(b"", b"x", hashlib.sha256).hexdigest()
    assert contracts.verify_webhook_signature(b"x", empty_key_sig, "") is False


def test_eventing_cross_language_unknown_field_and_version():
    assert contracts.validate("subscription", {"schema": "product-forge/subscription@1", "id": "s1", "tenant_id": "t", "transport": "webhook", "auth_ref": "x", "unexpected": 1})["valid"] is False
    assert contracts.validate("alert-rule", {"schema": "product-forge/alert-rule@1", "tenant_id": "t", "event_type": "run_failed", "channels": ["email"], "unexpected": 1})["valid"] is False
    assert contracts.validate("webhook-delivery", {"schema": "product-forge/webhook-delivery@1", "delivery_id": "d", "event_id": "e", "subscription_id": "s", "target_url": "https://example.test", "unexpected": 1})["valid"] is False
    assert contracts.validate("event-envelope", {"schema": "product-forge/event-envelope@1", "event_id": "e", "event_type": "x", "event_version": "2", "occurred_at": "2026-01-01", "seq": 1})["valid"] is False
    assert contracts.validate("event-envelope", {"schema": "product-forge/event-envelope@1", "event_id": "e", "event_type": "x", "event_version": "1", "occurred_at": "2026-01-01", "seq": "1"})["valid"] is False


def test_event_cursor_ordering():
    rows = [{"seq": 3}, {"seq": 1}, {"seq": 2}]
    assert [r["seq"] for r in contracts.events_after_cursor(rows, 1)] == [2, 3]
