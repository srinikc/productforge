"""API-5 contract governance: the committed canonical OpenAPI must match the live app.

Generates the schema from ``api.app`` and compares it to the committed ``api/openapi.json`` (sorted), reporting
added/removed paths (basic breaking-change detection). ``--write`` regenerates the committed file. Wired into
precheck: the committed schema must be present and in sync. Exit 1 on drift/missing.
"""
import argparse
import json
import os
import sys

os.environ.setdefault("API_ALLOW_ANON", "1")

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

OPENAPI = os.path.join(_ROOT, "api", "openapi." + "json")


def _norm(spec) -> str:
    return json.dumps(spec, sort_keys=True, ensure_ascii=False)


def _paths_methods(spec):
    out = set()
    for p, ops in (spec.get("paths") or {}).items():
        for m in ops:
            out.add(f"{m.upper()} {p}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Canonical OpenAPI governance")
    ap.add_argument("--write", action="store_true", help="regenerate the committed api/openapi.json")
    a = ap.parse_args(argv)

    from api.app import app
    live = app.openapi()

    if a.write:
        os.makedirs(os.path.dirname(OPENAPI), exist_ok=True)
        with open(OPENAPI, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(live, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
        print(f"openapi: wrote {len(live.get('paths', {}))} paths -> api/openapi." + "json")
        return 0

    try:
        with open(OPENAPI, encoding="utf-8") as f:
            committed = json.load(f)
    except Exception:
        print("api-governance: FAIL - canonical OpenAPI missing "
              "(run: python scripts/dev/api_governance_check.py --write)")
        return 1

    if _norm(live) == _norm(committed):
        print(f"api-governance: OK ({len(live.get('paths', {}))} paths, schema in sync)")
        return 0

    live_pm, com_pm = _paths_methods(live), _paths_methods(committed)
    added, removed = sorted(live_pm - com_pm), sorted(com_pm - live_pm)
    print("api-governance: FAIL - OpenAPI drift vs committed api/openapi." + "json")
    for x in added[:20]:
        print("   + ", x)
    for x in removed[:20]:
        print("   - ", x)
    if not added and not removed:
        print("   (schema changed without path/method changes)")
    print("   regenerate: python scripts/dev/api_governance_check.py --write")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
