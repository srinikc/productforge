"""Neutral vendored-tools resolver — framework-agnostic tool location (BI-0202).

Bundled/large external CLI tools (e.g. draw.io) live OUTSIDE the ``.opencode`` tree in a neutral
``vendor/`` directory. Resolution order: explicit env var -> ``vendor/<name>/<subpath>`` -> PATH.
``.opencode`` is never a default; a legacy path may be consulted only when explicitly allowed.
See docs/VENDORED-TOOLS.md.
"""

import os
import shutil
from typing import Dict, List, Optional

try:
    from core.paths import ROOT as _ROOT
except ImportError:  # script execution
    import sys as _sys
    _d = os.path.abspath(__file__)
    for _ in range(3):
        _d = os.path.dirname(_d)
        if os.path.isfile(os.path.join(_d, "core", "paths.py")):
            _sys.path.insert(0, _d)
            break
    from core.paths import ROOT as _ROOT

# known vendored tools: name -> (subpath within vendor/<name>/, env var override, PATH names)
TOOLS: Dict[str, Dict] = {
    "drawio": {"subpath": os.path.join("drawio", "draw.io.exe"),
               "env": "PIPELINE_DRAWIO_CLI", "path_names": ("drawio", "draw.io", "drawio.exe")},
}


def vendor_dir() -> str:
    """Neutral location for large/3rd-party tool binaries (outside .opencode)."""
    return os.path.join(str(_ROOT), "vendor")


def legacy_allowed() -> bool:
    """Legacy ``.opencode/tools`` is consulted ONLY when explicitly enabled."""
    return str(os.environ.get("ALLOW_OPENCODE_TOOLS_LEGACY", "")).strip().lower() in ("1", "true", "yes")


def _legacy_path(name: str) -> str:
    return os.path.join(str(_ROOT), ".opencode", "tools", TOOLS.get(name, {}).get("subpath", ""))


def resolve_tool(name: str) -> Dict:
    """Resolve a vendored tool. Returns {found, path, source} where source ∈ env|vendor|path|legacy|''.

    Never raises; never defaults to .opencode.
    """
    spec = TOOLS.get(name) or {}
    env_var = str(spec.get("env") or "")
    env = (os.environ.get(env_var) or "").strip() if env_var else ""
    if env and os.path.exists(env):
        return {"found": True, "path": env, "source": "env", "env": env_var}
    sub = str(spec.get("subpath") or "")
    # subpath is already relative to vendor/ (e.g. "drawio/draw.io.exe")
    vend = os.path.join(vendor_dir(), sub) if sub else ""
    if vend and os.path.exists(vend):
        return {"found": True, "path": vend, "source": "vendor", "env": env_var}
    vend2 = os.path.join(vendor_dir(), name, sub) if sub else ""
    if vend2 and os.path.exists(vend2):
        return {"found": True, "path": vend2, "source": "vendor", "env": env_var}
    for pn in (spec.get("path_names") or ()):
        w = shutil.which(pn)
        if w:
            return {"found": True, "path": w, "source": "path", "env": env_var}
    if legacy_allowed():
        lg = _legacy_path(name)
        if os.path.exists(lg):
            return {"found": True, "path": lg, "source": "legacy", "env": env_var}
    return {"found": False, "path": "", "source": "", "env": env_var}


def missing_hint(name: str) -> str:
    """Clear, neutral-location error hint for an unresolved tool."""
    spec = TOOLS.get(name) or {}
    sub = str(spec.get("subpath") or name)
    env_var = str(spec.get("env") or f"PIPELINE_{name.upper()}_CLI")
    return (f"{name} CLI not found. Place it at vendor/{name}/{sub}, or set {env_var}, "
            f"or install '{name}' on PATH. See docs/VENDORED-TOOLS.md.")


def list_tools() -> List[Dict]:
    """Availability of every known vendored tool (for API/discovery)."""
    out = []
    for name in TOOLS:
        r = resolve_tool(name)
        out.append({"name": name, "found": r["found"], "path": r["path"], "source": r["source"]})
    return out
