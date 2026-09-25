"""Deterministic per-feature FR/NFR/US id allocation + post-merge integrity gate.

Guards the duplicate-id bug: stage 1 (design) and stage 1a (product-design-spec)
generate per-feature sections in INDEPENDENT LLM calls, so each call used to
invent its own global id plan and the ids collided across features.

  t1  id_allocation() ranges are unique, contiguous-per-feature, stable across runs.
  t2  a merge with a duplicated FR id FAILS the gate and lists the offending ids.
  t3  an out-of-range / undefined-reference id FAILS the gate.
  t4  a clean merge (all ids unique + in range) PASSES.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from core.agent_requirements import ID_BLOCK_SIZES, id_allocation  # noqa: E402
from core.output_checklist import (  # noqa: E402
    check as checklist_check,
    check_id_integrity_all,
    id_families,
)


def test_t1_allocation_unique_contiguous_stable():
    outline = ["F-1: Alpha", "F-2: Beta", "F-3: Gamma"]
    a = id_allocation(outline)
    b = id_allocation(outline)
    assert a == b  # stable across runs
    assert list(a.keys()) == ["F-1", "F-2", "F-3"]
    assert a["F-1"]["FR"] == (1, 25)
    assert a["F-2"]["FR"] == (26, 50)
    assert a["F-3"]["FR"] == (51, 75)
    assert a["F-1"]["NFR"] == (1, 15) and a["F-2"]["NFR"] == (16, 30)
    assert a["F-1"]["US"] == (1, 15) and a["F-2"]["US"] == (16, 30)

    for prefix, size in ID_BLOCK_SIZES.items():
        covered = set()
        for fid in a:
            start, end = a[fid][prefix]
            rng = set(range(start, end + 1))
            assert len(rng) == size
            assert not (covered & rng), f"{prefix} overlaps at {fid}"
            covered |= rng
        assert covered == set(range(1, len(outline) * size + 1))  # contiguous


def _gate(tmp_path, text):
    p = tmp_path / "spec.md"
    p.write_text(text, encoding="utf-8")
    return checklist_check("design", [str(p)])


def test_t2_duplicate_id_fails_with_offending_ids(tmp_path):
    text = (
        "# Design\n"
        "## F-1: Alpha\n- FR-1: a\n- FR-2: b\n"
        "## F-2: Beta\n- FR-26: c\n- FR-2: duplicated\n"
    )
    res = _gate(tmp_path, text)
    assert res["ok"] is False
    assert "FR-2" in res["id_integrity"]["duplicates"]
    assert "requirement_ids" in res["essential_missing"]


def test_t3_out_of_range_and_undefined_reference_fail(tmp_path):
    oor = _gate(tmp_path, "# Design\n## F-1: Alpha\n- FR-1: a\n- FR-999: way out\n")
    assert oor["ok"] is False
    assert "FR-999" in oor["id_integrity"]["out_of_range"]

    undef = _gate(tmp_path, "# Design\n## F-1: Alpha\n- FR-1: a\nSee US-9 for details.\n")
    assert undef["ok"] is False
    assert "US-9" in undef["id_integrity"]["undefined_refs"]


def test_t4_clean_merge_passes(tmp_path):
    text = (
        "# Design\n"
        "## F-1: Alpha\n"
        "### Behaviour\n- does a thing\n"
        "### Validation\n- rejects empty\n"
        "### Acceptance criteria\n- happy path\n"
        "- FR-1: alpha requirement\n- NFR-1: alpha perf\n- US-1: as a user\n"
        "## F-2: Beta\n"
        "### Behaviour\n- does b thing\n"
        "### Validation\n- rejects empty\n"
        "### Acceptance criteria\n- happy path\n"
        "- FR-26: beta requirement\n- NFR-16: beta perf\n- US-16: as a user\n"
        "## Functional Requirements\n"
        "## Non-Functional Requirements\n"
        "## User Stories\n"
        "## API Contracts\n"
    )
    res = _gate(tmp_path, text)
    assert res["id_integrity"]["ok"] is True
    assert res["ok"] is True


def _full_design(blocks):
    """Wrap per-feature blocks with the global sections design requires."""
    head = "# Design\n"
    tail = ("## Functional Requirements\n## Non-Functional Requirements\n"
            "## User Stories\n## API Contracts\n")
    return head + blocks + tail


def test_t5_local_id_may_repeat_across_features(tmp_path):
    text = _full_design(
        "## F-1: Alpha\n### Behaviour\n- does a\n### Business rules\n"
        "- **AC-1:** first feature\n### Acceptance criteria\n- ok\n"
        "- FR-1: alpha req\n- NFR-1: alpha perf\n- US-1: as a user\n"
        "## F-2: Beta\n### Behaviour\n- does b\n### Business rules\n"
        "- **AC-1:** second feature, different meaning\n### Acceptance criteria\n- ok\n"
        "- FR-26: beta req\n- NFR-16: beta perf\n- US-16: as a user\n"
    )
    res = _gate(tmp_path, text)
    assert res["id_integrity"]["ok"] is True
    assert res["id_integrity"]["local_duplicates"] == []
    assert res["ok"] is True


def test_t6_local_id_duplicate_in_same_feature_fails(tmp_path):
    text = _full_design(
        "## F-1: Alpha\n### Behaviour\n- does a\n### Business rules\n"
        "- **AC-1:** first\n- **AC-1:** duplicate in same feature\n"
        "### Acceptance criteria\n- ok\n"
        "- FR-1: alpha req\n- NFR-1: alpha perf\n- US-1: as a user\n"
    )
    res = _gate(tmp_path, text)
    assert res["id_integrity"]["ok"] is False
    assert "AC-1 in F-1" in res["id_integrity"]["local_duplicates"]
    assert "requirement_ids" in res["essential_missing"]
    assert res["ok"] is False


def test_t7_local_id_referenced_but_not_defined_fails(tmp_path):
    text = _full_design(
        "## F-1: Alpha\n### Behaviour\n- does a\n### Business rules\n"
        "- **AC-1:** defined here\n### Acceptance criteria\n- ok\n"
        "See AC-9 for the missing one.\n"
        "- FR-1: alpha req\n- NFR-1: alpha perf\n- US-1: as a user\n"
    )
    res = _gate(tmp_path, text)
    assert res["id_integrity"]["ok"] is False
    assert "AC-9 in F-1" in res["id_integrity"]["local_undefined_refs"]


def test_t8_global_rule_unchanged_and_defaults_when_config_missing(tmp_path):
    # GLOBAL FR duplicate across features still FAILS (unchanged rule).
    dup = _gate(tmp_path, _full_design(
        "## F-1: Alpha\n### Behaviour\n- a\n### Business rules\n- b\n"
        "### Acceptance criteria\n- c\n- FR-1: alpha\n"
        "## F-2: Beta\n### Behaviour\n- a\n### Business rules\n- b\n"
        "### Acceptance criteria\n- c\n- FR-1: duplicate global id\n"
    ))
    assert dup["id_integrity"]["ok"] is False
    assert "FR-1" in dup["id_integrity"]["duplicates"]

    # Missing config file -> hardcoded defaults still classify AC- as LOCAL.
    fam = id_families(str(tmp_path / "missing-spec-id-families"))
    assert fam["global"] == ["FR", "NFR", "US"]
    assert "AC" in fam["local"]
    res = check_id_integrity_all(
        _full_design(
            "## F-1: Alpha\n### Business rules\n- **AC-1:** one\n- **AC-1:** two\n"
            "- FR-1: alpha\n"
        ), families=fam)
    assert res["ok"] is False
    assert "AC-1 in F-1" in res["local_duplicates"]
