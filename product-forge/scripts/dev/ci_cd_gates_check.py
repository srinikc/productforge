"""CI/CD gate registry guard (BI-PF-1239).

Single truth = ``scripts/dev/precheck.py::_GATES`` (the mechanical gate list). This script keeps the
DERIVED registry ``config/ci-cd-gates.json`` in lock-step with it so ``core/ci_cd_model.py`` (and the read
API) can serve the gate catalog WITHOUT ``core`` importing ``scripts`` and WITHOUT a second truth.

  python scripts/dev/ci_cd_gates_check.py --write   # regenerate the registry from precheck._GATES
  python scripts/dev/ci_cd_gates_check.py           # verify (fatal on drift)  [default]

Run from product-forge/. Exit 0 = in sync, 1 = drift.
"""
import argparse
import importlib.util
import json
import os
import sys

if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

from core.paths import ROOT  # noqa: E402

_CONFIG = os.path.join(str(ROOT), "config", "ci-cd-gates.json")
_TIERS = {
    "fast": "per-change / per-phase",
    "deep": "merge / CI (precheck --full)",
    "release": "periodic full-tree sweeps (precheck --release)",
}


def _load_precheck():
    """Load scripts/dev/precheck.py as a module (no main() side effects)."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "precheck.py")
    spec = importlib.util.spec_from_file_location("_pf_precheck_gates", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build() -> dict:
    """The registry projection of precheck._GATES."""
    mod = _load_precheck()
    gates = []
    for entry in mod._GATES:
        name, cmd, tier, area = entry
        gates.append({"id": str(name), "cmd": [str(c) for c in cmd], "tier": str(tier),
                      "area": list(area) if area else None, "blocking": True})
    return {
        "$schema": "ci-cd-gates-v1",
        "description": "DERIVED mechanical gate registry - projection of scripts/dev/precheck.py::_GATES. "
                       "Single truth = precheck._GATES; kept in lock-step by scripts/dev/ci_cd_gates_check.py.",
        "source": "scripts/dev/precheck.py::_GATES",
        "generated": True,
        "tiers": _TIERS,
        "gates": gates,
    }


def _read_config() -> dict:
    try:
        with open(_CONFIG, encoding="utf-8-sig") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _norm(d: dict) -> dict:
    return {"tiers": d.get("tiers"), "gates": d.get("gates")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="CI/CD gate registry guard (BI-PF-1239)")
    ap.add_argument("--write", action="store_true", help="regenerate config/ci-cd-gates.json")
    a = ap.parse_args(argv)
    want = build()
    if a.write:
        os.makedirs(os.path.dirname(_CONFIG), exist_ok=True)
        with open(_CONFIG, "w", encoding="utf-8", newline="\n") as f:
            json.dump(want, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"ci-cd-gates: wrote {len(want['gates'])} gate(s) -> config/ci-cd-gates.json")
        return 0
    have = _read_config()
    if _norm(have) != _norm(want):
        hg = {g.get("id"): g for g in (have.get("gates") or [])}
        wg = {g.get("id"): g for g in want["gates"]}
        missing = sorted(set(wg) - set(hg))
        extra = sorted(set(hg) - set(wg))
        changed = sorted(k for k in (set(hg) & set(wg)) if hg[k] != wg[k])
        print("ci-cd-gates: FAIL - config/ci-cd-gates.json is stale vs precheck._GATES")
        if missing:
            print("   missing gates:", missing)
        if extra:
            print("   extra gates  :", extra)
        if changed:
            print("   changed gates:", changed)
        print("   regenerate: python scripts/dev/ci_cd_gates_check.py --write")
        return 1
    # the model (the reader) must actually surface the registry (also keeps core.ci_cd_model reachable)
    try:
        from core import ci_cd_model
        model = ci_cd_model.load()
    except Exception as e:  # noqa: BLE001
        print(f"ci-cd-gates: FAIL - core.ci_cd_model.load() failed: {type(e).__name__}: {e}")
        return 1
    if len(model.get("mechanical_gates") or []) != len(want["gates"]):
        print("ci-cd-gates: FAIL - core.ci_cd_model does not read the registry (count mismatch)")
        return 1
    print(f"ci-cd-gates: OK ({len(want['gates'])} gates in sync with precheck._GATES; model reads registry)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
