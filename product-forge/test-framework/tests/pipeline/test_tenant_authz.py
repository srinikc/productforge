"""PF-022 tenant-scoped authz: fail-closed cross-tenant decision."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import tenancy  # noqa: E402


def test_platform_admin_any_tenant():
    assert tenancy.cross_tenant_allowed("operator", "", "acme", True) is True
    assert tenancy.cross_tenant_allowed("tenant", "acme", "other", True) is True


def test_tenant_only_own_bound_tenant():
    assert tenancy.cross_tenant_allowed("tenant", "acme", "acme", False) is True
    assert tenancy.cross_tenant_allowed("tenant", "acme", "other", False) is False


def test_unbound_tenant_instance_denied():
    assert tenancy.cross_tenant_allowed("tenant", "", "acme", False) is False
    assert tenancy.cross_tenant_allowed("tenant", "acme", "", False) is False


def test_operator_without_platform_admin_denied():
    assert tenancy.cross_tenant_allowed("operator", "", "acme", False) is False
