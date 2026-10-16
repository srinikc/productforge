"""BI-PF-1419: precheck NAMED groups - tests that can fail.

The full precheck is churned in named groups (structure/security/contracts/worker/backlog/quality/tests-a/
tests-b/deep/release). Every gate must belong to exactly one group, and the two test halves must partition
the suite. Pure-function tests (no repo-state dependence).
"""
import importlib.util
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
os.environ.setdefault("PF_OFFLINE", "1")

_ROOT = Path(__file__).resolve().parents[3]


def _load():
    spec = importlib.util.spec_from_file_location(
        "precheck_mod", _ROOT / "scripts" / "dev" / "precheck.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_every_gate_is_in_exactly_one_named_group():
    p = _load()
    names = [n for n, _c, _t, _a in p._GATES]
    missing = [n for n in names if n not in p._GROUP_OF]
    assert not missing, f"gates with no group: {missing}"
    assert set(p._GROUP_OF.values()) <= (set(p._GROUP_ORDER) | {"release"})


def test_groups_partition_all_gates():
    p = _load()
    names = {n for n, _c, _t, _a in p._GATES}
    union = set()
    for g in p._GROUP_ORDER:
        if g in p._TEST_GROUPS:
            continue
        union |= {n for n, _c, _t, _a in p._GATES if p._GROUP_OF.get(n) == g}
    assert union == names, f"unpartitioned: {names - union}"


def test_named_group_emits_its_steps():
    p = _load()
    steps, label = p._group_steps("backlog")
    assert steps and "gate" in label
    names = {n for n, _c in steps}
    assert {"backlog-context", "backlog-write", "backlog-epic"} <= names
    # the 'fast' aggregate alias covers all fast-tier gates
    fast, _ = p._group_steps("fast")
    assert len(fast) == sum(1 for _n, _c, t, _a in p._GATES if t == "fast")
    assert p._group_steps("does-not-exist")[0] is None


def test_numeric_aliases_resolve():
    p = _load()
    assert p._resolve_group("1") == "fast"
    assert p._resolve_group("2") == "deep"
    assert p._resolve_group("3") == "release"
    assert p._resolve_group("4") == "tests-a"
    assert p._resolve_group("backlog") == "backlog"


def test_test_halves_partition_the_suite():
    p = _load()
    a, b = p._suite_halves()["tests-a"], p._suite_halves()["tests-b"]
    assert a and b and set(a).isdisjoint(b)
    assert sorted(a + b) == sorted(p._suite_files())
