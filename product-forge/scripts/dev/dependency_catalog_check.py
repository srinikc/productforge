"""BI-PF-0443 fail-closed gate: a NEW dependency (manifest diff) must have a tool-catalog entry.

Changed-file scoped (mirrors scripts/dev/store_check.py): diffs PF's OWN dependency manifests (product-forge/
pyproject.toml + requirements*.txt + setup.py; workergrid/go.mod; .opencode/package.json) against the merge-base
with ``develop`` plus the working tree. Any dependency that is ADDED must resolve via
``core.tool_catalog.lookup`` (name or ``manifest_names`` alias) -> else FAIL, unless ``PF_ALLOW_UNCATALOGUED=1``.

No new API: the catalog is already read-exposed via ``GET /api/v1/tools/catalog`` (BI-0211).
"""
import argparse
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

from core import tool_catalog  # noqa: E402

INTEGRATION = "develop"
MANIFESTS = ("product-forge/pyproject.toml", "product-forge/requirements.txt", "product-forge/setup.py",
             "product-forge/.opencode/package.json", "workergrid/go.mod")


def _git(*args) -> str:
    r = subprocess.run(["git", *args], cwd=_ROOT, capture_output=True, text=True)
    return (r.stdout or "").strip()


def _norm(name: str) -> str:
    return str(name or "").strip().lower()


def parse_toml_deps(text: str) -> set:
    deps, in_dep = set(), False
    for ln in (text or "").splitlines():
        s = ln.strip()
        if s.startswith("dependencies") and "[" in s:
            in_dep = True
            continue
        if in_dep:
            if s.startswith("]"):
                in_dep = False
                continue
            m = re.match(r'"([^"<>=!~ ;]+)', s)
            if m:
                deps.add(_norm(m.group(1)))
    return deps


def parse_setup_deps(text: str) -> set:
    m = re.search(r"install_requires\s*=\s*\[(.*?)\]", text or "", re.S)
    return {_norm(d) for d in re.findall(r'"([^"<>=!~ ;]+)', m.group(1))} if m else set()


def parse_package_json(text: str) -> set:
    try:
        d = json.loads(text or "{}")
    except Exception:
        return set()
    out = set()
    for k in ("dependencies", "devDependencies"):
        out |= {_norm(x) for x in (d.get(k) or {})}
    return out


def parse_go_mod(text: str) -> set:
    deps, in_req = set(), False
    for ln in (text or "").splitlines():
        s = ln.strip()
        if s.startswith("require ("):
            in_req = True
            continue
        if in_req and s == ")":
            in_req = False
            continue
        if in_req and "// indirect" not in s:
            parts = s.split()
            if parts:
                deps.add(_norm(parts[0]))
    return deps


def parse_requirements(text: str) -> set:
    out = set()
    for ln in (text or "").splitlines():
        s = ln.strip()
        if s and not s.startswith("#") and not s.startswith("-"):
            m = re.match(r"([A-Za-z0-9_.\-]+)", s)
            if m:
                out.add(_norm(m.group(1)))
    return out


def parse_deps(path: str, text: str) -> set:
    if path.endswith(".toml"):
        return parse_toml_deps(text)
    if path.endswith("setup.py"):
        return parse_setup_deps(text)
    if path.endswith("package.json"):
        return parse_package_json(text)
    if path.endswith("go.mod"):
        return parse_go_mod(text)
    if path.endswith(".txt"):
        return parse_requirements(text)
    return set()


def missing_from_catalog(names) -> list:
    return [n for n in sorted(set(names)) if not tool_catalog.lookup(n)]


def added_deps() -> set:
    base = _git("merge-base", INTEGRATION, "HEAD")
    added = set()
    for m in MANIFESTS:
        try:
            with open(os.path.join(_ROOT, m), encoding="utf-8") as f:
                cur = f.read()
        except Exception:
            continue
        old = _git("show", f"{base}:{m}") if base else ""
        added |= (parse_deps(m, cur) - parse_deps(m, old))
    return added


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    opts = ap.parse_args(argv)
    if str(os.environ.get("PF_ALLOW_UNCATALOGUED", "")).strip().lower() in ("1", "true", "yes"):
        print("dependency-catalog: OK (PF_ALLOW_UNCATALOGUED override)")
        return 0
    added = added_deps()
    if opts.list:
        print(sorted(added))
        return 0
    missing = missing_from_catalog(added)
    if missing:
        print(f"dependency-catalog: FAIL ({len(missing)} newly added dependency(ies) with no catalog entry):")
        for m in missing:
            print("   -", m)
        print("   add an entry (name + license_class + bundle_allowed) in config/tool-catalog.json")
        return 1
    print(f"dependency-catalog: OK ({len(added)} added dependency(ies), all catalogued)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
