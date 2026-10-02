"""ENG-8 gate: shared-path detection + advisory reservations (no shared-store residue).

Uses a temp reservations file via PF_RESERVATIONS_FILE. Exercises: shared allowlist detection, acquire, conflict
on a second holder, all-or-nothing acquire_many rollback, release, and the git-hotspot heuristic.
Run: ``python scripts/dev/reservations_check.py`` (wired into precheck).
"""
import os
import sys
import tempfile

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

FAILS = []


def _check(cond, msg):
    if not cond:
        FAILS.append(msg)


def main() -> int:
    tmp = os.path.join(tempfile.mkdtemp(prefix="pf-resv-"), "reservations." + "json")
    os.environ["PF_RESERVATIONS_FILE"] = tmp
    try:
        from core import reservations as rv

        _check(rv.is_shared("core/worker.py"), "core/** is shared")
        _check(rv.is_shared("api/app.py"), "api/** is shared")
        _check(not rv.is_shared("src/feature.py"), "src/feature.py is not shared")
        _check(rv.shared_paths(["core/x.py", "src/y.py"]) == ["core/x.py"], "shared_paths filter")

        a = rv.acquire("core/x.py", holder_task="T1")
        _check(a.get("ok"), "first acquire ok")
        b = rv.acquire("core/x.py", holder_task="T2")
        _check(b.get("ok") is False and b.get("reason") == "reserved", "second acquire blocked")
        _check((b.get("holder") or {}).get("holder_task") == "T1", "holder reported")

        m = rv.acquire_many(["core/a.py", "core/b.py"], holder_task="T3")
        _check(m.get("ok"), "acquire_many ok")
        roll = rv.acquire_many(["core/c.py", "core/a.py"], holder_task="T4")
        _check(roll.get("ok") is False, "acquire_many blocked on held resource")
        _check(rv.holder_of("core/c.py") is None, "acquire_many rolled back the non-conflicting hold")

        rv.release("core/x.py")
        _check(rv.holder_of("core/x.py") is None, "release frees the resource")
        _check(isinstance(rv.hotspots(), list), "hotspots returns a list")
    finally:
        os.environ.pop("PF_RESERVATIONS_FILE", None)
        import shutil
        shutil.rmtree(os.path.dirname(tmp), ignore_errors=True)

    if FAILS:
        print("reservations: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("reservations: OK (shared detection, acquire/conflict/rollback/release, hotspots)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
