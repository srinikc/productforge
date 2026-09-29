"""BI-PF-0260: PROJECT-STATUS.md is single-writer (run_status); journal uses a distinct file."""
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.project_journal import ProjectJournal  # noqa: E402


def test_journal_status_targets_are_distinct_from_run_status_md():
    j = ProjectJournal(products_dir="x", project="p1")
    assert j.status_file.replace("\\", "/").endswith("project-status.json")
    assert j.status_md.replace("\\", "/").endswith("project-status.md")
    assert not j.status_md.replace("\\", "/").endswith("PROJECT-STATUS.md")


def test_journal_writes_distinct_status_files():
    d = tempfile.mkdtemp()
    try:
        j = ProjectJournal(products_dir=d, project="p1")
        st = j.write_status(None)
        assert st is not None, "write_status returned None (build/write failed)"
        p = os.path.join(d, "p1")
        assert os.path.exists(os.path.join(p, "project-status.json"))
        assert os.path.exists(os.path.join(p, "project-status.md"))
    finally:
        shutil.rmtree(d, ignore_errors=True)
