"""REL-0 gate: an edition package manifest is fail-closed and distinct per edition.

Builds+validates a scratch-project manifest (no store churn beyond the scratch path), asserts every
REL-0 distinction is populated, editions resolve to different entitlements/deploy targets, and an
unknown edition is rejected. Run: ``python scripts/dev/packaging_check.py``.
"""
import contextlib
import os
import shutil
import sys

try:
    from core.paths import PRODUCTS_DIR as _PRODUCTS
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    _PRODUCTS = os.path.join(_ROOT, "products")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

FAILS = []
_PROJ = "_test_packaging"
_REQUIRED = ("community", "enterprise", "saas", "on-prem", "oem")


def _check(cond, msg):
    if not cond:
        FAILS.append(msg)


def _force_rmtree(p):
    p = str(p)
    if not os.path.exists(p):
        return
    for root, _dirs, files in os.walk(p, topdown=False):
        for name in files:
            with contextlib.suppress(Exception):
                os.chmod(os.path.join(root, name), 0o700)
    shutil.rmtree(p, ignore_errors=True)


def main() -> int:
    from core import packaging
    store = os.path.join(_PRODUCTS, _PROJ)
    _force_rmtree(store)
    os.makedirs(store, exist_ok=True)
    try:
        _check(set(packaging.EDITIONS) == set(_REQUIRED), "all five editions defined")

        # unknown edition is rejected
        bad = packaging.build("project", _PROJ, edition="nope")
        _check(bad.get("ok") is False, "unknown edition rejected")

        # every distinction populated + validation passes
        m = packaging.build("project", _PROJ, edition="enterprise")
        dist = m.get("distinctions") or {}
        for k in packaging.DISTINCTIONS:
            _check(k in dist and dist[k] is not None and not (isinstance(dist[k], dict) and dist[k].get("error")),
                   f"distinction populated: {k}")
        _check(packaging.validate(m).get("valid") is True, "enterprise manifest validates")

        # editions are genuinely distinct (entitlement tier / deploy target differ)
        comm = packaging.build("project", _PROJ, edition="community")
        ent = packaging.build("project", _PROJ, edition="enterprise")
        _check((comm.get("entitlement") or {}).get("tier") != (ent.get("entitlement") or {}).get("tier"),
               "community vs enterprise entitlement tiers differ")
        _check(dist.get("deployment_target", {}).get("target") == "kubernetes",
               "enterprise deploy target = kubernetes")

        # write persists a single manifest without a second store
        w = packaging.write("project", _PROJ, edition="saas")
        _check(w.get("ok") is True, "saas manifest writes ok")
        _check(os.path.exists(packaging.manifest_path("project", _PROJ)), "manifest persisted")
        _check(packaging.load("project", _PROJ).get("edition") == "saas", "manifest round-trips")
    finally:
        _force_rmtree(store)

    if FAILS:
        print("packaging: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("packaging: OK (5 editions, distinctions, fail-closed, single manifest)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
