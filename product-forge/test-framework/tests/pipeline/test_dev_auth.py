"""BI-PF-1256: local dev auth - shared dev token (dev-only, fail-closed in prod)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from api import auth  # noqa: E402


def test_is_dev_gate(monkeypatch):
    monkeypatch.delenv("PF_DEV", raising=False)
    assert auth.is_dev() is False
    monkeypatch.setenv("PF_DEV", "1")
    assert auth.is_dev() is True


def test_ensure_dev_token_stable(monkeypatch, tmp_path):
    monkeypatch.setattr(auth, "TOKEN_PATH", str(tmp_path / "dev-api-token"))
    assert auth.dev_token() == ""
    t1 = auth.ensure_dev_token()
    assert t1 and auth.dev_token() == t1
    assert auth.ensure_dev_token() == t1  # stable across calls


def test_api_auth_uses_dev_token(monkeypatch, tmp_path):
    monkeypatch.setattr(auth, "TOKEN_PATH", str(tmp_path / "dev-api-token"))
    monkeypatch.setenv("PF_DEV", "1")
    for k in ("API_TOKEN", "DASHBOARD_API_TOKEN", "API_ALLOW_ANON"):
        monkeypatch.delenv(k, raising=False)
    tok = auth._token()
    assert tok and tok == auth.ensure_dev_token()


def test_api_auth_fail_closed_without_dev(monkeypatch, tmp_path):
    monkeypatch.setattr(auth, "TOKEN_PATH", str(tmp_path / "dev-api-token"))
    monkeypatch.delenv("PF_DEV", raising=False)
    for k in ("API_TOKEN", "DASHBOARD_API_TOKEN", "API_ALLOW_ANON"):
        monkeypatch.delenv(k, raising=False)
    assert auth._token() == ""  # no file fallback outside dev -> fail-closed
