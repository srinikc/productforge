"""Store-contract check scoped to CHANGED files (author-time guard for the store-registry rule).

Ported from ``wired_audit.store_audit`` but narrowed to the Python files changed on this branch
(vs the merge-base with ``develop``) plus uncommitted changes. `wired_audit` scans the WHOLE tree
(merge-time, fatal); this catches a NEW unregistered data-file literal at author time so it never
reaches the merge-time precheck. Same registry + allow-list semantics, so the two agree.

Usage:
  python scripts/dev/store_check.py           # check (exit 1 on violation)
  python scripts/dev/store_check.py --strict  # same (default); kept for symmetry with lint_check
"""
import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_EXCLUDE = ("dashboard/", "archive/", "vendor/", "node_modules/", "products/", ".opencode/")
_INTEGRATION = "develop"
_REPO_ROOT = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                            cwd=_ROOT, capture_output=True, text=True).stdout.strip() or _ROOT

# mirror wired_audit constants
STORE_EXTS = ("json", "jsonl", "db", "sqlite", "csv", "yaml", "yml")
# mirror wired_audit: config-registry/doc references are not stores, so they are allowlisted there too
STORE_ALLOW = ("*.schema.json", "build-info.json", "project.json", "package.json",
               "pyproject.toml", "requirements.txt", "tsconfig.json", "store-registry.json",
               "model-tier.json", "model-catalog.json", "shared-paths.json", "engineering-flow.json")
STORE_EXTERNAL = ("openapi.json", "pipeline-definition.json")


def _git(*args):
    r = subprocess.run(["git", *args], cwd=_ROOT, capture_output=True, text=True)
    return (r.stdout or "").strip()


def _changed_py():
    files = set()
    base = _git("merge-base", _INTEGRATION, "HEAD")
    if base:
        for ln in _git("diff", "--name-only", base, "HEAD").splitlines():
            files.add(ln.strip())
    for ln in _git("diff", "--name-only", "HEAD").splitlines():
        files.add(ln.strip())
    out = []
    for f in files:
        f = f.replace("\\", "/")
        if not f.endswith(".py") or any(x in f for x in _EXCLUDE):
            continue
        rel = os.path.relpath(os.path.join(_REPO_ROOT, f), _ROOT).replace("\\", "/")
        if rel.startswith(".."):
            continue
        out.append(rel)
    return sorted(out)


def main(argv=None) -> int:
    argparse.ArgumentParser(description="Store-contract on changed files").parse_args(argv)
    reg_path = os.path.join(_ROOT, "config", "store-registry.json")
    try:
        with open(reg_path, encoding="utf-8") as f:
            data = json.load(f)
        known = set((data.get("stores") or {}).keys())
        allow = list(STORE_ALLOW) + list(data.get("allow", []) or [])
    except Exception as e:
        print(f"store-check: SKIP (cannot read store-registry.json: {e})")
        return 0

    exts = "|".join(STORE_EXTS)
    pattern = re.compile(rf'["\']([A-Za-z0-9_\-\./]+\.(?:{exts}))["\']', re.I)

    def allowed(path, base):
        if base in known or path in known or base in STORE_EXTERNAL:
            return True
        return any(fnmatch.fnmatch(path, g) or fnmatch.fnmatch(base, g) for g in allow)

    files = _changed_py()
    unregistered = {}
    for rel in files:
        # the audit tool itself operates on data-file NAMES (registry/allowlist strings), not stores
        if rel.endswith("scripts/dev/wired_audit.py") or rel.endswith("scripts/dev/store_check.py"):
            continue
        p = os.path.join(_ROOT, rel)
        if not os.path.isfile(p):
            continue
        try:
            with open(p, encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except Exception:
            continue
        for lit in set(pattern.findall(text)):
            base = lit.split("/")[-1]
            if allowed(lit, base):
                continue
            unregistered.setdefault(base, set()).add(rel)

    if unregistered:
        print(f"store-check: {len(unregistered)} NEW data file literal(s) NOT registered/allowed")
        for name, mods in sorted(unregistered.items()):
            print(f"   {name:34s} <- {', '.join(sorted(mods))}")
        print("   register (owner+kind+scope) in config/store-registry.json, or add an `allow` glob")
        print("   -> see docs/ADDING-TO-PRODUCT-FORGE.md")
        return 1
    print(f"store-check: OK ({len(files)} changed file(s), all data files registered)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
