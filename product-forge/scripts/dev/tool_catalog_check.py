"""BI-0211 fail-closed gate: the tool catalog is consistent, and nothing that ships is non-bundle_allowed.

Fatal if any bundled component's license_class is not bundle_allowed (or any schema/class mismatch), so a
non-redistributable component can never be packaged. Wired into ``precheck``.
"""
import os
import sys

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core import tool_catalog  # noqa: E402


def main(argv=None) -> int:
    probs = tool_catalog.validate()
    ents = tool_catalog.entries()
    if probs:
        print(f"tool-catalog: FAIL ({len(probs)} problem(s) across {len(ents)} entries)")
        for p in probs[:20]:
            print("   -", p)
        return 1
    bundled = [e["name"] for e in ents if e.get("bundled")]
    print(f"tool-catalog: OK ({len(ents)} entries; {len(bundled)} bundled all bundle_allowed; "
          f"{len(ents) - len(bundled)} invoked/self-host/api)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
