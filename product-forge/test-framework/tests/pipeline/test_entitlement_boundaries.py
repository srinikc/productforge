"""Test suite for BI-PF-1286: Entitlement enforcement across remaining execution boundaries.

Verifies fail-closed enforcement across:
1. Pipeline stage execution boundary
2. Capability bridge invocation boundary
3. REST API endpoint boundary
4. Declarative config-driven action->group mappings
"""
import os
import pytest

from core import licensing
from core import capability_bridge
from api import auth as api_auth
from api.errors import ApiError


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch):
    monkeypatch.delenv("PF_INSTANCE_TIER", raising=False)
    monkeypatch.delenv("PF_TENANT", raising=False)
    monkeypatch.setenv("INSTANCE_ROLE", "tenant")


def test_action_group_mapping_config():
    """AC-3: Per-action feature group mappings are loaded from config/licensing-tiers.json."""
    m = licensing.action_group_map()
    assert "stages" in m
    assert "capabilities" in m
    assert "api_routes" in m

    # Mapped groups
    assert licensing.action_group("stages", "11") == "content-media"
    assert licensing.action_group("stages", "2") == "build-products"
    assert licensing.action_group("capabilities", "build_video") == "content-media"
    assert licensing.action_group("capabilities", "research_domain") == "ideate-design"

    # Default fallback
    assert licensing.action_group("stages", "unknown-stage-99") == "build-products"
    assert licensing.action_group("capabilities", "unknown-cap") == "build-products"


def test_pipeline_stage_boundary_enforcement(monkeypatch):
    """AC-1 & AC-2: Pipeline stage boundary enforces mapped groups fail-closed."""
    # Trial tier does NOT entitle content-media (stage 11)
    monkeypatch.setenv("PF_INSTANCE_TIER", "trial")
    with pytest.raises(licensing.LicenseError) as exc:
        licensing.enforce_stage("11")
    assert "not entitled to content-media" in str(exc.value)

    # Trial tier DOES entitle build-products (stage 2) and ideate-design (stage 0c)
    licensing.enforce_stage("2")
    licensing.enforce_stage("0c")

    # Pro tier entitles content-media (stage 11)
    monkeypatch.setenv("PF_INSTANCE_TIER", "pro")
    licensing.enforce_stage("11")


def test_capability_bridge_boundary_enforcement(monkeypatch, tmp_path):
    """AC-1 & AC-2: Capability bridge boundary enforces mapped groups fail-closed."""
    pdir = str(tmp_path)

    # Starter tier does NOT entitle content-media
    monkeypatch.setenv("PF_INSTANCE_TIER", "starter")
    with pytest.raises(licensing.LicenseError):
        capability_bridge.invoke_capability("build_video", pdir)

    # In stage hooks, entitlement failure is captured fail-closed in output
    hooks = capability_bridge.run_stage_hooks(pdir, "8")  # build_artifacts -> build-products
    assert "build_artifacts" in hooks
    assert "error" not in hooks.get("build_artifacts", {})

    # Pro tier entitles content-media (build_video/build_deck)
    monkeypatch.setenv("PF_INSTANCE_TIER", "pro")
    res = capability_bridge.invoke_capability("build_video", pdir)
    assert isinstance(res, dict)
    assert "entitlement_refused" not in res.get("error", "")


def test_api_route_guard_enforcement(monkeypatch):
    """AC-1 & AC-2: API route guards enforce feature group entitlement with 403 ENTITLEMENT_REFUSED."""
    from unittest.mock import MagicMock
    from fastapi import Request

    monkeypatch.setenv("API_ALLOW_ANON", "1")
    guard = api_auth.require_feature_group("content-media")

    def _req(path: str = "/api/v1/content/generate"):
        req = MagicMock(spec=Request)
        req.url.path = path
        req.state.pf_ctx = {}
        return req

    # Starter tier lacks content-media -> raises 403 ENTITLEMENT_REFUSED
    monkeypatch.setenv("PF_INSTANCE_TIER", "starter")
    with pytest.raises(ApiError) as exc:
        guard(_req(), x_tenant_id="tenant-starter")
    assert exc.value.code == "ENTITLEMENT_REFUSED"
    assert exc.value.status == 403

    # Enterprise tier entitles content-media -> passes
    monkeypatch.setenv("PF_INSTANCE_TIER", "enterprise")
    ctx = guard(_req(), x_tenant_id="tenant-ent")
    assert ctx is not None

    # Operator role is exempt -> passes regardless of tier
    monkeypatch.setenv("PF_INSTANCE_TIER", "trial")
    ctx_op = guard(_req(), x_roles="operator")
    assert ctx_op is not None


def test_fail_closed_unknown_tier_and_tenant(monkeypatch):
    """AC-2: Unknown tier or unentitled tenant fails closed with zero bypass."""
    monkeypatch.setenv("PF_INSTANCE_TIER", "non_existent_tier")
    with pytest.raises(licensing.LicenseError):
        licensing.enforce_stage("2")

    with pytest.raises(licensing.LicenseError):
        licensing.enforce_capability("research_domain")
