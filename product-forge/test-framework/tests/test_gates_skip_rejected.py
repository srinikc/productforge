from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import design_pack
import functional_spec
import spec_pack
import gate_status


def _item(status: str) -> dict:
    return {"id": "BI-TEST-0001", "status": status, "created_at": "2026-11-24T00:00:00+00:00"}


def test_rejected_status_skips_design_and_spec_gates():
    for mod, cfg in (
        (design_pack, design_pack._cfg()),
        (functional_spec, functional_spec._cfg()),
        (spec_pack, spec_pack._cfg()),
    ):
        for status in ("rejected", "cancelled", "won't_do", "wont_do"):
            assert mod.should_enforce(_item(status), cfg) is False


def test_live_statuses_still_enforced():
    for mod, cfg in (
        (design_pack, design_pack._cfg()),
        (functional_spec, functional_spec._cfg()),
        (spec_pack, spec_pack._cfg()),
    ):
        assert mod.should_enforce(_item("in_progress"), cfg) is True


def test_unknown_status_still_enforced():
    for mod, cfg in (
        (design_pack, design_pack._cfg()),
        (functional_spec, functional_spec._cfg()),
        (spec_pack, spec_pack._cfg()),
    ):
        assert mod.should_enforce(_item("on_hold"), cfg) is True


def test_gates_share_the_terminal_predicate():
    for mod in (design_pack, functional_spec, spec_pack):
        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "gate_status.should_skip" in source


def test_terminal_status_set_is_explicit():
    assert gate_status.TERMINAL_SKIP == {"rejected", "cancelled", "won't_do", "wont_do"}
