"""Backlog view: epic-wise classification (epic fields per row + 'By epic' summary + Epic column)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
os.environ.setdefault("PF_OFFLINE", "1")

from core import views  # noqa: E402


def test_rows_have_epic_fields():
    rows = views._all_backlog_items()
    assert rows
    assert all("epic" in r and "epic_title" in r for r in rows)


def test_html_has_epic_section_and_column():
    h = views.render_backlog_html()
    assert "By epic" in h
    assert "<th>Epic</th>" in h
