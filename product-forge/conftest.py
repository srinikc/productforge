"""Repo-wide offline default for backlog tests."""
import os

os.environ.setdefault("PF_BACKLOG_DB", "off")
