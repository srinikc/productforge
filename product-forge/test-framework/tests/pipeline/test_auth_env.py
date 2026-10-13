"""BI-PF-1325: PF_API_TOKEN is the canonical auth env; API_TOKEN is a deprecated alias; the legacy
DASHBOARD_API_TOKEN is removed. Verifies api.auth._token() resolution order."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from api import auth  # noqa: E402

_ENVS = ("PF_API_TOKEN", "API_TOKEN", "DASHBOARD_API_TOKEN", "PF_DEV")


def _clear(monkeypatch):
    for k in _ENVS:
        monkeypatch.delenv(k, raising=False)


def test_pf_api_token_is_canonical(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("PF_API_TOKEN", "pf-canon")
    monkeypatch.setenv("API_TOKEN", "old-alias")
    assert auth._token() == "pf-canon"          # canonical wins


def test_api_token_is_backcompat_alias(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("API_TOKEN", "old-alias")
    assert auth._token() == "old-alias"         # deprecated alias still works


def test_dashboard_api_token_is_gone(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("DASHBOARD_API_TOKEN", "legacy")
    assert auth._token() == ""                   # legacy alias removed -> ignored (no dev fallback)


def test_dev_fallback_when_unset(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("PF_DEV", "1")
    assert auth._token()                         # dev: falls back to the shared token file
