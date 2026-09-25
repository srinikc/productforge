"""Migrate backlog storage: legacy full-array layout -> items/<ID>.json (truth) + derived indexes.

Idempotent + re-runnable. Converts every scope:
  * writes one file per item to `backlog/items/<ID>.json`
  * regenerates the DERIVED lean `open.json` / `closed.json` indexes
  * leaves `history/<ID>.jsonl` in place (unchanged)

Safe: only ADDS items/ files and REWRITES the (derived) index files; it never deletes items.
A backup should be taken before running (see the task log / backup dir).

Usage: python scripts/dev/migrate_backlog_storage.py [--scope product_forge|<project>] [--verify]
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

import os
import sys

sys.path.insert(0, str(_PF_ROOT))

from core import backlog  # noqa: E402


def _counts(scope, project):
    op, cl = backlog._load_all(scope, project)
    return len(op) + len(cl)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Migrate backlog storage to per-item files + derived index.")
    ap.add_argument("--scope", default="", help="product_forge | <project> (default: all scopes)")
    ap.add_argument("--verify", action="store_true", help="verify item counts after migration")
    a = ap.parse_args(argv)

    if a.scope:
        scopes = [("project", a.scope)] if a.scope != "product_forge" else [("product_forge", None)]
    else:
        scopes = backlog._all_scopes()
    # only scopes that actually have a backlog dir (never create empty ones)
    scopes = [(s, p) for s, p in scopes if os.path.isdir(backlog._dir(s, p))]

    total_before = total_after = 0
    for scope, project in scopes:
        before = _counts(scope, project)
        res = backlog.migrate_scope(scope, project)
        after = _counts(scope, project)
        total_before += before
        total_after += after
        tag = f"{scope}:{project or ''}"
        flag = "OK " if after == before else "!! "
        print(f"  {flag}{tag:34s} migrated={res['migrated']:<4} items={after} (was {before})")

    if a.verify:
        print(f"\nVERIFY: items before={total_before} after={total_after} "
              f"-> {'MATCH' if total_before == total_after else 'MISMATCH'}")
        return 0 if total_before == total_after else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
