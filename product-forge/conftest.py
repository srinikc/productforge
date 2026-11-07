"""Repo-wide offline default for backlog tests."""
import os

if os.environ.get("PF_TEST_DB_MODE") != "1":
    os.environ["PF_BACKLOG_DB"] = "off"
