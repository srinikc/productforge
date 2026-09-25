"""
Tests for the TTY-less prompt bridge (core/interactive.py) — BI-0026.

Guarantees covered:
  * bridge OFF + non-TTY  -> return default (terminal/headless behaviour unchanged)
  * bridge OFF + TTY      -> input()
  * bridge ON             -> a pending prompt is written; answering it resumes ``ask``
  * timeout               -> falls back to the default (never hangs)
"""
import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import core.interactive as I  # noqa: E402


def _force_non_tty(monkeypatch):
    monkeypatch.setattr(I, "_isatty", lambda: False)


def test_disabled_non_tty_returns_default(monkeypatch):
    monkeypatch.delenv("PIPELINE_INTERACTIVE", raising=False)
    _force_non_tty(monkeypatch)
    assert I.ask("q?", "DEF", project_dir="products/_nope") == "DEF"


def test_disabled_tty_uses_input(monkeypatch):
    monkeypatch.delenv("PIPELINE_INTERACTIVE", raising=False)
    monkeypatch.setattr(I, "_isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "typed")
    assert I.ask("q?", "DEF") == "typed"


def test_enabled_writes_prompt_and_answer_resumes(monkeypatch, temp_products_dir):
    monkeypatch.setenv("PIPELINE_INTERACTIVE", "1")
    _force_non_tty(monkeypatch)
    project_dir = str(Path(temp_products_dir) / "test-project")

    result = {}

    def _ask():
        result["v"] = I.ask("What to build?", "DEF", project_dir=project_dir, timeout=15)

    t = threading.Thread(target=_ask)
    t.start()

    pending = []
    for _ in range(50):
        pending = I.list_pending(project_dir, products_dir=str(temp_products_dir))
        if pending:
            break
        time.sleep(0.1)

    assert pending, "the bridge should have written a pending prompt"
    assert pending[0]["prompt"] == "What to build?"
    assert pending[0]["default"] == "DEF"

    I.answer(project_dir, "latest", "my idea", products_dir=str(temp_products_dir))
    t.join(timeout=5)
    assert result.get("v") == "my idea"


def test_enabled_timeout_falls_back_to_default(monkeypatch, temp_products_dir):
    monkeypatch.setenv("PIPELINE_INTERACTIVE", "1")
    _force_non_tty(monkeypatch)
    project_dir = str(Path(temp_products_dir) / "test-project")
    # sub-second timeout: unanswered prompt must not hang
    assert I.ask("q?", "DEF", project_dir=project_dir, timeout=0.2) == "DEF"
    assert I.list_pending(project_dir, products_dir=str(temp_products_dir)) == []


def test_stop_signal_aborts_wait(monkeypatch, temp_products_dir):
    """A cross-process stop must break the prompt wait immediately, not after the timeout."""
    monkeypatch.setenv("PIPELINE_INTERACTIVE", "1")
    _force_non_tty(monkeypatch)
    project_dir = str(Path(temp_products_dir) / "test-project")
    os.makedirs(project_dir, exist_ok=True)
    (Path(project_dir) / "control.json").write_text('{"action": "stop"}', encoding="utf-8")
    t0 = time.time()
    assert I.ask("q?", "DEF", project_dir=project_dir, timeout=30) == "DEF"
    assert time.time() - t0 < 6, "stop should abort the wait promptly"


def test_answer_unknown_id_returns_none(monkeypatch, temp_products_dir):
    monkeypatch.setenv("PIPELINE_INTERACTIVE", "1")
    project_dir = str(Path(temp_products_dir) / "test-project")
    assert I.answer(project_dir, "P999", "x", products_dir=str(temp_products_dir)) is None


def test_ids_are_sequential(monkeypatch, temp_products_dir):
    monkeypatch.setenv("PIPELINE_INTERACTIVE", "1")
    _force_non_tty(monkeypatch)
    project_dir = str(Path(temp_products_dir) / "test-project")
    for expected in ("P1", "P2"):
        t = threading.Thread(
            target=I.ask, args=("q", "D"),
            kwargs={"project_dir": project_dir, "timeout": 10},
        )
        t.start()
        pid = None
        for _ in range(50):
            pend = I.list_pending(project_dir, products_dir=str(temp_products_dir))
            if pend:
                pid = pend[-1]["id"]
                break
            time.sleep(0.1)
        assert pid == expected
        I.answer(project_dir, pid, "ok", products_dir=str(temp_products_dir))
        t.join(timeout=5)
