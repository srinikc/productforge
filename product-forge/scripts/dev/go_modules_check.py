"""BI-PF-1381: CI gate for the product-forge Go modules (``product-forge/go/*``).

Discovers every ``go/<module>/go.mod`` and, for each module, runs ``gofmt -l`` (must be clean),
``go vet``, ``go build ./...`` and ``go test ./...``. DB-backed tests self-skip unless their DSN env is set,
so the gate is green in CI without a database. Fail-closed when the Go toolchain is absent (install hint).
Covers the EDP Go modules (datastore EDP-07, migrate EDP-08, and the edpsvc internal packages).

Run: ``python scripts/dev/go_modules_check.py``.
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

_GO_DIR = os.path.join(str(_ROOT), "go")
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


def _run(bin_path, args, cwd, env):
    try:
        p = subprocess.run([bin_path, *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=900)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, f"{type(e).__name__}: {e}"
    return p.returncode, (p.stdout + p.stderr).strip()


def _modules() -> list:
    """Every directory under go/ that holds a go.mod (its own module)."""
    out = []
    if os.path.isdir(_GO_DIR):
        for name in sorted(os.listdir(_GO_DIR)):
            d = os.path.join(_GO_DIR, name)
            if os.path.isfile(os.path.join(d, "go.mod")):
                out.append(d)
    return out


def _git(*args) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=str(_ROOT), capture_output=True, text=True)
        return (r.stdout or "").strip()
    except Exception:
        return ""


def _changed_files() -> set:
    """Paths (relative to _ROOT) changed vs origin/develop + working tree + untracked (diff-scoped gofmt)."""
    pfx = _git("rev-parse", "--show-prefix").replace("\\", "/")  # e.g. "product-forge/"
    files = set()

    def _add(out):
        for ln in (out or "").splitlines():
            p = ln.strip().replace("\\", "/")
            if not p:
                continue
            if pfx and p.startswith(pfx):
                p = p[len(pfx):]
            files.add(p)

    _add(_git("diff", "--name-only", "origin/develop", "--"))
    _add(_git("diff", "--name-only", "--cached"))
    _add(_git("diff", "--name-only"))
    _add(_git("ls-files", "--others", "--exclude-standard"))
    return files


def main() -> int:
    go = _go_bin()
    if not go:
        print("go-modules: FAIL")
        print("   - go toolchain not found (install Go, or set PATH / %LOCALAPPDATA%\\go\\bin)")
        return 1
    env = dict(os.environ)
    go_dir = os.path.dirname(go)
    if go_dir not in env.get("PATH", "").split(os.pathsep):
        env["PATH"] = go_dir + os.pathsep + env.get("PATH", "")

    mods = _modules()
    _check(bool(mods), "at least one go/<module>/go.mod found")
    if not mods:
        print("go-modules: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1

    gofmt = os.path.join(os.path.dirname(go), "gofmt.exe" if os.name == "nt" else "gofmt")
    changed = _changed_files()
    for d in mods:
        rel = os.path.relpath(d, str(_ROOT)).replace("\\", "/")
        if os.path.exists(gofmt):
            rc, out = _run(gofmt, ["-l", "."], d, env)
            flagged = [ln.strip() for ln in out.splitlines() if ln.strip()]
            # diff-scoped: fail only on CHANGED files (pre-existing debt is advisory) - like lint_check.
            new_bad = [f for f in flagged if f"{rel}/{f}".replace("//", "/") in changed]
            _check(rc == 0 and not new_bad,
                   f"{rel}: gofmt not clean on CHANGED file(s) (rc={rc}): {', '.join(new_bad) or 'none'}")
            if flagged and not new_bad:
                print(f"go-modules: advisory - {rel} pre-existing unformatted file(s): {', '.join(flagged)}")
        else:
            FAILS.append("gofmt binary not found next to go")
        rc, out = _run(go, ["vet", "./..."], d, env)
        _check(rc == 0, f"{rel}: go vet green (rc={rc}): {out[-400:]}")
        rc, out = _run(go, ["build", "./..."], d, env)
        _check(rc == 0, f"{rel}: go build green (rc={rc}): {out[-400:]}")
        rc, out = _run(go, ["test", "./..."], d, env)
        _check(rc == 0, f"{rel}: go test green (rc={rc}): {out[-400:]}")

    if FAILS:
        print("go-modules: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print(f"go-modules: OK ({len(mods)} module(s): gofmt + vet + build + test)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
