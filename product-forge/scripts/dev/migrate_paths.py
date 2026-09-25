"""One-shot migration (BI-0204): route every root derivation through core/paths.py.

For each ``core/``, ``dashboard/``, ``scripts/`` module that re-derives the repo root,
replace the computation with ``_PF_ROOT`` (imported from ``core.paths``) and inject a
self-seeding header so the module still works when executed from any CWD.

Idempotent; skips ``core/paths.py`` and frozen legacy files. Re-run safe.
"""
import ast
import json
import os
import re

SKIP = {"core/paths.py"}

HEADER = [
    "try:",
    "    from core.paths import ROOT as _PF_ROOT",
    "except ImportError:  # executed as a script: seed the repo root on sys.path, then retry",
    "    import os as _pf_os",
    "    import sys as _pf_sys",
    "    _pf_d = _pf_os.path.abspath(__file__)",
    "    for _pf_i in range(3):",
    "        _pf_d = _pf_os.path.dirname(_pf_d)",
    "        if _pf_os.path.isfile(_pf_os.path.join(_pf_d, 'core', 'paths.py')):",
    "            _pf_sys.path.insert(0, _pf_d)",
    "            break",
    "    from core.paths import ROOT as _PF_ROOT",
]

_p3 = re.compile(r"os\.path\.dirname\(\s*os\.path\.dirname\(\s*os\.path\.dirname\(\s*os\.path\.abspath\(\s*__file__\s*\)\s*\)\s*\)\s*\)")
_ppp = re.compile(r"Path\(\s*__file__\s*\)(?:\.resolve\(\))?\.parent\.parent\.parent")
_p2 = re.compile(r"os\.path\.dirname\(\s*os\.path\.dirname\(\s*os\.path\.abspath\(\s*__file__\s*\)\s*\)\s*\)")
_ppr = re.compile(r"Path\(\s*__file__\s*\)\.resolve\(\)\.parent\.parent")
_pp = re.compile(r"Path\(\s*__file__\s*\)\.parent\.parent")
# order matters: longest first
SUBS = [(_p3, "str(_PF_ROOT)"), (_ppp, "_PF_ROOT"), (_p2, "str(_PF_ROOT)"),
        (_ppr, "_PF_ROOT"), (_pp, "_PF_ROOT")]

_HEADER_FIX_SRC = "isfile(_pf_os.path.join(_pf_d, 'core', 'paths.py'))"
_HEADER_FIX_DST = "isfile(_pf_os.path.join(_pf_d, 'core', 'paths.py'))"


def _iter_py(roots):
    for r in roots:
        for dp, _dn, fn in os.walk(r):
            for f in fn:
                if f.endswith(".py"):
                    yield os.path.join(dp, f).replace("\\", "/")


def _insert_index(lines):
    """Index to insert the header: after module docstring + any __future__ imports."""
    try:
        tree = ast.parse("\n".join(lines))
    except SyntaxError:
        return 0
    idx = 0
    if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(
            getattr(tree.body[0], "value", None), ast.Constant) and isinstance(tree.body[0].value.value, str):
        idx = tree.body[0].end_lineno
    for ln in lines[idx:idx + 4]:
        s = ln.strip()
        if s.startswith("from __future__"):
            idx += 1
        elif s == "" or s.startswith("#"):
            idx += 1
        else:
            break
    return idx


def migrate():
    frozen = set()
    try:
        frozen = set(json.load(open("config/legacy-frozen.json", encoding="utf-8")).get("files", {}))
    except Exception:
        pass
    changed = 0
    sites = 0
    for rel in _iter_py(["core", "dashboard", "scripts"]):
        if rel in SKIP or rel in frozen:
            continue
        text = open(rel, encoding="utf-8").read()
        lines = text.split("\n")
        hits = 0
        for i, ln in enumerate(lines):
            if _HEADER_FIX_SRC in ln:  # repair the earlier isdir(i.e. never-true) header
                lines[i] = ln.replace(_HEADER_FIX_SRC, _HEADER_FIX_DST)
                hits += 1
                continue
            new = ln
            for rx, rep in SUBS:
                new, n = rx.subn(rep, new)
                hits += n
            lines[i] = new
        if not hits:
            continue
        if "from core.paths import" not in text:
            idx = _insert_index(lines)
            lines[idx:idx] = HEADER + [""]
        open(rel, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
        changed += 1
        sites += hits
        print(f"  {rel}: {hits} site(s)")
    print(f"\nmigrated {sites} site(s) across {changed} file(s)")


if __name__ == "__main__":
    migrate()
