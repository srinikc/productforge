"""BI-PF-1066 (E9) backfill: give OPEN items an ``api_impact`` decision derived from their OWN declared data.

Honest + non-fabricating: an item that declares ``route:/api/v1/...`` in ``links.backend_capability`` ->
``needs_api=true`` with those routes; otherwise ``needs_api=false`` (no API surface declared). Idempotent;
items that already have a decision are left untouched. ``--write`` applies (dry-run otherwise).
"""
import argparse
import os
import sys

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core import backlog  # noqa: E402


def _routes(it: dict) -> list:
    caps = ((it.get("links") or {}).get("backend_capability")) or []
    if isinstance(caps, str):
        caps = [caps]
    return [c.split(":", 1)[1].strip() for c in caps if isinstance(c, str) and c.startswith("route:")]


def decide(it: dict) -> dict:
    routes = _routes(it)
    if routes:
        return {"needs_api": True, "routes": routes, "consumers": ["internal"],
                "reason": "route(s) declared in links.backend_capability"}
    return {"needs_api": False, "routes": [], "consumers": [],
            "reason": "no API surface declared in backend_capability"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    changed = 0
    for it in backlog.list_open("product_forge", None):
        if it.get("api_impact"):
            continue
        backlog.update("product_forge", None, it["id"], api_impact=decide(it)) if a.write else None
        changed += 1
    print(f"backfill-api-impact: {'WROTE' if a.write else 'would set'} {changed} item(s); "
          f"remaining warnings={len(backlog.api_impact_warnings())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
