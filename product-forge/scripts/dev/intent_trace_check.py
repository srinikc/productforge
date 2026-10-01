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


def _registered_stores() -> set:
    try:
        with open(os.path.join(_ROOT, "config", "store-registry.json"), encoding="utf-8") as f:
            return set((json.load(f).get("stores") or {}).keys())
    except Exception:
        return set()


def _routes() -> set:
    try:
        from api.app import app
        return set(app.openapi().get("paths", {}).keys())
    except Exception:
        return set()


def _check(desc: str, routes: set, stores: set):
    kind, _, val = str(desc).partition(":")
    val = val.strip()
    if not val:
        return "empty descriptor"
    if kind == "route":
        path = val.split(" ", 1)[1] if " " in val else val
        return None if path in routes else f"route not registered: {val}"
    if kind == "store":
        return None if val in stores else f"store not registered: {val}"
    if kind in ("module", "test", "file", "artifact"):
        p = val
        if kind == "module" and "/" not in p and not p.endswith(".py"):
            p = p.replace(".", "/") + ".py"
        return None if os.path.exists(os.path.join(_ROOT, p)) else f"path not found: {p}"
    return None if os.path.exists(os.path.join(_ROOT, val)) else f"path not found: {val}"


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
    routes, stores = _routes(), _registered_stores()
    drift, checked = [], 0
    for scope, project in backlog._all_scopes():
        for it in backlog.list_open(scope, project, order=False) + backlog.list_closed(scope, project):
            if str(it.get("origin")) != "review":
                continue
            descs = (it.get("links") or {}).get("backend_capability") or []
            if not descs:
                continue
            checked += 1
            ref = backlog.qualify(scope, project, it.get("id"))
            for d in descs:
                err = _check(d, routes, stores)
                if err:
                    drift.append(f"{ref}: {d} -> {err}")

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
