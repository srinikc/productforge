"""Protect every test from ambient Git repository selectors."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.dev.git_env import sanitize_process_env  # noqa: E402


@pytest.fixture(autouse=True)
def _sanitize_ambient_git_env(monkeypatch):
    sanitize_process_env()
    # Unit tests are offline by default; DB authority tests opt in explicitly.
    monkeypatch.setenv("PF_BACKLOG_DB", "off")
