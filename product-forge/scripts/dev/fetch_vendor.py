"""Place/verify a neutral vendored tool (BI-0202). Prints the neutral target + how to obtain it.

Idempotent; performs no network calls itself (prints the download command) so it is safe in CI.
Run: python scripts/dev/fetch_vendor.py [tool|--list]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core import vendor  # noqa: E402

_HINTS = {
    "drawio": ("draw.io desktop (headless export). Download the desktop release and place 'draw.io.exe' "
               "at the target path, or set PIPELINE_DRAWIO_CLI, or install drawio on PATH."),
}


def main() -> int:
    ap = argparse.ArgumentParser(description="Resolve/place a neutral vendored tool")
    ap.add_argument("tool", nargs="?", help="tool name (e.g. drawio)")
    ap.add_argument("--list", action="store_true", help="list known tools + resolution status")
    args = ap.parse_args()

    if args.list or not args.tool:
        for t in vendor.list_tools():
            print(f"{t['name']}: found={t['found']} source={t['source'] or '-'} path={t['path'] or '-'}")
        return 0

    name = args.tool
    r = vendor.resolve_tool(name)
    if r["found"]:
        print(f"{name}: OK (source={r['source']}) -> {r['path']}")
        return 0
    print(f"{name}: NOT FOUND")
    print(vendor.missing_hint(name))
    if name in _HINTS:
        print("How to obtain:", _HINTS[name])
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
