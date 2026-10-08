"""BI-PF-0449 migration: retrofit backlog items with context (M1).

- structured bodies (## Problem / why, ## Goal & value, ## In/Out of scope, ## Acceptance criteria) are
  PARSED into brief/objective/in_scope/out_of_scope/acceptance_criteria (fidelity preserved);
- items with no structured body get a DERIVED brief/objective + a placeholder acceptance criterion,
  flagged ``brief.derived=True`` / ``intent_derived=True`` (never passed off as authored);
- child items get ``epic`` set from their existing ``parent``; every epic's ``children[]`` is rebuilt.

Idempotent + single-writer (uses core.backlog.update). Dry-run by default; ``--write`` to apply.
Scope: product_forge (default) or ``--all`` product backlogs.
"""
import argparse
import os
import re
import sys

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core import backlog  # noqa: E402


def _section(body: str, names: tuple) -> str:
    pat = r"^\s*#{1,4}\s*(?:" + "|".join(re.escape(n) for n in names) + r")[^\n]*\n(.*?)(?=\n\s*#{1,4}\s|\Z)"
    m = re.search(pat, body or "", re.I | re.S | re.M)
    return (m.group(1).strip() if m else "")


def _bullets(text: str) -> list:
    out = []
    for ln in (text or "").splitlines():
        m = re.match(r"\s*[-*]\s+(.*)$", ln)
        if m and m.group(1).strip():
            out.append(m.group(1).strip())
    return out


_DEFAULTS = {
    "review": {}, "approach": "", "affected_components": [], "affected_files": [],
    "owner": "", "requester": "", "due": "", "target_release": "", "approvals": [],
    "evidence": [], "verification": [], "risks": [], "rollback": "", "summary": "",
    "in_scope": [], "out_of_scope": [],
}


def _first_para(body: str) -> str:
    for blk in re.split(r"\n\s*\n", body or ""):
        t = re.sub(r"^\s*#{1,4}\s*.*$", "", blk, flags=re.M).strip()
        if len(t) >= 40:
            return t
    return ""


def _derive(item: dict) -> dict:
    """Field updates for one item: extracted context + fill missing fields with defaults."""
    body = item.get("body") or ""
    upd = {}
    if not (item.get("brief") or {}).get("problem") and not (item.get("brief") or {}).get("what_adds"):
        problem = _section(body, ("problem", "problem / why"))
        goal = _section(body, ("goal & value", "goal", "what it adds"))
        para = _first_para(body)
        if problem:
            upd["brief"] = {"problem": problem[:1200], "what_adds": (goal or item.get("title") or "")[:600],
                            "why": "", "who_feels": "", "source": "extracted"}
        elif len(body.strip()) >= 60:
            upd["brief"] = {"problem": (para or body.strip())[:1200],
                            "what_adds": (goal or item.get("title") or "")[:600],
                            "why": "", "who_feels": "", "source": "extracted"}
        else:
            upd["brief"] = {"problem": item.get("title") or "", "what_adds": item.get("title") or "",
                            "why": "", "who_feels": "", "source": "derived"}
    br = item.get("brief") or {}
    if br and not br.get("source"):          # upgrade provenance on pre-existing briefs
        body_ok = (bool(_section(body, ("problem", "problem / why", "goal & value", "goal")))
                   or len(body.strip()) >= 60)
        nb = dict(br)
        nb["source"] = "extracted" if body_ok else "derived"
        upd["brief"] = nb
    if not str(item.get("objective") or "").strip():
        goal = _section(body, ("goal & value", "goal"))
        upd["objective"] = (goal[:300] if goal else (item.get("title") or ""))
    if not item.get("acceptance_criteria"):
        ac = _bullets(_section(body, ("acceptance criteria (testable)", "acceptance criteria", "acceptance")))
        upd["acceptance_criteria"] = ac or [f"(derived) objective met: {item.get('title', '')}"]
    if not item.get("in_scope"):
        sc = _bullets(_section(body, ("in scope", "in scope (sub-items)")))
        if sc:
            upd["in_scope"] = sc
    if not item.get("out_of_scope"):
        oos = _bullets(_section(body, ("out of scope",)))
        if oos:
            upd["out_of_scope"] = oos
    if not item.get("epic") and item.get("parent"):
        upd["epic"] = str(item.get("parent"))
    for k, dv in _DEFAULTS.items():          # normalize: every item carries the full field set
        if k not in upd and not item.get(k):
            upd[k] = dv
    return upd


def _items(scope, project):
    return backlog.list_open(scope, project) + backlog.list_closed(scope, project)


def _run(scope, project, write: bool):
    items = _items(scope, project)
    changed = 0
    for it in items:
        upd = _derive(it)
        if upd and write:
            backlog.update(scope, project, str(it["id"]), **upd)
        if upd:
            changed += 1
    # rebuild epic children[]
    epics = [i for i in _items(scope, project) if backlog.is_epic(i)]
    for e in epics:
        kids = [str(i.get("id")) for i in _items(scope, project)
                if str(i.get("epic") or i.get("parent") or "") == str(e.get("id"))]
        if list(e.get("children") or []) != kids and write:
            backlog.update(scope, project, str(e["id"]), children=kids)
    return len(items), changed, len(epics)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args(argv)
    scopes = [("product_forge", None)]
    if a.all:
        from core.paths import PRODUCTS_DIR
        root = str(PRODUCTS_DIR)
        for name in sorted(os.listdir(root)) if os.path.isdir(root) else []:
            if not name.startswith(("_", ".")) and os.path.isdir(os.path.join(root, name, "backlog", "items")):
                scopes.append(("project", name))
    for scope, project in scopes:
        n, changed, epics = _run(scope, project, a.write)
        print(f"  {scope}:{project or '-'}: {n} items, {changed} needing context, {epics} epics "
              f"({'WROTE' if a.write else 'dry-run'})")
    if not a.write:
        print("backfill-context: dry-run (pass --write to apply)")
    else:
        print("backfill-context: done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
