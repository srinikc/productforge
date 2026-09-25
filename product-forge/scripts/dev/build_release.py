"""Build-time separation of operator vs customer (tenant) packages (BI-0070).

Produces a route manifest for each build role and asserts the tenant build does
NOT contain operator routes. This is the backend half; the frontend half will
emit an operator bundle vs a tenant bundle from the same Next.js codebase.

Usage:
    python scripts/dev/build_release.py            # verify both builds
    python scripts/dev/build_release.py --write    # write dist/build-manifest-<role>.json
"""
try:
    from core.paths import ROOT as _PF_ROOT
except ImportError:  # executed as a script: seed the repo root on sys.path, then retry
    import os as _pf_os
    import sys as _pf_sys
    _pf_d = _pf_os.path.abspath(__file__)
    for _pf_i in range(3):
        _pf_d = _pf_os.path.dirname(_pf_d)
        if _pf_os.path.isfile(_pf_os.path.join(_pf_d, 'core', 'paths.py')):
            _pf_sys.path.insert(0, _pf_d)
            break
    from core.paths import ROOT as _PF_ROOT

import json
import os
import sys
from pathlib import Path

ROOT = _PF_ROOT
sys.path.insert(0, str(ROOT))

OPERATOR_MARKERS = ("/api/v1/licensing/keys", "/api/v1/licensing/tenants",
                    "/api/v1/licensing/trials", "/api/v1/projects/purge-due",
                    "/api/v1/cp/tenants")


def _routes_for(role: str):
    os.environ["BUILD_ROLE"] = role
    for m in list(sys.modules):
        if m.startswith("dashboard.api"):
            del sys.modules[m]
    from dashboard.api import app as a
    paths = sorted({getattr(r, "path", "") for r in a.app.routes if getattr(r, "path", "")})
    return paths


def main():
    write = "--write" in sys.argv
    tenant = _routes_for("tenant")
    operator = _routes_for("operator")
    leaked = [p for p in tenant if p.startswith(OPERATOR_MARKERS)]
    print(f"tenant routes:   {len(tenant)}")
    print(f"operator routes: {len(operator)}")
    print(f"operator leakage in tenant build: {leaked or 'NONE'}")
    if write:
        out = ROOT / "dist"
        out.mkdir(exist_ok=True)
        (out / "build-manifest-tenant.json").write_text(
            json.dumps({"role": "tenant", "routes": tenant}, indent=2), encoding="utf-8")
        (out / "build-manifest-operator.json").write_text(
            json.dumps({"role": "operator", "routes": operator}, indent=2), encoding="utf-8")
        print("wrote dist/build-manifest-{tenant,operator}.json")
    sys.exit(1 if leaked else 0)


if __name__ == "__main__":
    main()
