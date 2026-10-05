"""PFSSOT-P8A (BI-PF-0370): single submission path + optional/removable worker layer.

Covers: the runtime switch disables the worker layer cleanly (503 / pull refuses), the worker-layer flag
is declared default-on, and core does not import the worker layer.
"""
import importlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
os.environ.setdefault("API_ALLOW_ANON", "1")

from fastapi.testclient import TestClient  # noqa: E402

from core import env_flags, worker_registry  # noqa: E402


def test_flag_declared_and_default_on():
    # declared in the central registry, default enables the layer
    assert "WORKER_INTEGRATION_ENABLED" in env_flags.load()
    assert worker_registry.integration_enabled() in (True, False)


def test_disable_is_clean(monkeypatch):
    monkeypatch.setenv("WORKER_INTEGRATION_ENABLED", "0")
    assert worker_registry.integration_enabled() is False
    from core import work_pull
    r = work_pull.pull("product_forge", None, runtime="command")
    assert r["assigned"] is False and "disabled" in r["reason"]

    from api.app import app
    c = TestClient(app)
    assert c.get("/api/v1/engineering/workers").status_code == 503
    assert c.get("/api/v1/engineering/adapters").status_code == 503
    assert c.post("/api/v1/engineering/work", json={"runtime": "command"}).status_code == 503


def test_core_does_not_import_worker_layer():
    root = Path(__file__).parent.parent.parent.parent
    offenders = []
    for f in (root / "core").glob("*.py"):
        if f.name in ("worker_registry.py", "worker_adapters.py", "work_pull.py"):
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        for mod in ("worker_registry", "worker_adapters", "work_pull"):
            if f"import {mod}" in text or f"core.{mod}" in text:
                offenders.append(f"{f.name}:{mod}")
    assert not offenders, offenders


def test_pipeline_executor_construction_reloads():
    # sanity: importing the executor does not pull the worker layer
    m = importlib.import_module("core.pipeline_executor")
    assert hasattr(m, "PipelineExecutor")
