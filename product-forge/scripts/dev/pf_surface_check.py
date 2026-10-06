"""PFSSOT-P10 gate: the `/pf` command surface is thin, complete, and API-first.

Asserts: scripts/pf.py exists with the declared verbs + a dispatch table; .opencode/command/pf.md is a thin
adapter (references scripts/pf.py, no orchestration); /pipeline is marked a deprecated alias; and the
worker/scheduler API routes exist in the OpenAPI surface.
Run: ``python scripts/dev/pf_surface_check.py``.
"""
import os
import re
import sys

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

FAILS = []
_REQUIRED_VERBS = {"product", "backlog", "work", "scheduler", "worker", "adapters",
                   "dispatch", "dogfood", "validate", "release", "package", "audit", "status"}
_REQUIRED_ROUTES = ("/api/v1/engineering/schedule/status", "/api/v1/engineering/schedule/eligible",
                    "/api/v1/engineering/work", "/api/v1/engineering/workers/register",
                    "/api/v1/engineering/adapters", "/api/v1/engineering/dispatch/tick")


def _check(cond, msg):
    if not cond:
        FAILS.append(msg)


def main() -> int:
    pf = os.path.join(_ROOT, "scripts", "pf.py")
    _check(os.path.exists(pf), "scripts/pf.py exists")
    pf_txt = ""
    if os.path.exists(pf):
        with open(pf, encoding="utf-8", errors="ignore") as f:
            pf_txt = f.read()
    for v in _REQUIRED_VERBS:
        _check(f'"{v}"' in pf_txt, f"pf.py declares verb {v}")

    cmd = os.path.join(_ROOT, ".opencode", "command", "pf.md")
    _check(os.path.exists(cmd), ".opencode/command/pf.md exists")
    cmd_txt = ""
    if os.path.exists(cmd):
        with open(cmd, encoding="utf-8", errors="ignore") as f:
            cmd_txt = f.read()
    _check("scripts/pf.py" in cmd_txt, "pf.md is a thin adapter (calls scripts/pf.py)")
    _check(not re.search(r"def \w+\(|import core", cmd_txt), "pf.md contains no logic (thin adapter)")

    pipe = os.path.join(_ROOT, ".opencode", "command", "pipeline.md")
    pipe_txt = ""
    if os.path.exists(pipe):
        with open(pipe, encoding="utf-8", errors="ignore") as f:
            pipe_txt = f.read()
    _check("DEPRECATED" in pipe_txt and "/pf product" in pipe_txt, "/pipeline marked deprecated alias")

    try:
        from api.app import app
        paths = set(app.openapi().get("paths", {}).keys())
        for r in _REQUIRED_ROUTES:
            _check(r in paths, f"API route present: {r}")
    except Exception as e:
        FAILS.append(f"openapi error: {type(e).__name__}")

    if FAILS:
        print("pf-surface: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("pf-surface: OK (/pf verbs + thin adapter + /pipeline alias + worker/scheduler API)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
