#!/usr/bin/env python3
"""Invocation audit: is every core module actually REACHABLE from the runtime path?

Why this exists
---------------
`wired_audit.py` classifies a module by *substring mention* ("is `core.X` imported
by a runtime file?"). A single unused import — e.g.
``from core.discovery_engine import run_discovery  # noqa: F401`` — is enough to be
reported as **RUNTIME**, so "imported but never invoked" modules hide.

This audit instead builds a **reachability graph** from the real entrypoints and
follows *use* edges (a name bound from a core import that is actually loaded),
plus the dynamic dispatch surface (``"core.X:Class"`` strings used by
``core/pipeline_capabilities.py``).

Every core module is classified by the highest surface that reaches it:
RUNTIME > CLI > TOOLING, plus ENTRYPOINT (the invoker itself) and DEPRECATED
(dead code pending removal — reported separately, never counted as unwired).

Exit 0 = **UNWIRED: 0**. Exit 1 = at least one module reached by no surface.
"""
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Reachability roots, by surface. A module is "wired" if ANY real entry can reach it;
# the highest tier that reaches it becomes its reported status.
ENTRY_RUNTIME = [
    "core/pipeline_executor.py", "core/orchestrator", "core/test_framework_integration.py",
    "core/qa_report.py", "core/qa_manifest.py", "core/build_manager.py", "core/vcs.py",
]
ENTRY_CLI = [
    "scripts/run_pipeline.py", "scripts/pipeline.py", "core/main.py",
    "dashboard/server.py", "dashboard/api/app.py", "approve.py",
]
ENTRY_TOOLING = ["scripts/dev", "adapters", "scripts/setup"]

# Entrypoints themselves (not "invoked" — they are the invoker).
ENTRY_MODULES = {"core.main"}

# Dead modules pending removal. Currently empty: forge_supervisor, human_controls and
# pipeline_engine were removed after the removal check (superseded by PipelineExecutor
# + core/orchestrator/*). Add here only with a removal plan.
DEPRECATED = set()


def _rel(p):
    return os.path.relpath(p, ROOT).replace("\\", "/")


def _py(base):
    out = []
    d = os.path.join(ROOT, base)
    if not os.path.isdir(d):
        return out
    for dp, _dn, fn in os.walk(d):
        if any(x in dp for x in ("node_modules", "__pycache__", ".pytest_cache")):
            continue
        for f in fn:
            if f.endswith(".py"):
                out.append(os.path.join(dp, f))
    return out


def build_graph():
    core_files = _py("core")
    scan_files = core_files + _py("scripts") + _py("dashboard") + _py("adapters")

    mod_of = {}
    for p in core_files:
        r = _rel(p)
        if r.endswith("/__init__.py"):
            continue
        mod_of[r[:-3].replace("/", ".")] = p

    def resolve(name):
        return name if name in mod_of else None

    edges = {}
    for p in scan_files:
        r = _rel(p)
        try:
            tree = ast.parse(open(p, encoding="utf-8", errors="ignore").read())
        except Exception:
            continue
        bound = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.startswith("core."):
                        tgt = resolve(a.name) or resolve(a.name.rsplit(".", 1)[0])
                        if tgt:
                            bound[a.asname or a.name.split(".")[-1]] = tgt
            elif isinstance(node, ast.ImportFrom):
                m = node.module or ""
                if m == "core":
                    for a in node.names:
                        tgt = resolve("core." + a.name)
                        if tgt:
                            bound[a.asname or a.name] = tgt
                elif m.startswith("core"):
                    tgt = resolve(m)
                    if tgt:
                        for a in node.names:
                            bound[a.asname or a.name] = resolve(m + "." + a.name) or tgt
        used = set()
        loads = {n.id for n in ast.walk(tree)
                 if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
        for nm, mod in bound.items():
            if nm in loads:
                used.add(mod)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                    and node.value.id == "core":
                tgt = resolve("core." + node.attr)
                if tgt:
                    used.add(tgt)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                for m in re.findall(r"core\.[a-zA-Z_][a-zA-Z0-9_.]*", node.value):
                    tgt = resolve(m) or resolve(m.rsplit(".", 1)[0])
                    if tgt:
                        used.add(tgt)
        edges[r] = used
    return mod_of, edges


def _expand(entries):
    out = []
    for e in entries:
        if e.endswith(".py"):
            out.append(e)
        else:
            out += [_rel(p) for p in _py(e)]
    return out


def resolve_file_mod(f, mod_of):
    if f.endswith("/__init__.py"):
        return None
    m = f[:-3].replace("/", ".")
    return m if m in mod_of else None


def reachable(mod_of, edges, entries):
    reach_files, reach_mods = set(), set()
    queue = _expand(entries)
    while queue:
        f = queue.pop()
        if f in reach_files:
            continue
        reach_files.add(f)
        fm = resolve_file_mod(f, mod_of)
        if fm:
            reach_mods.add(fm)
        for m in edges.get(f, ()):
            if m not in reach_mods:
                reach_mods.add(m)
                queue.append(_rel(mod_of[m]))
    return reach_mods


def classify(mod_of, edges):
    rt = reachable(mod_of, edges, ENTRY_RUNTIME)
    cli = reachable(mod_of, edges, ENTRY_CLI)
    tool = reachable(mod_of, edges, ENTRY_TOOLING)
    status = {}
    for m in mod_of:
        short = m.split(".")[-1]
        if m in ENTRY_MODULES:
            status[m] = "ENTRYPOINT"
        elif m in rt:
            status[m] = "RUNTIME"
        elif m in cli:
            status[m] = "CLI"
        elif m in tool:
            status[m] = "TOOLING"
        elif short in DEPRECATED:
            status[m] = "DEPRECATED"
        else:
            status[m] = "UNWIRED"
    return status


def main():
    mod_of, edges = build_graph()
    status = classify(mod_of, edges)
    order = ["UNWIRED", "DEPRECATED", "ENTRYPOINT", "TOOLING", "CLI", "RUNTIME"]
    counts = {k: sum(1 for v in status.values() if v == k) for k in order}

    print(f"core modules: {len(mod_of)}")
    print("  " + " | ".join(f"{k}: {counts[k]}" for k in order))
    print("=" * 72)

    if "--report" in sys.argv:
        for m in sorted(status, key=lambda x: (order.index(status[x]), x)):
            print(f"  {status[m]:10s} {m}")
        print("=" * 72)

    unwired = sorted(m for m, s in status.items() if s == "UNWIRED")
    deprecated = sorted(m for m, s in status.items() if s == "DEPRECATED")
    if deprecated:
        print("DEPRECATED (scheduled for removal):")
        for m in deprecated:
            print("   ~", m)
    if unwired:
        print("UNWIRED (not reachable from runtime/CLI/tooling):")
        for m in unwired:
            print("   -", m)
        print(f"\ninvocation-audit: FAIL ({len(unwired)} unwired)")
        return 1
    tail = f" ({len(deprecated)} deprecated pending removal)" if deprecated else ""
    print(f"invocation-audit: OK - unwired: 0{tail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
