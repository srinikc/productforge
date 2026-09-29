"""Section D P3-P6 (BI-PF-0244): status rebuild, SLIs, OTel export, JSONL retention."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import events, run_status, sli, otel, log_router as lr  # noqa: E402


def test_rebuild_status_from_stream(tmp_path):
    events.emit(str(tmp_path), "run_started", run_id="r1")
    events.emit(str(tmp_path), "stage_started", run_id="r1", stage="1")
    events.emit(str(tmp_path), "run_failed", run_id="r1")
    d = run_status.rebuild(str(tmp_path))
    assert d["state"] == "failed" and d["stages"].get("1") == "interrupted"


def test_sli_counts(tmp_path):
    events.emit(str(tmp_path), "run_started", run_id="r1")
    events.emit(str(tmp_path), "run_completed", run_id="r1")
    s = sli.summary(str(tmp_path))
    assert s["runs_completed"] == 1 and s["success_rate"] == 1.0


def test_otel_flag_gated(tmp_path, monkeypatch):
    monkeypatch.delenv("PIPELINE_OTEL", raising=False)
    assert otel.export(str(tmp_path)) == ""
    monkeypatch.setenv("PIPELINE_OTEL", "1")
    events.emit(str(tmp_path), "run_started", run_id="r1")
    p = otel.export(str(tmp_path))
    assert p.endswith("otel-spans.jsonl") and os.path.exists(p)


def test_trim_jsonl(tmp_path):
    p = tmp_path / "events.jsonl"
    p.write_text("\n".join(str(i) for i in range(100)) + "\n", encoding="utf-8")
    removed = lr.trim_jsonl(str(p), max_lines=10)
    assert removed == 90 and len(p.read_text(encoding="utf-8").splitlines()) == 10
