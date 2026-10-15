"""API-first retrofit triage (BI-PF-1406, Slice 2).

For every open item lacking an ``api_impact`` decision, propose one and (with ``--apply``) record it via the
backlog HTTP API (single writer) so decisions are API-only.

Policy (conservative):
  - item declares routes in ``links.backend_capability`` -> needs_api=true (with those routes);
  - otherwise -> needs_api=false with an explicit reason (no external API consumer recorded); a human flips
    it to true (with routes) when an API is actually required.

Reads go through ``core.backlog`` (read-only); writes go ONLY through the API.

Usage:
  python scripts/dev/api_impact_triage.py            # dry-run (prints proposals)
  python scripts/dev/api_impact_triage.py --apply    # write decisions via the API
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

NO_NEED_REASON = ("retrofit assessment (ADR-0007): no external API consumer recorded; treated as internal "
                  "until an API surface is required (then set needs_api=true with routes)")


def _routes_of(item: dict) -> list[str]:
    bc = (item.get("links") or {}).get("backend_capability")
    if isinstance(bc, dict):
        routes = bc.get("routes") or bc.get("route") or []
    elif isinstance(bc, list):
        routes = bc
    elif isinstance(bc, str):
        routes = [bc]
    else:
        routes = []
    if isinstance(routes, str):
        routes = [routes]
    return [str(r) for r in routes if str(r).strip()]


def propose(item: dict) -> dict:
    routes = _routes_of(item)
    if routes:
        return {"needs_api": True, "reason": "declared API surface (links.backend_capability)", "routes": routes}
    return {"needs_api": False, "reason": NO_NEED_REASON, "routes": []}


def _post(base: str, token: str, item_id: str, decision: dict) -> None:
    data = json.dumps(decision).encode("utf-8")
    req = urllib.request.Request(f"{base}/backlog/items/{item_id}/api-impact", data=data, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Roles", "operator")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{item_id} -> HTTP {e.code}: {e.read().decode('utf-8', 'replace')}") from None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Record api_impact decisions for open items (via the API).")
    ap.add_argument("--scope", default="product_forge")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--api-url", default=os.environ.get("PF_API_URL", "http://127.0.0.1:8010/api/v1"))
    ap.add_argument("--token", default="")
    a = ap.parse_args(argv)

    from core import backlog

    items = [it for it in backlog.list_open(a.scope) if not it.get("api_impact")]
    proposals = [(it.get("id"), propose(it)) for it in items]
    need = [i for i, p in proposals if p["needs_api"]]
    print(f"api-impact triage: {len(proposals)} item(s) lack a decision; needs_api=true: {len(need)}")
    for i, p in proposals[:15]:
        print(f"   {i}: needs_api={p['needs_api']}")
    if not a.apply:
        print("(dry-run; pass --apply to write via the API)")
        return 0

    token = a.token or os.environ.get("PF_API_TOKEN", "")
    if not token:
        tf = ROOT / "data" / "local" / "dev-api-token"
        token = tf.read_text(encoding="utf-8").strip() if tf.is_file() else ""
    if not token:
        print("no API token", file=sys.stderr)
        return 2
    ok = 0
    for item_id, decision in proposals:
        try:
            _post(a.api_url, token, str(item_id), decision)
            ok += 1
        except RuntimeError as e:
            print(f"   FAIL {e}", file=sys.stderr)
    print(f"api-impact triage: applied {ok}/{len(proposals)} decisions via the API")
    return 0 if ok == len(proposals) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
