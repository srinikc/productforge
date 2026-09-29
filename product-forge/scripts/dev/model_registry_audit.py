"""Advisory model-registry freshness + tier/catalog drift audit (BI-PF-0246).

Surfaces (a) whether the live capability catalog is stale and (b) models referenced by
config/model-tier.json that are absent from the catalog or whose records lack
context_window/tools. Advisory (non-fatal): returns 0.
"""
import json
import os
import sys

try:
    from core.paths import ROOT
    from core import model_catalog as _mc
except Exception:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
    from core.paths import ROOT
    from core import model_catalog as _mc

TIER_CFG = os.path.join(str(ROOT), "config", "model-tier.json")


def _tier_models() -> set:
    try:
        with open(TIER_CFG, "r", encoding="utf-8-sig") as f:
            cfg = json.load(f) or {}
    except Exception:
        return set()
    names = set()
    for a in (cfg.get("agents") or {}).values():
        if (a or {}).get("model"):
            names.add(a["model"])
    for s in (cfg.get("stages") or {}).values():
        if (s or {}).get("model"):
            names.add(s["model"])
    for prof in (cfg.get("profiles") or {}).values():
        for m in ((prof or {}).get("models") or {}):
            names.add(m)
        if (prof or {}).get("default_model"):
            names.add(prof["default_model"])
    return names


def main() -> int:
    try:
        reg = _mc.load() or {}
        records = reg.get("models") or reg.get("data") or {}
    except Exception:
        records = {}
    if isinstance(records, list):
        records = {r.get("id") or r.get("name"): r for r in records if isinstance(r, dict)}
    known = set(records.keys())
    tier_models = _tier_models()
    missing = sorted(m for m in tier_models if m and m not in known)
    incomplete = sorted(
        m for m, r in records.items()
        if isinstance(r, dict) and (not r.get("context_window") or "tools" not in r))[:20]
    try:
        stale = _mc.is_stale()
    except Exception:
        stale = None
    print(f"\nmodel-registry: catalog={'STALE' if stale else 'fresh' if stale is not None else 'unknown'} "
          f"records={len(known)}")
    if missing:
        print(f"   {len(missing)} tier model(s) not in catalog: {missing[:10]}")
    if incomplete:
        print(f"   {len(incomplete)} catalog record(s) missing context_window/tools (sample): {incomplete[:5]}")
    if not missing and not incomplete:
        print("   no drift detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
