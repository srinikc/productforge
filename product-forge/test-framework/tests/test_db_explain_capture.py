import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("db_explain_capture", ROOT / "scripts/dev/db_explain_capture.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_production_sampling_cap():
    assert mod.validate("production", 0.05, 10, True) == ""
    assert "production" in mod.validate("production", 0.10, 10, True)


def test_rate_and_sample_bounds():
    assert mod.validate("dev", -0.1, 10)
    assert mod.validate("dev", 1.1, 10)
    assert mod.validate("dev", 0.1, 61)


def test_redaction_removes_literals_and_large_numbers():
    out = mod.redact("Filter: (tenant_id = 'customer-1') rows=12345")
    assert "customer-1" not in out
    assert "12345" not in out


def test_rate_cap_and_audit(tmp_path):
    from datetime import datetime, timezone
    state = tmp_path / "state.json"
    now = datetime.now(timezone.utc)
    assert mod.rate_ok(str(state), 1, now) is True
    assert mod.rate_ok(str(state), 1, now) is False
    audit = tmp_path / "audit.jsonl"
    mod.audit(str(audit), {"statement_label": "backlog_items", "decision": "captured"})
    text = audit.read_text(encoding="utf-8")
    assert "captured" in text and "statement_label" in text and "SELECT" not in text
