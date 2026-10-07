"""WorkerGrid Go gate (BI-PF-0412): the coordinator builds, vets, tests, and passes the contract suite.

Asserts (fail-closed): the Go toolchain is present (install hint otherwise), ``gofmt`` is clean,
``go build`` / ``go vet`` / ``go test`` are green for ``workergrid/``, the binary lands at
``workergrid/bin/wg-coordinator``, and the cross-impl contract suite passes with
``WG_CONTRACT_REQUIRE_GO=1`` (pins the Go coordinator's behavior; the python leg self-skips after the
Stage 3a cutover, so this is the parity/regression proof). Run: ``python scripts/dev/wg_go_check.py``.
"""
import os
import shutil
import subprocess
import sys

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# workergrid/ is a sibling of product-forge/ (the git repo root)
_WG = os.path.join(os.path.dirname(str(_ROOT)), "workergrid")
_CONTRACT = os.path.join(_ROOT, "test-framework", "tests", "pipeline",
                         "test_workergrid_service_contract.py")
FAILS = []


def _check(cond, msg):
    if not cond:
        FAILS.append(msg)


def _go_bin():
    found = shutil.which("go")
    if found:
        return found
    local = os.path.join(os.environ.get("LOCALAPPDATA", ""), "go", "bin",
                         "go.exe" if os.name == "nt" else "go")
    return local if os.path.exists(local) else None


def _run(go, args, cwd, env):
    try:
        p = subprocess.run([go, *args], cwd=cwd, env=env, capture_output=True,
                           text=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, f"{type(e).__name__}: {e}"
    return p.returncode, (p.stdout + p.stderr).strip()


def main() -> int:
    go = _go_bin()
    if not go:
        print("wg-go: FAIL")
        print("   - go toolchain not found (install Go, or set PATH / %LOCALAPPDATA%\\go\\bin)")
        return 1
    env = dict(os.environ)
    go_dir = os.path.dirname(go)
    if go_dir not in env.get("PATH", "").split(os.pathsep):
        env["PATH"] = go_dir + os.pathsep + env.get("PATH", "")

    _check(os.path.exists(os.path.join(_WG, "go.mod")), "workergrid/go.mod exists")
    _check(os.path.exists(os.path.join(_WG, "cmd", "wg-coordinator", "main.go")),
           "workergrid/cmd/wg-coordinator/main.go exists")
    _check(os.path.exists(_CONTRACT),
           "contract suite exists (test-framework/tests/pipeline/test_workergrid_service_contract.py)")
    if FAILS:  # structure broken - skip toolchain runs
        print("wg-go: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1

    gofmt = os.path.join(os.path.dirname(go),
                         "gofmt.exe" if os.name == "nt" else "gofmt")
    if os.path.exists(gofmt):
        rc, out = _run(gofmt, ["-l", "."], _WG, env)
        _check(rc == 0 and not out.strip(),
               f"gofmt clean (rc={rc}): {out.strip() or 'formatted'}")
    else:
        FAILS.append("gofmt binary not found next to go")

    rc, out = _run(go, ["build", "-o", "bin/", "./cmd/wg-coordinator"], _WG, env)
    _check(rc == 0, f"go build green (rc={rc}): {out[-800:]}")
    rc, out = _run(go, ["vet", "./..."], _WG, env)
    _check(rc == 0, f"go vet green (rc={rc}): {out[-800:]}")

    rc, out = _run(go, ["test", "./..."], _WG, env)
    _check(rc == 0, f"go test green (rc={rc}): {out[-800:]}")

    bin_name = "wg-coordinator.exe" if os.name == "nt" else "wg-coordinator"
    _check(os.path.exists(os.path.join(_WG, "bin", bin_name)),
           f"binary built at workergrid/bin/{bin_name}")

    env2 = dict(env)
    env2["WG_CONTRACT_REQUIRE_GO"] = "1"
    env2["PYTHONIOENCODING"] = "utf-8"
    try:
        p = subprocess.run([sys.executable, "-m", "pytest", _CONTRACT, "-q", "-o", "addopts="],
                           cwd=str(_ROOT), env=env2, capture_output=True, text=True, timeout=600)
        rc, out = p.returncode, (p.stdout + p.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        rc, out = 1, f"{type(e).__name__}: {e}"
    _check(rc == 0, f"contract suite green (rc={rc}): {out[-800:]}")

    if FAILS:
        print("wg-go: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("wg-go: OK (gofmt + build + vet + test + contract suite parity)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
