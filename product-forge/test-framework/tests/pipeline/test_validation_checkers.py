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
