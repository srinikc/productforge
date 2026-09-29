"""Section D P2 (BI-PF-0244): canonical levels + secret redaction on log/event writes."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import log_router as lr  # noqa: E402
from core import events  # noqa: E402


def test_redact_secret_keys_and_values():
    d = lr.redact({"api_key": "abc", "authorization": "Bearer x",
                   "nested": {"password": "p"}, "note": "key sk-abcdefghijklmnop"})
    assert d["api_key"] == "***REDACTED***" and d["authorization"] == "***REDACTED***"
    assert d["nested"]["password"] == "***REDACTED***"
    assert "sk-abcdefghijklmnop" not in d["note"] and "REDACTED" in d["note"]


def test_events_carry_level(tmp_path):
    ev = events.emit(str(tmp_path), "agent_completed", run_id="r", stage="1", agent="design")
    assert ev.get("level") == "INFO"


def test_log_line_redacts(tmp_path):
    p = str(tmp_path / "agent.log")
    lr.log_event(p, event="e", message="leak token sk-abcdefghijklmnop now")
    assert "sk-abcdefghijklmnop" not in open(p, encoding="utf-8").read()
