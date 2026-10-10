"""A6 change governance (BI-PF-0395): change classifier + language rule + undeclared-dep policy.

The LOCKED delivery baseline (BI-PF-0387 / ADR BI-PF-0388) says: new shipped/sensitive logic lands in
**Go**; existing Python ships **compiled** (Numba/Nuitka builds are A3's concern); build-time tooling may
stay Python. Until now that rule lived only in prose - this module makes it mechanically checkable:

* ``classify_file``     - area of any changed path: shipped | shipped-sensitive | go | tooling | test |
                          config | data | docs | legacy | external | unknown (drift guard's foundation).
* ``language_rule_findings``     - NEW ``.py`` under a shipped root (outside the declared allowlist) violates
                                   the language rule. EDITS to existing shipped Python are compliant (they
                                   stay compiled); new Go files are always compliant.
* ``undeclared_import_findings`` - a changed shipped ``.py`` importing a third-party module that is not in
                                   the declared dependency set (pyproject ``dependencies`` + extras, with an
                                   import-alias map) fails. Complements BI-PF-0443
                                   (dependency_catalog_check): that gate covers new DECLARED deps needing a
                                   tool-catalog entry; this covers imports that were NEVER declared.
* ``drift_report`` - the gate's advisory line (added Go vs new shipped Python vs undeclared deps).

Fail-closed: a ``.py`` added under an UNKOWN top-level path is flagged (unclassified - placement rules
forbid new top-level directories, AGENTS.md #5), and an unparseable shipped file is flagged.

Single writer for the policy config ``config/language-rule.json`` (registered in store-registry): this
module only READS it. Enforcement + changed-file plumbing live in ``scripts/dev/language_rule_check.py``
(author-time/precheck gate); this module is pure (stdlib only).

The legacy dashboard (BI-PF-1223) is exempt: never grown, only retired.
"""
import ast
import json
import os
import sys
from typing import Any, Iterable

from core.paths import ROOT

_CONFIG = os.path.join(str(ROOT), "config", "language-rule.json")
_PYPROJECT = os.path.join(str(ROOT), "pyproject.toml")

# import-name -> distribution package (only where they differ)
IMPORT_ALIASES = {
    "yaml": "pyyaml", "PIL": "pillow", "bs4": "beautifulsoup4", "dotenv": "python-dotenv",
    "dateutil": "python-dateutil", "sklearn": "scikit-learn", "cv2": "opencv-python",
    "docx": "python-docx", "pptx": "python-pptx", "Crypto": "pycryptodome", "fitz": "pymupdf",
    "attr": "attrs", "serial": "pyserial", "pkg_resources": "setuptools",
}

_DEFAULTS: dict[str, Any] = {
    "shipped_roots": ["core/", "api/", "adapters/"],
    "sensitive_roots": [],
    "allow_new_python": ["core/change_policy.py"],
    "legacy_exempt_roots": ["dashboard/"],
    "go_roots": ["go/"],
    "tooling_roots": ["scripts/", "config/", "data/", "docs/", "products/", ".opencode/",
                      "templates/", "pipeline_templates/", "security/", "issues/",
                      "engineering/", "pipeline/", "test-framework/"],
    "escape_env": "PF_ALLOW_PY_SHIPPED",
}

_loaded: dict[str, Any] | None = None


def policy(force_reload: bool = False) -> dict[str, Any]:
    """The language-rule config (defaults merged; cached per process)."""
    global _loaded
    if _loaded is not None and not force_reload:
        return _loaded
    p = dict(_DEFAULTS)
    try:
        with open(_CONFIG, encoding="utf-8-sig") as f:
            data = json.load(f)
        for k in _DEFAULTS:
            if isinstance(data.get(k), list):
                p[k] = data[k]
    except FileNotFoundError:
        pass  # defaults remain: fail-closed via shipped_roots, never a crash
    except Exception:
        pass
    _loaded = p
    return p


def normalize(path: str) -> str:
    p = str(path or "").replace("\\", "/").strip("/")
    for pre in ("product-forge/", "./"):
        if p.startswith(pre):
            p = p[len(pre):]
    return p


def _starts(p: str, prefixes: Iterable[str]) -> bool:
    return any(p == str(x).strip("/") or p.startswith(str(x)) for x in prefixes)


def classify_file(path: str, pol: dict[str, Any] | None = None) -> dict[str, Any]:
    """Area + sensitivity of one (normalized) repo path. Unknown stays 'unknown' (fail-closed).

    Priority: test > legacy > go > shipped-sensitive > shipped > tooling > external > unknown.
    """
    pol = pol or policy()
    p = normalize(path)
    out: dict[str, Any] = {"path": p, "area": "unknown", "sensitive": False, "py": p.endswith(".py")}
    if not p:
        return out
    base = os.path.basename(p)
    if base.startswith("test_") or base == "conftest.py" or p.startswith("test-framework/") \
            or "/tests/" in f"/{p}" or p.startswith("tests/"):
        out["area"] = "test"
        return out
    if _starts(p, pol["legacy_exempt_roots"]):
        out["area"] = "legacy"
        return out
    if _starts(p, pol["go_roots"]) or p.endswith(".go"):
        out["area"] = "go"
        return out
    if _starts(p, pol["sensitive_roots"]):
        out["area"], out["sensitive"] = "shipped", True
        return out
    if _starts(p, pol["shipped_roots"]):
        out["area"] = "shipped"
        return out
    if _starts(p, pol["tooling_roots"]) or p.startswith(".opencode/"):
        out["area"] = "tooling"
        return out
    head = p.split("/", 1)[0] + "/" if "/" in p else ""
    if head and head not in {"core/", "api/", "adapters/", "go/", "dashboard/", "docs/",
                             "config/", "data/", "scripts/", "products/", "tests/"}:
        out["area"] = "external" if head == "workergrid/" else "unknown"
    return out


def language_rule_findings(changed: Iterable[str], added: Iterable[str],
                           pol: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """NEW ``.py`` under a shipped root, outside the declared allowlist, violates the language rule."""
    pol = pol or policy()
    findings: list[dict[str, Any]] = []
    for a in sorted(set(added)):
        c = classify_file(a, pol)
        if c["area"] != "shipped" or not c["py"]:
            continue
        p = c["path"]
        if p in {normalize(x) for x in pol["allow_new_python"]}:
            continue
        # no __init__.py exemption: a shipped package's __init__ can carry real code - fail-closed.
        findings.append({
            "rule": "language-rule", "path": p, "sensitive": c["sensitive"],
            "detail": ("new shipped%s Python module: new shipped/sensitive logic must land in Go "
                       "(BI-PF-0387/0388); edits to existing shipped Python remain allowed"
                       % ("-sensitive" if c["sensitive"] else ""))
            + " | set PF_ALLOW_PY_SHIPPED=1 (worker: --allow-py-shipped) to record a reasoned exception",
        })
    return findings


def unclassified_findings(added: Iterable[str], pol: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Fail-closed placement guard: a new ``.py`` under an unclassified top-level path."""
    pol = pol or policy()
    out = []
    for a in sorted(set(added)):
        c = classify_file(a, pol)
        if c["py"] and c["area"] == "unknown":
            out.append({"rule": "unclassified-path", "path": c["path"],
                        "detail": "new Python file under an unrecognized root - placement per AGENTS.md #5; "
                                 "extend config/language-rule.json roots deliberately (reviewed change)"})
    return out


def _declared_imports() -> set[str]:
    """Normalized distribution names from pyproject (dependencies + all extras)."""
    names: set[str] = set()
    try:
        with open(_PYPROJECT, encoding="utf-8") as f:
            text = f.read()
    except Exception:
        return names
    in_deps = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith(("dependencies", "])")):
            in_deps = s.startswith("dependencies")
            continue
        if in_deps and s.startswith("["):
            in_deps = False
        if in_deps:
            tok = s.strip("\"',[]").strip()
            m = tok.split("=")[0].split("<")[0].split(">")[0].split("!")[0].split("[")[0].strip()
            if m:
                names.add(m.lower().replace("-", "_"))
    return names


def _first_party() -> set[str]:
    try:
        return {d for d in os.listdir(str(ROOT)) if os.path.isdir(os.path.join(str(ROOT), d))}
    except Exception:
        return set()


def top_level_imports(source: str) -> list[str]:
    """Unique top-level module names imported by a source file (absolute imports only)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    mods: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods += [(a.name or "").split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                mods.append(node.module.split(".")[0])
    return sorted(set(m for m in mods if m))


def undeclared_import_findings(sources: dict[str, str],
                               pol: dict[str, Any] | None = None,
                               declared: set[str] | None = None) -> list[dict[str, Any]]:
    """Changed shipped ``.py`` files importing third-party modules absent from the declared deps.

    ``declared`` may be injected (tests); default reads pyproject (deps + extras, normalized).
    """
    pol = pol or policy()
    declared = declared if declared is not None else _declared_imports()
    first_party = _first_party()
    stdlib = set(getattr(sys, "stdlib_module_names", set())) | {"__future__"}
    findings = []
    for path, src in sorted(sources.items()):
        c = classify_file(path, pol)
        if c["area"] != "shipped" or not c["py"]:
            continue
        try:
            ast.parse(src)  # fail-closed: unparseable shipped file
        except SyntaxError as e:
            findings.append({"rule": "undeclared-dep", "path": c["path"],
                             "detail": f"unparseable shipped file (fail-closed): {e}"})
            continue
        for mod in top_level_imports(src):
            if mod in stdlib or mod in first_party:
                continue
            pkg = IMPORT_ALIASES.get(mod, mod).lower().replace("-", "_")
            if pkg in declared:
                continue
            findings.append({
                "rule": "undeclared-dep", "path": c["path"],
                "detail": f"import '{mod}' is not a declared runtime dependency "
                          "(pyproject dependencies/extras); declare it AND add the tool-catalog entry "
                          "(BI-PF-0443), or import via an existing owner",
            })
    return findings


def check(changed: Iterable[str], added: Iterable[str], sources: dict[str, str],
          pol: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """All policy findings in one call (gate consumes this)."""
    pol = pol or policy()
    return (language_rule_findings(changed, added, pol)
            + unclassified_findings(added, pol)
            + undeclared_import_findings(sources, pol))


def drift_report(added: Iterable[str], findings: list[dict[str, Any]],
                 pol: dict[str, Any] | None = None) -> dict[str, int]:
    """The gate's advisory line: Go growth vs new shipped Python vs violations."""
    pol = pol or policy()
    areas = [classify_file(a, pol)["area"] for a in set(added)]
    return {
        "added_go": areas.count("go"),
        "added_shipped_python_new": sum(1 for f in findings if f["rule"] == "language-rule"),
        "undeclared_deps": sum(1 for f in findings if f["rule"] == "undeclared-dep"),
        "unclassified": sum(1 for f in findings if f["rule"] == "unclassified-path"),
    }
