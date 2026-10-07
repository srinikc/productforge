"""WorkerGrid gate: the `/wg` execution plane exists, is thin, and the producer contract is present.

Asserts: `workergrid/wg.py` exists with the declared verbs; `.opencode/command/wg.md` is a thin adapter to it;
the shared instructions + config exist; the worker/scheduler verbs were **removed** from `/pf`; and the PF
producer API routes WorkerGrid depends on are present. Run: ``python scripts/dev/wg_surface_check.py``.
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

# workergrid/ is a sibling of product-forge/ (the git repo root)
_WG = os.path.join(os.path.dirname(str(_ROOT)), "workergrid")
FAILS = []
_REQUIRED_VERBS = {"serve", "register", "list", "status", "unregister", "work", "schedule",
                   "adapters", "dispatch", "instruct", "config"}
_REQUIRED_ROUTES = ("/api/v1/backlog", "/api/v1/engineering/schedule/eligible",
                    "/api/v1/backlog/items/{item_id}/status")


def _check(cond, msg):
    if not cond:
        FAILS.append(msg)


def main() -> int:
    wg = os.path.join(_WG, "wg.py")
    _check(os.path.exists(wg), "workergrid/wg.py exists")
    wg_txt = ""
    if os.path.exists(wg):
        with open(wg, encoding="utf-8", errors="ignore") as f:
            wg_txt = f.read()
    for v in _REQUIRED_VERBS:
        _check(f'"{v}"' in wg_txt, f"wg.py declares verb {v}")
    for f in ("client.py", "config." + "json", "instructions.md", "README.md"):
        _check(os.path.exists(os.path.join(_WG, f)), f"workergrid/{f} exists")

    cmd = os.path.join(str(_ROOT), ".opencode", "command", "wg.md")
    _check(os.path.exists(cmd), ".opencode/command/wg.md exists")
    cmd_txt = ""
    if os.path.exists(cmd):
        with open(cmd, encoding="utf-8", errors="ignore") as f:
            cmd_txt = f.read()
    _check("workergrid/wg.py" in cmd_txt, "wg.md is a thin adapter (calls workergrid/wg.py)")
    _check(not re.search(r"def \w+\(|import core", cmd_txt), "wg.md contains no logic (thin adapter)")

    # decoupled: worker/scheduler verbs must NOT be in /pf
    pf = os.path.join(str(_ROOT), "scripts", "pf.py")
    pf_txt = ""
    if os.path.exists(pf):
        with open(pf, encoding="utf-8", errors="ignore") as f:
            pf_txt = f.read()
    import ast
    try:
        _verbs = None
        for node in ast.walk(ast.parse(pf_txt)):
            if isinstance(node, ast.Assign) and any(
                    getattr(t, "id", "") == "VERBS" for t in node.targets):
                _verbs = set(ast.literal_eval(node.value))
        for v in ("work", "scheduler", "worker", "adapters", "dispatch"):
            _check(_verbs is not None and v not in _verbs, f"'{v}' removed from /pf VERBS")
    except Exception as e:
        FAILS.append(f"pf.py VERBS parse error: {type(e).__name__}")

    try:
        from api.app import app
        paths = set(app.openapi().get("paths", {}).keys())
        for r in _REQUIRED_ROUTES:
            _check(r in paths, f"producer API route present: {r}")
    except Exception as e:
        FAILS.append(f"openapi error: {type(e).__name__}")

    if FAILS:
        print("wg-surface: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("wg-surface: OK (/wg verbs + thin adapter + instructions + decoupled from /pf + producer API)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
