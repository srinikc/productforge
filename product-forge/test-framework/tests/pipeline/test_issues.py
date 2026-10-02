"""Issue tracker (BI-PF-0262): tagged ids, dedup by source_ref, 1:1 backlog mapping,
RCCA gate before a linked backlog item can complete."""
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import backlog, issues  # noqa: E402

ROOT = Path(__file__).parent.parent.parent.parent


def _clean(proj):
    d = ROOT / "products" / proj
    if d.is_dir():
        shutil.rmtree(d, ignore_errors=True)


def test_raise_id_dedup_and_priority():
    proj = "_test_issues_a"
    try:
        it = issues.raise_issue("project", proj, "Boom", source="defect", source_ref="D-1",
                                priority="P1", module="core.x")
        assert it["id"].startswith("IS-") and it["priority"] == "P1"
        again = issues.raise_issue("project", proj, "Boom", source="defect", source_ref="D-1")
        assert again["id"] == it["id"]  # idempotent by (source, source_ref)
    finally:
        _clean(proj)


def test_rcca_required_to_close_issue():
    proj = "_test_issues_b"
    try:
        it = issues.raise_issue("project", proj, "Y")
        with pytest.raises(ValueError):
            issues.set_status("project", proj, it["id"], "closed")
        issues.set_rcca("project", proj, it["id"], root_cause="r", corrective="c",
                        fixed_where="core/x.py")
        assert issues.rcca_complete(issues.get("project", proj, it["id"]))
        issues.set_status("project", proj, it["id"], "verified")
        assert issues.get("project", proj, it["id"])["status"] == "verified"
    finally:
        _clean(proj)


def test_backlog_close_gated_by_issue_rcca():
    proj = "_test_issues_c"
    try:
        it = issues.raise_issue("project", proj, "Z")
        bi = backlog.add_epic("project", proj, "fix Z", type_="bug", origin="intake")
        issues.link_backlog("project", proj, it["id"],
                            backlog.qualify("project", proj, bi["id"]))
        # backlog item now carries the issue link; closing is blocked until RCCA completes
        backlog.set_status("project", proj, bi["id"], "completed")
        assert backlog.get_epic("project", proj, bi["id"])["status"] != "completed"
        issues.set_rcca("project", proj, it["id"], root_cause="r", corrective="c",
                        fixed_where="core/x.py")
        backlog.set_status("project", proj, bi["id"], "completed")
        assert backlog.get_epic("project", proj, bi["id"])["status"] == "completed"
    finally:
        _clean(proj)


def test_num_reads_sequence_not_tag_digits():
    """IS-PF-0033: _num must read only the final <nnn> segment, not digits embedded in the tag."""
    assert issues._num("IS-TESTBIPF02-0002") == 2
    assert issues._num("IS-PF-0032") == 32
    assert issues._num("IS-TESTBIPF02-0126") == 126
    assert backlog._num("BI-TESTBIPF02-0002") == 2
    assert backlog._num("BI-PF-0354") == 354
    assert backlog._num("BI-0137") == 137


def test_raised_ids_are_bounded_and_sequential():
    """Ids stay short/sequential even when the project slug ends in digits (IS-PF-0033 guard)."""
    proj = "_test_bi_pf_0271"
    try:
        ids = [issues.raise_issue("project", proj, f"t{i}", source_ref=f"r{i}")["id"] for i in range(3)]
        assert all(len(i) < 40 for i in ids), ids
        nums = [issues._num(i) for i in ids]
        assert nums == sorted(nums) and nums[-1] == nums[0] + 2, nums
    finally:
        _clean(proj)
