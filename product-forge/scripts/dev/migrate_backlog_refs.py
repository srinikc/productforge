"""Migration (BI-0082): qualify bare BI-#### cross-scope links.

Idempotent. Rewrites link values that are bare ``BI-####`` into scope-qualified
refs, using the link key + scope as context:
  * product_forge item's ``dashboard_item`` -> project:<DASH_PROJECT>:BI-####
  * project item's ``backend_item``         -> product_forge:BI-####

Usage:
    python scripts/dev/migrate_backlog_refs.py            # dry-run
    python scripts/dev/migrate_backlog_refs.py --apply
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
import re
import sys

sys.path.insert(0, str(_PF_ROOT))
from core import backlog  # noqa: E402

BARE = re.compile(r"^BI-\d+$")
DASH_PROJECT = "ProductForge-Dashboard"
APPLY = "--apply" in sys.argv


def _qualify_value(scope, project, key, value):
    if not isinstance(value, str) or not BARE.match(value):
        return value
    if key in ("dashboard_item", "dashboard_backlog", "dashboard_scope_item"):
        return backlog.qualify("project", DASH_PROJECT, value)
    if key in ("backend_item", "backend_backlog"):
        return backlog.qualify("product_forge", None, value)
    return value  # unknown context: leave (and let link() warn)


def migrate_scope(scope, project):
    items = backlog.list_open(scope, project, order=False) + backlog.list_closed(scope, project)
    changed = 0
    for it in items:
        links = dict(it.get("links") or {})
        new = {}
        touched = False
        for k, v in links.items():
            if isinstance(v, list):
                nv = [_qualify_value(scope, project, k, x) for x in v]
            else:
                nv = _qualify_value(scope, project, k, v)
            if nv != v:
                touched = True
            new[k] = nv
        if touched:
            changed += 1
            print(f"  {scope}:{it['id']} links {links} -> {new}")
            if APPLY:
                backlog.update(scope, project, it["id"], links=new)
    return changed


def main():
    print(f"{'APPLY' if APPLY else 'DRY-RUN'} migrate_backlog_refs (BI-0082)")
    n = 0
    n += migrate_scope("product_forge", None)
    n += migrate_scope("project", DASH_PROJECT)
    print("items changed:", n)
    if not APPLY:
        print("re-run with --apply to write")


if __name__ == "__main__":
    main()
