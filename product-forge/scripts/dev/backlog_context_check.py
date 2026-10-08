"""BI-PF-0448 fail-closed gate: every OPEN work item carries context; Epics are consistent.

For scope ``product_forge`` (and, with --all, every product backlog):
  - a WORK item must have a non-empty ``brief`` (problem/what_adds), ``objective`` and ``acceptance_criteria``;
  - an EPIC must have ``brief`` + ``objective`` and a ``children[]`` that matches its actual children;
  - any ``epic`` reference on a child must resolve to a real item.

Fatal on violation (wired into precheck). Author-time companion: the same checks run for changed items.
"""
import argparse
import os
import sys

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core import backlog  # noqa: E402


def _scopes(include_all: bool):
    out = [("product_forge", None)]
    if include_all:
        try:
            from core.paths import PRODUCTS_DIR
            root = os.path.join(str(PRODUCTS_DIR))
            for name in sorted(os.listdir(root)) if os.path.isdir(root) else []:
                if name.startswith("_") or name.startswith(".") or name == "test-project":
                    continue
                if os.path.isdir(os.path.join(root, name, "backlog", "items")):
                    out.append(("project", name))
        except Exception:
            pass
    return out


def _problems_for(scope, project, items, all_items):
    probs = []
    ids = {str(i.get("id")) for i in all_items}
    for it in items:
        eid = str(it.get("id"))
        brief = it.get("brief") or {}
        obj = str(it.get("objective") or "").strip()
        if backlog.is_epic(it):
            if not (brief.get("problem") or brief.get("what_adds")):
                probs.append(f"{eid}: epic missing brief")
            if not obj and not str(it.get("summary") or "").strip():
                probs.append(f"{eid}: epic missing objective/summary")
            kids = [i for i in all_items if str(i.get("epic") or i.get("parent") or "") == eid]
            if list(it.get("children") or []) != [str(k.get("id")) for k in kids]:
                probs.append(f"{eid}: epic children[] out of sync (has {len(it.get('children') or [])}, "
                             f"actual {len(kids)})")
        else:
            if not (brief.get("problem") or brief.get("what_adds")):
                probs.append(f"{eid}: missing brief (problem/what_adds)")
            if brief.get("source") not in ("authored", "extracted"):
                probs.append(f"{eid}: brief not authored/extracted (source={brief.get('source')!r})")
            if not obj:
                probs.append(f"{eid}: missing objective")
            if not (it.get("acceptance_criteria") or []):
                probs.append(f"{eid}: missing acceptance_criteria")
            for fld in ("in_scope", "out_of_scope", "affected_components", "affected_files", "approach",
                        "verification", "risks", "rollback", "evidence", "owner", "requester", "due",
                        "target_release"):
                v = it.get(fld)
                if isinstance(v, list):
                    if not v:
                        probs.append(f"{eid}: empty {fld}")
                elif not str(v or "").strip():
                    probs.append(f"{eid}: empty {fld}")
            if not (it.get("review") or {}):
                probs.append(f"{eid}: empty review")
        ep = str(it.get("epic") or "").strip()
        if ep and ep not in ids:
            probs.append(f"{eid}: epic ref {ep!r} does not resolve")
    return probs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="also check every product backlog")
    a = ap.parse_args(argv)
    total, probs = 0, []
    for scope, project in _scopes(a.all):
        items = backlog.list_open(scope, project)
        all_items = items + backlog.list_closed(scope, project)
        total += len(items)
        probs += _problems_for(scope, project, items, all_items)
    if probs:
        print(f"backlog-context: FAIL ({len(probs)} problem(s) across {total} open item(s))")
        for p in probs[:25]:
            print("   -", p)
        return 1
    print(f"backlog-context: OK ({total} open item(s) carry context; epics consistent)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
