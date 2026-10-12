"""BI-PF-1261: shared assignment-lease authority (offline path + helpers)."""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import job_manager  # noqa: E402


def test_lease_acquire_local_when_disabled(monkeypatch):
    monkeypatch.setenv("PF_LEASE_REMOTE", "off")
    r = job_manager.lease_acquire("product_forge", None, "BI-PF-0001", "w1", "L1", 60)
    assert r["ok"] is True and r["authority"] == "local"


def test_lease_strict_fails_closed_when_no_authority(monkeypatch):
    from core import id_allocator
    monkeypatch.setenv("PF_LEASE_REMOTE", "strict")
    monkeypatch.setattr(id_allocator, "_repo_root", lambda: "")  # no shared authority
    r = job_manager.lease_acquire("product_forge", None, "BI-PF-0001", "w1", "L1", 60)
    assert r["ok"] is False


def test_lease_soft_allows_when_no_authority(monkeypatch):
    from core import id_allocator
    monkeypatch.setenv("PF_LEASE_REMOTE", "on")
    monkeypatch.setattr(id_allocator, "_repo_root", lambda: "")
    r = job_manager.lease_acquire("product_forge", None, "BI-PF-0001", "w1", "L1", 60)
    assert r["ok"] is True and r["authority"] == "local"


def test_lease_release_local_when_disabled(monkeypatch):
    monkeypatch.setenv("PF_LEASE_REMOTE", "off")
    assert job_manager.lease_release("product_forge", None, "BI-PF-0001", "w1") is True


def test_lease_holder_none_when_disabled(monkeypatch):
    monkeypatch.setenv("PF_LEASE_REMOTE", "off")
    assert job_manager.lease_holder("product_forge", None, "BI-PF-0001") is None


def test_lease_expired():
    assert job_manager._lease_expired({"expires_at": (datetime.now() - timedelta(seconds=5)).isoformat()}) is True
    assert job_manager._lease_expired({"expires_at": (datetime.now() + timedelta(seconds=5)).isoformat()}) is False
    assert job_manager._lease_expired({}) is True


def test_lease_key_shape():
    assert job_manager._lease_key("product_forge", None, "BI-PF-0001") == "product_forge::::BI-PF-0001"
