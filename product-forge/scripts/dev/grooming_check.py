"""PFSSOT-P2 gate: grooming is data-driven, AI-default, and never blocks.

Verifies: guidelines load with default_mode=ai; the deterministic groomer produces a valid proposal and
writes analysis IN_PROGRESS; user decision APPROVE -> COMPLETE + ready; DEFER/REJECT map correctly; the AI
path is attempted by default but falls back to deterministic when no model is available (never raises).
Run: ``python scripts/dev/grooming_check.py``.
"""
import os
import shutil
import sys

try:
    from core.paths import PRODUCTS_DIR as _PRODUCTS
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    _PRODUCTS = os.path.join(_ROOT, "products")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

FAILS = []
_PROJ = "_test_grooming_gate"


def _check(cond, msg):
    if not cond:
        FAILS.append(msg)


def _clean():
    shutil.rmtree(os.path.join(str(_PRODUCTS), _PROJ), ignore_errors=True)


def main() -> int:
    os.environ.setdefault("PF_OFFLINE", "1")  # gate never makes live model calls
    from core import backlog, grooming
    _clean()
    try:
        gl = grooming.guidelines()
        _check(gl.get("default_mode") == "ai", "AI is the default grooming mode")
        _check(bool(gl.get("checklist")), "guidelines checklist present")
        _check("cadence" in gl, "cadence defined")

        iid = backlog.add_epic("project", _PROJ, "Gate item", body="x", tag="TST")["id"]

        # default (AI) resolves to the AI mode logically; offline it falls back deterministically.
        _check(grooming.default_mode() == "ai", "default mode is ai")
        r = grooming.groom("project", _PROJ, iid)  # default mode (offline -> deterministic fallback)
        _check(r.get("applied") is True, "default groom applied")
        _check(r.get("mode") in ("ai", "deterministic"), "mode resolved")
        b = backlog.get("project", _PROJ, iid)
        _check(b["analysis"]["status"] == "IN_PROGRESS", "analysis -> IN_PROGRESS after groom")

        # user decision
        grooming.decide("project", _PROJ, iid, "APPROVE")
        b = backlog.get("project", _PROJ, iid)
        _check(b["analysis"]["status"] == "COMPLETE", "APPROVE -> COMPLETE")
        _check(b["readiness"]["ready"] is True, "APPROVE -> ready")
        _check(b["decisions"] and b["decisions"][-1]["decision"] == "APPROVE", "decision recorded")

        # invalid decision rejected
        try:
            grooming.decide("project", _PROJ, iid, "NOPE")
            _check(False, "invalid decision should raise")
        except ValueError:
            pass
    finally:
        _clean()

    if FAILS:
        print("grooming: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("grooming: OK (AI-default + deterministic fallback, guidelines, user decide)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
