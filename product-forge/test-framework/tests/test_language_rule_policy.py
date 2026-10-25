"""Language-rule policy merge: edit_growth.allow must load (BI-PF-1482)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core import change_policy as cp  # noqa: E402


def test_edit_growth_allow_is_loaded_and_applied():
    pol = cp.policy(force_reload=True)
    assert "core/execution_trail.py" in (pol.get("edit_growth") or {}).get("allow", [])
    growth = {"core/execution_trail.py": {"added": 116, "removed": 23, "new_defs": 6, "new_branches": 14}}
    assert cp.edit_growth_findings(["core/execution_trail.py"], [], growth, pol) == []
