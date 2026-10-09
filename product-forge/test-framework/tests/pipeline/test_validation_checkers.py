"""BI-PF-0425: every validation-profile checker is implemented (no profile is permanently BLOCKED)."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from core import validation_engine as ve  # noqa: E402


def test_every_profile_checker_is_implemented():
    profs = ve.profiles().get("profiles", {})
    assert profs, "profiles must load"
    missing = []
    for name, prof in profs.items():
        for c in prof.get("checks", []):
            if c == "target":
                continue
            if c not in ve._CHECKERS:
                missing.append(f"{name}:{c}")
    assert not missing, f"unimplemented checkers: {missing}"


def test_new_checkers_return_a_valid_status(tmp_path):
    d = tmp_path / "proj"
    d.mkdir()
    for fn in (ve._check_cross_contract, ve._check_e2e, ve._check_security):
        r = fn("_nonexistent_project", str(d))
        assert r["status"] in ("pass", "fail", "skip", "unknown"), (fn.__name__, r)


def test_security_scan_runs_and_passes_clean_tree(tmp_path):
    d = tmp_path / "clean"
    d.mkdir()
    (d / "main.py").write_text("print('hello world')\n", encoding="utf-8")
    r = ve._check_security("clean", str(d))
    assert r["status"] in ("pass", "fail")          # checker runs (not 'unknown')
    assert r["status"] == "pass"                     # a clean tree passes


# ── BI-PF-0455: e2e checker runs the product's e2e suite (no prior-DOGFOOD-PASS dependency) ──

def test_e2e_skips_without_suite(tmp_path):
    d = tmp_path / "proj"
    d.mkdir()
    assert ve._check_e2e("p", str(d))["status"] == "skip"


def _stub_runner(monkeypatch, ok):
    from core import test_framework_integration as tfi
    monkeypatch.setattr(tfi, "_run_plan_item",
                        lambda item, pd, tech=None: {"category": "e2e", "runner": "playwright",
                                                     "ok": ok, "tail": ""})


def test_e2e_runs_suite_pass(tmp_path, monkeypatch):
    d = tmp_path / "proj"
    (d / "tests" / "e2e").mkdir(parents=True)
    _stub_runner(monkeypatch, True)
    assert ve._check_e2e("p", str(d))["status"] == "pass"


def test_e2e_runs_suite_fail(tmp_path, monkeypatch):
    d = tmp_path / "proj"
    (d / "tests" / "e2e").mkdir(parents=True)
    _stub_runner(monkeypatch, False)
    assert ve._check_e2e("p", str(d))["status"] == "fail"


def test_e2e_runner_absent_is_skip(tmp_path, monkeypatch):
    d = tmp_path / "proj"
    (d / "tests" / "e2e").mkdir(parents=True)
    _stub_runner(monkeypatch, None)
    assert ve._check_e2e("p", str(d))["status"] == "skip"
