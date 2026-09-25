"""
Tests for the E2E progress banner (core/progress.py) — BI-0027.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import progress as P  # noqa: E402


def _mk(tmp, name, state, live):
    d = Path(tmp) / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "pipeline-state.json").write_text(json.dumps(state), encoding="utf-8")
    (d / "agents-live.json").write_text(json.dumps(live), encoding="utf-8")
    (d / "budget.json").write_text(json.dumps({"state": {"total_used": 100, "total_max": 1000}}), encoding="utf-8")
    (d / "project.json").write_text(json.dumps({"name": name, "deploy": {"target": "docker"}}), encoding="utf-8")
    return str(d)


def test_snapshot_running_agent_first_stage(temp_products_dir):
    d = _mk(temp_products_dir, "prod-a", {"project": "prod-a", "stages": {}},
            {"0:ideation": {"agent_id": "ideation", "stage": "0", "status": "running"}})
    s = P.snapshot(d)
    assert s["stage_id"] == "0"
    assert s["agent"] == "ideation"
    assert s["status"] == "running"
    assert s["phase"].endswith("Ideation")
    assert s["stage_index"] == 1
    assert s["stage_total"] == len(P.ORDER)
    assert "discovery" in s["next"]
    assert s["target"] == "docker"


def test_snapshot_advances_to_next_incomplete_stage(temp_products_dir):
    d = _mk(temp_products_dir, "prod-b",
            {"project": "prod-b", "stages": {"0": {"status": "completed"},
                                             "0a": {"status": "completed"},
                                             "1": {"status": "pending"}}},
            {})
    s = P.snapshot(d)
    assert s["stage_id"] == "1"
    assert s["status"] == "pending"
    assert s["stage_name"] == "Design"
    assert "1a" in s["next"] or "Design" in s["next"]


def test_snapshot_complete(temp_products_dir):
    d = _mk(temp_products_dir, "prod-c",
            {"project": "prod-c", "stages": {sid: {"status": "completed"} for sid in P.ORDER},
             "completed_stages": list(P.ORDER)}, {})
    s = P.snapshot(d)
    assert s["status"] in ("completed", "skipped")
    assert s["next"] == "pipeline complete"


def test_render_contains_position_lines(temp_products_dir):
    d = _mk(temp_products_dir, "prod-d", {"project": "prod-d", "stages": {}},
            {"0a:discovery": {"agent_id": "discovery", "stage": "0a", "status": "running"}})
    txt = P.render(P.snapshot(d))
    assert "PIPELINE PROGRESS" in txt
    assert "Stage 2/" in txt
    assert "0a Discovery" in txt
    assert "Next:" in txt


def test_agent_banner_uses_event_label(temp_products_dir):
    d = _mk(temp_products_dir, "prod-e", {"project": "prod-e", "stages": {}}, {})
    assert "AGENT START" in P.agent_banner(d, "0", "ideation", "running")
    assert "AGENT END" in P.agent_banner(d, "0", "ideation", "completed")
