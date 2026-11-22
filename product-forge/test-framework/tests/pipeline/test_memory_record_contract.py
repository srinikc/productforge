"""
Unit tests for Canonical Memory Mapping Adapter (BI-PF-1566).
Verifies that all 8 legacy MemoryType enums map cleanly to the 6 canonical kinds.
"""

import json
from pathlib import Path
import pytest

from core.agent_memory import MemoryType, map_legacy_type_to_canonical


def test_map_all_legacy_enums_to_canonical():
    expected = {
        MemoryType.RAW_EVIDENCE: "external",
        MemoryType.SEMANTIC: "semantic",
        MemoryType.EPISODIC: "episodic",
        MemoryType.DECISION: "procedural",
        MemoryType.PROCEDURAL: "procedural",
        MemoryType.FAILURE: "episodic",
        MemoryType.POLICY: "semantic",
        MemoryType.WORKING: "working",
    }

    for mem_type, expected_kind in expected.items():
        kind, tags = map_legacy_type_to_canonical(mem_type)
        assert kind == expected_kind, f"Failed for {mem_type}"
        assert len(tags) > 0, f"Expected preservation tags for {mem_type}"
        assert tags[0] == f"legacy:{mem_type.value}"


def test_map_legacy_aliases():
    aliases = {
        "short_term": "working",
        "working_memory": "working",
        "long_term_fact": "semantic",
        "concept": "semantic",
        "session_event": "episodic",
        "conversation_turn": "episodic",
        "execution_step": "procedural",
        "workflow_rule": "procedural",
    }

    for alias, expected_kind in aliases.items():
        kind, tags = map_legacy_type_to_canonical(alias)
        assert kind == expected_kind, f"Failed for alias {alias}"
        assert tags[0] == f"legacy:{alias}"


def test_map_unknown_legacy_type_fails_closed():
    with pytest.raises(ValueError, match="Unknown legacy memory type"):
        map_legacy_type_to_canonical("unsupported_legacy_category")


def test_mapping_config_matches_canonical_schema():
    cfg_file = Path("config/memory_legacy_mapping.json")
    assert cfg_file.is_file(), "config/memory_legacy_mapping.json must exist"

    data = json.loads(cfg_file.read_text(encoding="utf-8"))
    mappings = data.get("mappings", {})
    assert len(mappings) >= 8, "Must contain at least 8 legacy mappings"

    canonical_kinds = {"working", "semantic", "episodic", "procedural", "prospective", "external"}
    for k, v in mappings.items():
        assert v["kind"] in canonical_kinds, f"Mapping {k} specifies unknown kind {v['kind']}"
