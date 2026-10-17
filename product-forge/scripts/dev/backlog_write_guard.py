"""Gate (BI-PF-1327 / WG-O3): backlog state is written only through the sanctioned path.

The durable backlog store (``product-forge/data/backlog/**``) has a **single writer** - ``core/backlog.py`` -
and exactly one sanctioned surface for callers: the **backlog API** (``/api/v1/backlog/*``). This gate flags
any OTHER module that reaches the store's PRIVATE writers (``_save_item`` / ``_write_indexes`` / ``_load_all``
/ ``_paths``) instead of going through the API - a bypass of the single-writer contract.

Allowed publishers:
  - ``core/backlog.py``            the owner (single writer)
  - ``api/routers/backlog.py``     the API (the sanctioned read/write surface)
  - ``core/state_checkpoint.py``   checkpoint bookkeeping (allowed)
  - ``core/delivery.py``           delivery bookkeeping (allowed)
  - the merge/reconcile maintenance utilities under ``scripts/dev/``

Advisory first + **baseline-aware**: pre-existing offenders (``_BASELINE``) are grandfathered; only NEW
bypasses warn (``--strict`` makes NEW bypasses fail). Scope: ``product_forge`` (the generated-product
pipeline reuses the same core, so it is covered by the same scan). See
``docs/WORKER-SCHEDULER-OPERATIONS.md`` (session model).

Run: ``python scripts/dev/backlog_write_guard.py [--strict] [--json]``.
"""
import argparse
import json
import os
import re
import sys

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_ROOT = str(_ROOT)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# sanctioned publishers (owner / API / checkpoint / delivery / merge-reconcile maintenance)
_ALLOW = {
    "core/backlog.py",
    "api/routers/backlog.py",
    "core/state_checkpoint.py",
    "core/delivery.py",
    "scripts/dev/pf_merge_driver.py",
    "scripts/dev/backlog_id_reconcile.py",
    "scripts/dev/migrate_backlog_storage.py",
    "scripts/dev/backlog_rebuild_projections.py",  # BI-PF-1399 demotion: regenerates DERIVED projections from the DB
    "scripts/dev/backlog_write_guard.py",  # this gate itself (references the private-writer names)
}
# legacy offenders grandfathered at introduction (BI-PF-1327) - advisory, not fatal
_BASELINE: set = set()

_SCAN_ROOTS = ("core", "api", "adapters", "scripts")
_PRIVATE = ("_save_item", "_write_indexes", "_load_all", "_paths")
# backlog.<private>(...)  (e.g. ``backlog._write_indexes(...)``)
_USE = re.compile(r"\bbacklog\.(" + "|".join(_PRIVATE) + r")\b")
# from core.backlog import _<private>  (direct private import)
_IMPORT = re.compile(r"from\s+core\.backlog\s+import\s+[^\n]*_(save_item|write_indexes|load_all|paths)")


def reaches_private(text: str) -> bool:
    """True when ``text`` reaches the backlog store's private writers (the bypass this gate flags)."""
    return bool(_USE.search(text) or _IMPORT.search(text))


def is_allowed(rel: str) -> bool:
    rel = rel.replace("\\", "/")
    return rel in _ALLOW or rel in _BASELINE


def _iter_py(root: str):
    base = os.path.join(_ROOT, root)
    if not os.path.isdir(base):
        return
    for dp, dn, fn in os.walk(base):
        dn[:] = [d for d in dn if d not in ("__pycache__", "node_modules", ".git")]
        for f in fn:
            if f.endswith(".py"):
                yield os.path.relpath(os.path.join(dp, f), _ROOT).replace("\\", "/")


def offenders() -> list:
    """Files that reach the private writers and are NOT sanctioned (sorted)."""
    out = []
    for root in _SCAN_ROOTS:
        for rel in _iter_py(root):
            if is_allowed(rel):
                continue
            try:
                with open(os.path.join(_ROOT, rel), encoding="utf-8", errors="ignore") as f:
                    text = f.read()
            except Exception:
                continue
            if reaches_private(text):
                out.append(rel)
    return sorted(set(out))


def new_offenders(found) -> list:
    """Offenders that are not grandfathered in the baseline (the ones that count)."""
    return [p for p in found if p not in _BASELINE]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Backlog API-only write guard (BI-PF-1327)")
    ap.add_argument("--strict", action="store_true", help="fail (exit 1) on NEW bypasses")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    found = offenders()
    new = new_offenders(found)
    if a.json:
        print(json.dumps({"offenders": found, "new": new, "strict": bool(a.strict)}, ensure_ascii=False))
    elif new:
        print(f"backlog-write: WARN - {len(new)} module(s) reach the backlog store's private writers "
              f"outside the API/checkpoint/delivery path (advisory):")
        for p in new:
            print("   -", p)
        print("   use the backlog API (api/routers/backlog.py) or a sanctioned path; "
              "see docs/WORKER-SCHEDULER-OPERATIONS.md")
    else:
        print(f"backlog-write: OK (0 new bypasses; {len(found)} non-sanctioned writer(s))")
    return 1 if (a.strict and new) else 0


if __name__ == "__main__":
    raise SystemExit(main())
