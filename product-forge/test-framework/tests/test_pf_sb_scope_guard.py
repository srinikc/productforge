"""PF-SB candidate scope guard (BI-PF-1509)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

from pf_sb_scope_guard import disallowed_paths  # noqa: E402


def test_scope_guard_allows_new_declared_paths_and_rejects_stray_paths():
    baseline = {"go/edpsvc/main.go"}
    allow = {"go/edpsvc/main.go", "migrations/0018_backlog_reservation_counter.up.sql"}
    current = baseline | allow | {"core/backlog.py"}
    assert disallowed_paths(current, baseline, allow) == {"core/backlog.py"}


def test_scope_guard_baseline_is_not_a_candidate_change():
    baseline = {"go/edpsvc/main.go", "engineering/trails/baseline.txt"}
    assert disallowed_paths(baseline, baseline, set()) == set()
