"""Intent traceability gate (drift-guard, part D).

For every review-origin backlog item that records artifact/test descriptors (`links.backend_capability`), verify
those descriptors still resolve: module/test/file paths exist, routes are registered, stores are registered.
A broken link means the item claims something that is gone or was never wired — drift caught in CI, not runtime.

Advisory by default (exit 0 with warnings). `--strict` exits 1 on drift (flip it on once the workflow is proven).
"""
import argparse
import json
import os
import sys

os.environ.setdefault("API_ALLOW_ANON", "1")

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# The repo root is one level above product-forge/; sibling components
# (workergrid/) live there, so descriptor paths resolve against either.
_REPO = os.path.dirname(str(_ROOT))


def _exists(p: str) -> bool:
    """A descriptor path may be relative to product-forge/ or the repo root."""
    return os.path.exists(os.path.join(str(_ROOT), p)) or os.path.exists(os.path.join(_REPO, p))


def _flags() -> set:
    try:
        with open(os.path.join(str(_ROOT), "config", "env-flags.json"), encoding="utf-8") as f:
            return set((json.load(f).get("flags") or {}).keys())
    except Exception:
        return set()


def _registered_stores() -> set:
    try:
        with open(os.path.join(str(_ROOT), "config", "store-registry.json"), encoding="utf-8") as f:
            return set((json.load(f).get("stores") or {}).keys())
    except Exception:
        return set()


def _routes() -> set:
    try:
        from api.app import app
        return set(app.openapi().get("paths", {}).keys())
    except Exception:
        return set()


def _check(desc: str, routes: set, stores: set, flags: set = None):
    kind, _, val = str(desc).partition(":")
    val = val.strip()
    if not val:
        return "empty descriptor"
    if kind == "route":
        path = val.split(" ", 1)[1] if " " in val else val
        return None if path in routes else f"route not registered: {val}"
    if kind == "store":
        return None if val in stores else f"store not registered: {val}"
    if kind == "flag":
        known = _flags() if flags is None else flags
        return None if val in known else f"flag not registered: {val}"
    if kind == "command":
        # a command descriptor is a path plus optional args
        p = val.split(" ", 1)[0]
        return None if _exists(p) else f"path not found: {p}"
    if kind in ("module", "test", "file", "artifact"):
        p = val
        if kind == "module" and "/" not in p and not p.endswith(".py"):
            p = p.replace(".", "/") + ".py"
        return None if _exists(p) else f"path not found: {p}"
    return None if _exists(val) else f"path not found: {val}"


def _sha_exists(sha: str) -> bool:
    import subprocess
    if not sha:
        return True
    r = subprocess.run(["git", "-C", _ROOT, "cat-file", "-e", sha], capture_output=True, text=True)
    return r.returncode == 0


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Intent traceability check (review-origin backlog items)")
    ap.add_argument("--strict", action="store_true", help="exit 1 on any drift")
    a = ap.parse_args(argv)

    from core import backlog
    routes, stores, flags = _routes(), _registered_stores(), _flags()
    drift, checked = [], 0
    for scope, project in backlog._all_scopes():
        for it in backlog.list_open(scope, project, order=False) + backlog.list_closed(scope, project):
            if str(it.get("origin")) != "review":
                continue
            links = it.get("links") or {}
            descs = links.get("backend_capability") or []
            delivery = links.get("delivery") or {}
            if not descs and not delivery:
                continue
            checked += 1
            ref = backlog.qualify(scope, project, it.get("id"))
            for d in descs:
                err = _check(d, routes, stores, flags)
                if err:
                    drift.append(f"{ref}: {d} -> {err}")
            # delivery provenance: the merge commit must exist in the repo
            if delivery and not _sha_exists(str(delivery.get("merge_sha") or "")):
                drift.append(f"{ref}: delivery merge_sha not found: {delivery.get('merge_sha')!r}")

    if drift:
        print(f"intent-trace: {len(drift)} drift item(s) across {checked} review item(s)")
        for d in drift:
            print("   -", d)
        if a.strict:
            return 1
        print("intent-trace: advisory (use --strict to fail)")
        return 0
    print(f"intent-trace: OK ({checked} review item(s) verified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
