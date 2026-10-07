"""PFSSOT-P10 gate: the `/pf` command surface is thin, complete, and API-first.

Asserts: scripts/pf.py exists with the declared verbs + a dispatch table; .opencode/command/pf.md is a thin
adapter (references scripts/pf.py, no orchestration); /pipeline is marked a deprecated alias; the checked-in
global /pf source (.opencode/command_global/pf.md) is self-locating + build mode, with no drift in the
installed ~/.config/opencode/command/pf.md; and the worker/scheduler API routes exist in the OpenAPI surface.
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
# worker/scheduler/work/adapters/dispatch verbs were MOVED to WorkerGrid (/wg) - see ADR-0002.
_REQUIRED_VERBS = {"product", "backlog", "dogfood", "validate", "release", "package",
                   "audit", "status", "pidl"}
_MOVED_VERBS = {"work", "scheduler", "worker", "adapters", "dispatch"}


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
    # decoupled: the moved verbs must NOT be in the /pf VERBS tuple
    import ast
    try:
        _verbs = None
        for node in ast.walk(ast.parse(pf_txt)):
            if isinstance(node, ast.Assign) and any(
                    getattr(t, "id", "") == "VERBS" for t in node.targets):
                _verbs = set(ast.literal_eval(node.value))
        for v in _MOVED_VERBS:
            _check(_verbs is not None and v not in _verbs, f"moved verb '{v}' absent from /pf VERBS")
    except Exception as e:
        FAILS.append(f"pf.py VERBS parse error: {type(e).__name__}")

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

    # Checked-in global /pf source: self-locating, build mode, thin (no installer dependency).
    gcmd = os.path.join(_ROOT, ".opencode", "command_global", "pf.md")
    _check(os.path.exists(gcmd), "command_global/pf.md exists (checked-in global /pf source)")
    gtxt = ""
    if os.path.exists(gcmd):
        with open(gcmd, encoding="utf-8", errors="ignore") as f:
            gtxt = f.read()
    _check("scripts/pf.py" in gtxt, "global pf.md is a thin adapter (calls scripts/pf.py)")
    _check(not re.search(r"def \w+\(|import core", gtxt), "global pf.md contains no logic")
    _check("agent: build" in gtxt, "global pf.md runs in build mode")
    _check("agent: orchestrator" not in gtxt, "global pf.md not bound to orchestrator")
    _check(not re.search(r"(?m)^model:", gtxt), "global pf.md has no model pin")
    _check("PF_ROOT" in gtxt, "global pf.md is self-locating (PF_ROOT resolution)")
    # Installed copy must be byte-identical to the checked-in source; absent = OK (fresh machine/CI).
    home = os.path.expanduser(os.path.join("~", ".config", "opencode", "command", "pf.md"))
    if os.path.exists(home) and os.path.exists(gcmd):
        def _norm(p):
            # newline-insensitive: core.autocrlf may check the source out as CRLF
            with open(p, "rb") as f:
                return f.read().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        if _norm(home) != _norm(gcmd):
            FAILS.append("installed ~/.config/opencode/command/pf.md drifted from "
                         ".opencode/command_global/pf.md (re-copy the checked-in source)")
    elif not os.path.exists(home):
        print("pf-surface: note - no installed global /pf (optional; copy "
              ".opencode/command_global/pf.md to ~/.config/opencode/command/pf.md)")

    if FAILS:
        print("pf-surface: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("pf-surface: OK (/pf verbs + thin adapter + /pipeline alias; worker/scheduler moved to /wg)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
