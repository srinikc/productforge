"""Advisory provider-fallback audit (BI-PF-0247).

OpenCode **Zen** free tier is not API-usable (403 FreeTierError); the working path is
**opencode-go** (`.../zen/go/v1/...`). This audit flags any model-tier profile that routes to the
unusable free Zen endpoint so the fallback stays explicit. Advisory (non-fatal): returns 0.
"""
import json
import os
import sys

try:
    from core.paths import ROOT
except Exception:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
    from core.paths import ROOT

TIER_CFG = os.path.join(str(ROOT), "config", "model-tier.json")
_UNUSABLE_FRAGMENT = "/zen/v1/"  # the free Zen path (no "/go/"); API returns 403


def findings():
    try:
        with open(TIER_CFG, "r", encoding="utf-8-sig") as f:
            cfg = json.load(f) or {}
    except Exception:
        return []
    out = []
    for name, prof in (cfg.get("profiles") or {}).items():
        ep = str((prof or {}).get("api_endpoint") or "")
        if _UNUSABLE_FRAGMENT in ep:
            out.append((name, ep))
    # the top-level default endpoint too
    if _UNUSABLE_FRAGMENT in str(cfg.get("api_endpoint") or ""):
        out.append(("<default>", cfg.get("api_endpoint")))
    return out


def main() -> int:
    bad = findings()
    fallback = os.getenv("PIPELINE_FALLBACK_PROVIDER", "opencode-go")
    if bad:
        print(f"\nprovider-fallback: {len(bad)} profile(s) route to the unusable Zen free endpoint "
              f"(advisory). Working path: provider={fallback} (.../zen/go/v1/...).")
        for name, ep in bad:
            print(f"   {name}: {ep}")
    else:
        print(f"\nprovider-fallback: OK (working fallback provider={fallback})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
