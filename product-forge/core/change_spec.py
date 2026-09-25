"""Change/new-item FUNCTIONAL SPEC generator (BI-0183).

Planned features get `artifacts/1 - Design/features/F-x-functional.md`. Items that are NOT planned
features (no `links.feature_id`) but are real work (feature/change/tech-debt) get NO spec - so their
design is unclear. This module creates a per-item functional spec, sourced from the item itself
(its body + links), and links it back on the item as `links.spec`.

Deterministic + faithful: it does NOT invent requirements - it carries the item's own context into
the functional-spec structure and marks the sections the design owner must finalise.

Store: `products/<project>/artifacts/1 - Design/changes/<ID>-functional.md` (append/single-writer).
Idempotent: a spec is (re)written only when the item's body changes (tracked by a body hash).

Owner: this module. Wired: core/intake.py (on item creation).
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

import hashlib
import json
import os
from datetime import datetime
from typing import Dict, Optional

SPEC_REL = os.path.join("artifacts", "1 - Design", "changes")
_SPEC_TYPES = {"feature", "change", "tech-debt"}


def _project_dir(project: str) -> str:
    repo = str(_PF_ROOT)
    return os.path.join(repo, "products", project)


def _is_change_new(item: Dict) -> bool:
    """True for a change/new item: not a planned feature (no feature_id) and real work."""
    links = item.get("links") or {}
    if links.get("feature_id"):
        return False
    ext = str(item.get("external_id") or "")
    if ext.startswith("feature:"):
        return False
    return str(item.get("type") or "") in _SPEC_TYPES


def _body_hash(item: Dict) -> str:
    return hashlib.sha256(str(item.get("body") or "").encode("utf-8")).hexdigest()[:16]


def spec_path(project: str, eid: str) -> str:
    return os.path.join(_project_dir(project), SPEC_REL, f"{eid}-functional.md")


def render(scope: str, project: str, item: Dict) -> str:
    eid = item.get("id", "")
    ref = f"{scope}:{project}:{eid}" if project else f"{scope}:{eid}"
    body = (item.get("body") or "").strip()
    links = item.get("links") or {}
    ts = datetime.now().isoformat(timespec="seconds")
    return (
        f"<!-- change-spec owner=core/change_spec.py item={ref} src-body-sha256={_body_hash(item)} -->\n"
        f"# {eid}: {item.get('title', '')}\n\n"
        f"> CHANGE / NEW item (not a planned feature) - type={item.get('type')} "
        f"status={item.get('status')} origin={item.get('origin')} - generated {ts}\n"
        f"> Auto-generated from the backlog item context; the design owner finalises the TODO sections.\n\n"
        f"## Problem / why\n{body or 'TODO: describe the problem / motivation.'}\n\n"
        f"## In scope / Out of scope\n- In scope: TODO\n- Out of scope: TODO\n\n"
        f"## Behaviour\n- TODO: describe the expected behaviour.\n\n"
        f"## Acceptance criteria\n- TODO: testable given/when/then.\n\n"
        f"## Edge cases & errors\n- TODO\n\n"
        f"## Dependencies & links\n- backlog item: {ref}\n- links: {json.dumps(links, ensure_ascii=False)}\n\n"
        f"## Status\nDraft (auto-generated). Source of truth: the backlog item {ref}.\n"
    )


def ensure(scope: str, project: Optional[str], eid: str) -> Optional[Dict]:
    """Create/refresh the functional spec for a change/new item. Idempotent. Returns info or None."""
    if scope != "project" or not project:
        return None
    try:
        from core import backlog
        item = backlog.get(scope, project, eid)
    except Exception:
        item = None
    if not item or not _is_change_new(item):
        return None
    p = spec_path(project, eid)
    h = _body_hash(item)
    if os.path.exists(p):
        try:
            head = open(p, encoding="utf-8").read(400)
            if f"src-body-sha256={h}" in head:
                return {"id": eid, "spec": p, "changed": False}
        except Exception:
            pass
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(render(scope, project, item))
    try:
        rel = os.path.relpath(p, os.path.dirname(_project_dir(project))).replace("\\", "/")
        from core import backlog
        backlog.link(scope, project, eid, spec=rel)
    except Exception:
        pass
    return {"id": eid, "spec": p, "changed": True}


def _main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Change/new item functional spec generator (BI-0183)")
    ap.add_argument("--project", required=True)
    ap.add_argument("--id", default="", help="one item id (default: all change/new items)")
    a = ap.parse_args(argv)
    from core import backlog
    ids = [a.id] if a.id else [i["id"] for i in backlog.list_items("project", a.project)]
    made = 0
    for eid in ids:
        r = ensure("project", a.project, eid)
        if r:
            print(f"  {'wrote' if r['changed'] else 'current'} {eid} -> {r['spec']}")
            made += 1 if r["changed"] else 0
    print(f"\nspecs written: {made}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
