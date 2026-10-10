"""B1 (BI-PF-0394) gate: the PF native Go core is built and invokable from the PF runtime.

Acceptance criteria (from the backlog item):
  1. ``go build`` succeeds (the pfcore host compiles).
  2. A new feature implemented in Go is invoked from the PF runtime
     (``core.go_host.invoke`` exchanges a valid A1 wire payload with the Go host).

Fail-closed checks included: unknown op / missing required fields / unknown contract must be
rejected by the Go host even when invoked from the PF runtime.
"""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
os.environ.setdefault("PF_OFFLINE", "1")

import pytest  # noqa: E402

from core import go_host  # noqa: E402

# B1 native Go core is optional in an environment without the Go toolchain (skip, don't fail).
pytestmark = pytest.mark.skipif(
    shutil.which("go") is None,
    reason="Go toolchain not on PATH (B1 native core optional in this environment)")


def test_pfcore_binary_builds():
    b = go_host.build()
    assert b.get("ok") is True, b
    assert os.path.isfile(go_host.binary_path()), b


def test_ping_invoked_from_pf_runtime():
    r = go_host.invoke("ping")
    assert r.get("ok") is True, r
    assert r.get("schema") == "product-forge/wire-response@1"
    assert r.get("host") == "go"                      # contract enum (no widening)
    assert (r.get("result") or {}).get("host_id") == "go-pfcore"
    assert (r.get("result") or {}).get("go_version")
    assert (r.get("result") or {}).get("capabilities")


def test_validate_fail_closed_from_pf_runtime():
    good = {"schema": "product-forge/product-spec@1", "product_id": "p1", "name": "Demo"}
    bad = {"name": "Demo"}
    r1 = go_host.invoke("validate", "product-spec", good)
    assert r1.get("ok") is True and (r1.get("result") or {}).get("valid") is True, r1
    r2 = go_host.invoke("validate", "product-spec", bad)
    assert r2.get("ok") is True and (r2.get("result") or {}).get("valid") is False, r2
    r3 = go_host.invoke("validate", "no-such-contract", good)
    assert r3.get("ok") is False and "unknown contract" in (r3.get("error") or ""), r3
    r4 = go_host.invoke("no-such-op")
    assert r4.get("ok") is False and "unsupported op" in (r4.get("error") or ""), r4


def test_status_probe():
    s = go_host.status()
    assert s.get("ok") is True and s.get("binary_present") is True, s
    assert s.get("host") == "go" and s.get("contracts"), s
