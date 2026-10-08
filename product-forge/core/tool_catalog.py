"""Tool / SDK / vendor / generator catalog (BI-0211) - single writer + reader.

One machine-readable record of every third-party *tool* PF uses, with its license class and whether it may be
**bundled** (shipped in PF's package) vs only *invoked* (user-installed binary) or *self-hosted* (operator-run
service) or *called as an API* (BYO-key). Models are catalogued separately (``config/model-catalog.json``,
BI-0206) - this catalog links to them, it does not duplicate them.

Consumers: ``scripts/dev/tool_catalog_check.py`` (fail-closed gate) and ``GET /api/v1/tools/catalog``.
Owner/single writer: this module.
"""
import json
import os
from typing import Any, Dict, List, Optional

from core.paths import ROOT

OUT = os.path.join(str(ROOT), "config", "tool-catalog.json")

# license class -> may PF ship (bundle) a component under this class?
CLASS_BUNDLE_ALLOWED = {
    "permissive": True,
    "weak-copyleft": False,     # LGPL: allowed only if unmodified/linked (recorded per-entry override)
    "strong-copyleft": False,
    "network-copyleft": False,
    "restricted": False,
    "proprietary": False,
}
# license id -> class. Unknown ids are fail-closed to "restricted".
KNOWN_LICENSES = {
    "MIT": "permissive", "BSD-2-Clause": "permissive", "BSD-3-Clause": "permissive",
    "Apache-2.0": "permissive", "ISC": "permissive", "PSF-2.0": "permissive", "Python-2.0": "permissive",
    "0BSD": "permissive", "Unlicense": "permissive", "MPL-2.0": "weak-copyleft",
    "LGPL-2.1": "weak-copyleft", "LGPL-3.0": "weak-copyleft",
    "GPL-2.0": "strong-copyleft", "GPL-3.0": "strong-copyleft", "AGPL-3.0": "network-copyleft",
    "proprietary": "proprietary", "service": "proprietary",
}
VALID_CLASSES = set(CLASS_BUNDLE_ALLOWED)
VALID_KINDS = {"agent-tool", "runtime-bin", "python-lib", "node-lib", "self-host-engine",
               "cloud-api", "sdk", "generator"}
VALID_SOURCES = {"pypi", "system", "api", "self-host", "npm"}


def license_class(license_id: str) -> str:
    """Map a license id to its class; unknown -> 'restricted' (fail-closed)."""
    return KNOWN_LICENSES.get(str(license_id or "").strip(), "restricted")


def class_bundle_allowed(cls: str) -> bool:
    return bool(CLASS_BUNDLE_ALLOWED.get(cls, False))


def load() -> Dict[str, Any]:
    try:
        with open(OUT, encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {"entries": []}


def entries() -> List[Dict[str, Any]]:
    return list(load().get("entries") or [])


def lookup(name: str) -> Optional[Dict[str, Any]]:
    n = str(name or "").strip().lower()
    for e in entries():
        if str(e.get("name", "")).strip().lower() == n:
            return e
    return None


def effective_bundle_allowed(entry: Dict[str, Any]) -> bool:
    """The entry's own decision, defaulting to the class rule; an explicit override wins."""
    if "bundle_allowed" in entry and entry["bundle_allowed"] is not None:
        return bool(entry["bundle_allowed"])
    return class_bundle_allowed(license_class(entry.get("license_id", "")))


def validate() -> List[str]:
    """Return a list of problems (empty == consistent). Fail-closed on any unknown field value."""
    problems: List[str] = []
    seen = set()
    for e in entries():
        nm = str(e.get("name", "")).strip()
        if not nm:
            problems.append("entry with empty name")
            continue
        if nm.lower() in seen:
            problems.append(f"{nm}: duplicate name")
        seen.add(nm.lower())
        cls = str(e.get("license_class", ""))
        if cls not in VALID_CLASSES:
            problems.append(f"{nm}: invalid license_class {cls!r}")
        if str(e.get("kind", "")) not in VALID_KINDS:
            problems.append(f"{nm}: invalid kind {e.get('kind')!r}")
        if str(e.get("source", "")) not in VALID_SOURCES:
            problems.append(f"{nm}: invalid source {e.get('source')!r}")
        expect = license_class(e.get("license_id", ""))
        if cls != expect:
            problems.append(f"{nm}: license_class {cls!r} != class for license_id {e.get('license_id')!r} ({expect})")
        if bool(e.get("bundled")) and not effective_bundle_allowed(e):
            problems.append(f"{nm}: bundled but license_class {cls!r} is not bundle_allowed "
                            f"(set bundle_allowed=true with a recorded reason, or bundled=false)")
    return problems


def write(data: Dict[str, Any]) -> None:
    """Single-writer entry point (used by tooling/tests). Atomic."""
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, OUT)
