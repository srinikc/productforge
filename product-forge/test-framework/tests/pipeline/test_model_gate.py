"""BI-PF-0246: unknown-capability fail-closed rule in the model capability gate."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import model_gate as g  # noqa: E402

_PROFILE = {"default_tier": "t", "agents": {"architect": {"model": "no-such-model-zzz"}}}


def _entry(rep, agent):
    return next((e for e in rep["entries"] if e["agent"] == agent), None)


def test_unknown_critical_is_rejected_by_default():
    os.environ.pop("MODEL_GATE_REJECT_UNKNOWN", None)
    rep = g.evaluate(_PROFILE)
    e = _entry(rep, "architect")
    if e and e["status"] == "UNKNOWN":
        assert "architect" in rep["summary"]["rejected_unknown"]
        assert "architect" in rep["summary"]["blocked_agents"]


def test_unknown_critical_can_be_disabled():
    os.environ["MODEL_GATE_REJECT_UNKNOWN"] = "0"
    try:
        rep = g.evaluate(_PROFILE)
        assert rep["summary"]["rejected_unknown"] == []
    finally:
        os.environ.pop("MODEL_GATE_REJECT_UNKNOWN", None)
