"""Issue tracker — the work-item registry for FINDINGS (one per scope).

Companion to the backlog (which tracks WORK). Every issue found maps 1:1 to exactly
one backlog item so remediation is trackable, and carries its RCCA + learning.

Scopes (same layout as the backlog):
  product_forge : product-forge/issues/
  project       : products/<project>/issues/
Per scope:
  items/<IS-...>.json   THE TRUTH (single writer)
  open.json / closed.json  DERIVED lean indexes
  counters.json         next IS id
  history/<IS>.jsonl    append-only journal

Id scheme: ``IS-<TAG>-<nnn>`` where TAG reuses the backlog destination tag
(PF | DASH | IN | <PROJECT-SLUG>) via ``core.backlog.tag_for`` (BI-PF-0231).

Model: Issue
  id, tag, scope, project, title, body, kind(issue|bug|risk|gap), priority(P0..P3),
  severity, module, status(open|triaged|fixed|verified|closed|wontfix|duplicate),
  rcca{root_cause, corrective, preventive, generalized(bool), guideline_ref, product_ref},
  backlog_ref (1:1), found_at, source, evidence[], links{}, created_at, updated_at
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
import re
import time
from datetime import datetime
from typing import Dict, List, Optional

_REPO = str(_PF_ROOT)
_PRODUCTS = os.path.join(_REPO, "products")
_FORGE_DIR = _REPO
_LEGACY_FORGE_SCOPE = "fac" "tory"
_CLOSED = {"closed", "verified", "fixed", "wontfix", "duplicate"}
_PRIORITIES = ("P0", "P1", "P2", "P3")
_KINDS = ("issue", "bug", "risk", "gap")


def _norm_scope(scope: str) -> str:
    return "product_forge" if scope in ("portfolio", "product_forge", _LEGACY_FORGE_SCOPE) else "project"


def _dir(scope: str, project: Optional[str] = None) -> str:
    if _norm_scope(scope) == "product_forge":
        legacy = os.path.join(_PRODUCTS, "issues")
        new = os.path.join(_FORGE_DIR, "issues")
        if not os.path.exists(new) and os.path.exists(legacy):
            return legacy
        return new
    return os.path.join(_PRODUCTS, project or "_unknown", "issues")


def _paths(scope: str, project: Optional[str] = None):
    d = _dir(scope, project)
    return d, os.path.join(d, "open.json"), os.path.join(d, "closed.json"), os.path.join(d, "counters.json")


def _rj(p, d):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def _wj(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, p)


def _lock(d):
    os.makedirs(d, exist_ok=True)
    lp = os.path.join(d, ".lock")
    for _ in range(50):
        try:
            fd = os.open(lp, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return lp
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(lp) > 300:
                    os.remove(lp)
                    continue
            except Exception:
                pass
            time.sleep(0.1)
    raise TimeoutError(f"[Issues] could not acquire lock {lp}")


def _unlock(lp):
    try:
        os.remove(lp)
    except Exception:
        pass


def _num(eid: str) -> int:
    return int(re.sub(r"\D", "", str(eid)) or 0)


def _tag_for(scope: str, project: Optional[str], kind: str) -> str:
    try:
        from core import backlog
        return backlog.tag_for(scope, project, "intake", kind)
    except Exception:
        return "PF" if _norm_scope(scope) == "product_forge" else "PRJ"


def _items_dir(d: str) -> str:
    return os.path.join(d, "items")


def _item_path(d: str, iid: str) -> str:
    return os.path.join(_items_dir(d), f"{iid}.json")


def _load_all(scope: str, project: Optional[str]):
    d, _of, _cf, _c = _paths(scope, project)
    idir = _items_dir(d)
    op: List[Dict] = []
    cl: List[Dict] = []
    if os.path.isdir(idir):
        for fn in sorted(os.listdir(idir)):
            if not fn.endswith(".json"):
                continue
            it = _rj(os.path.join(idir, fn), None)
            if not isinstance(it, dict) or not it.get("id"):
                continue
            (cl if str(it.get("status")) in _CLOSED else op).append(it)
    return op, cl


def _save_item(d: str, it: Dict) -> None:
    _wj(_item_path(d, it["id"]), it)


def _write_indexes(d: str, op: List[Dict], cl: List[Dict]) -> None:
    row = lambda e: {"id": e.get("id"), "status": e.get("status"), "priority": e.get("priority"),
                     "module": e.get("module"), "backlog_ref": e.get("backlog_ref"),
                     "title": e.get("title"), "updated_at": e.get("updated_at")}
    _wj(os.path.join(d, "open.json"), [row(e) for e in op])
    _wj(os.path.join(d, "closed.json"), [row(e) for e in cl])


def _hist(d: str, it: Dict, event: str = "update") -> None:
    try:
        h = os.path.join(d, "history")
        os.makedirs(h, exist_ok=True)
        with open(os.path.join(h, f"{it['id']}.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": datetime.now().isoformat(), "event": event,
                                "status": it.get("status")}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def raise_issue(scope: str, project: Optional[str], title: str, *, body: str = "",
                kind: str = "issue", priority: str = "P2", severity: str = "",
                module: str = "", source: str = "review", evidence: Optional[List] = None,
                rcca: Optional[Dict] = None, backlog_ref: str = "",
                source_ref: str = "") -> Dict:
    """Create one finding. Returns the issue (with an IS-<TAG>-<nnn> id).

    Idempotent by ``(source, source_ref)`` so re-ingesting the same underlying finding
    (a defect id, an issue_tracker id, an audit PF id) never duplicates.
    """
    scope = _norm_scope(scope)
    d, _of, _cf, ctr = _paths(scope, project)
    lp = _lock(d)
    try:
        op, cl = _load_all(scope, project)
        if source_ref:
            for e in op + cl:
                if e.get("source") == source and str(e.get("source_ref") or "") == str(source_ref):
                    return e
        mx = max([_num(e.get("id")) for e in op + cl] or [0])
        tag = _tag_for(scope, project, kind)
        iid = f"IS-{tag}-{mx + 1:04d}"
        counters = _rj(ctr, {})
        item = {
            "id": iid, "tag": tag, "scope": scope, "project": project or "",
            "title": title, "body": body, "kind": kind if kind in _KINDS else "issue",
            "priority": priority if priority in _PRIORITIES else "P2",
            "severity": severity, "module": module, "status": "open",
            "rcca": rcca or {}, "backlog_ref": backlog_ref, "source": source,
            "source_ref": source_ref, "evidence": evidence or [], "links": {},
            "created_at": datetime.now().isoformat(), "updated_at": datetime.now().isoformat(),
        }
        op.append(item)
        _save_item(d, item)
        _write_indexes(d, op, cl)
        _wj(ctr, counters)
        _hist(d, item, "created")
        return item
    finally:
        _unlock(lp)


def ingest_defects(scope: str, project: str) -> List[Dict]:
    """Reuse core/defect_loop: register each OPEN defect as an issue (idempotent)."""
    out: List[Dict] = []
    try:
        from core import defect_loop
        _pri = {"critical": "P0", "high": "P1", "medium": "P2", "low": "P3"}
        for d in (defect_loop.open_defects(project) or []):
            did = str(d.get("defect_id") or d.get("id") or "")
            out.append(raise_issue(
                scope, (project if _norm_scope(scope) == "project" else None),
                title=str(d.get("title") or d.get("description") or did or "defect"),
                body=str(d.get("description") or ""), kind="bug",
                priority=_pri.get(str(d.get("severity", "")).lower(), "P2"),
                severity=str(d.get("severity") or ""),
                module=str(d.get("affected_feature") or d.get("component") or ""),
                source="defect", source_ref=did,
                rcca={"preventive": str(d.get("rcca_recommendation") or "")}))
    except Exception:
        pass
    return out


def get(scope: str, project: Optional[str], iid: str) -> Optional[Dict]:
    return _rj(_item_path(_dir(scope, project), iid), None)


def list_open(scope: str, project: Optional[str] = None, priority: str = "",
              module: str = "") -> List[Dict]:
    op, _cl = _load_all(scope, project)
    if priority:
        op = [e for e in op if e.get("priority") == priority]
    if module:
        op = [e for e in op if e.get("module") == module]
    return op


def list_closed(scope: str, project: Optional[str] = None) -> List[Dict]:
    _op, cl = _load_all(scope, project)
    return cl


def set_status(scope: str, project: Optional[str], iid: str, status: str,
               note: str = "", force: bool = False) -> Optional[Dict]:
    d, _of, _cf, _c = _paths(scope, project)
    lp = _lock(d)
    try:
        op, cl = _load_all(scope, project)
        found = None
        for e in op + cl:
            if e.get("id") == iid:
                found = e
                break
        if not found:
            return None
        # Fail closed: an issue may only reach a terminal state with a complete RCCA.
        if status in _CLOSED and not force and not rcca_complete(found):
            raise ValueError(f"issue {iid}: cannot set '{status}' - RCCA incomplete "
                             "(root_cause + corrective + fixed_where required)")
        found["status"] = status
        found["updated_at"] = datetime.now().isoformat()
        if note:
            found["note"] = note
        op2 = [e for e in op + cl if str(e.get("status")) not in _CLOSED]
        cl2 = [e for e in op + cl if str(e.get("status")) in _CLOSED]
        _save_item(d, found)
        _write_indexes(d, op2, cl2)
        _hist(d, found, f"status:{status}")
        return found
    finally:
        _unlock(lp)


def set_rcca(scope: str, project: Optional[str], iid: str, *, root_cause: str = "",
             corrective: str = "", preventive: str = "", fixed_where: str = "",
             generalized: bool = False, guideline_ref: str = "", product_ref: str = "") -> Optional[Dict]:
    """Attach/refresh the RCCA (root cause, what was done, WHERE it was fixed, learning)."""
    it = get(scope, project, iid)
    if not it:
        return None
    rcca = dict(it.get("rcca") or {})
    rcca.update({"root_cause": root_cause or rcca.get("root_cause", ""),
                 "corrective": corrective or rcca.get("corrective", ""),
                 "preventive": preventive or rcca.get("preventive", ""),
                 "fixed_where": fixed_where or rcca.get("fixed_where", ""),
                 "generalized": bool(generalized),
                 "guideline_ref": guideline_ref or rcca.get("guideline_ref", ""),
                 "product_ref": product_ref or rcca.get("product_ref", "")})
    d, _of, _cf, _c = _paths(scope, project)
    lp = _lock(d)
    try:
        op, cl = _load_all(scope, project)
        for e in op + cl:
            if e.get("id") == iid:
                e["rcca"] = rcca
                e["updated_at"] = datetime.now().isoformat()
                _save_item(d, e)
                _hist(d, e, "rcca")
                return e
    finally:
        _unlock(lp)
    return None


def rcca_complete(it: Dict) -> bool:
    """An issue is 'fixed with RCCA' only when root cause + corrective + WHERE are recorded."""
    r = (it or {}).get("rcca") or {}
    return bool(str(r.get("root_cause") or "").strip()
                and str(r.get("corrective") or "").strip()
                and str(r.get("fixed_where") or "").strip())


def can_close_ref(ref: str):
    """Gate for a backlog item's linked issue: (ok, reason). Fail closed."""
    try:
        from core import backlog
        sc, pr, iid = backlog.parse_ref(ref)
        if not sc:
            return False, f"issue ref not scope-qualified: {ref!r}"
        it = get(sc, pr, iid)
        if not it:
            return False, f"issue {ref} not found"
        if not rcca_complete(it):
            return False, (f"issue {iid}: RCCA incomplete - need root_cause + corrective + "
                           "fixed_where before the backlog item can close")
        return True, ""
    except Exception as e:
        return False, f"issue check failed: {e}"


def link_backlog(scope: str, project: Optional[str], iid: str, backlog_ref: str) -> Optional[Dict]:
    """Establish the 1:1 mapping: issue.backlog_ref <-> backlog item links.issue (reciprocal)."""
    it = get(scope, project, iid)
    if not it:
        return None
    d, _of, _cf, _c = _paths(scope, project)
    lp = _lock(d)
    try:
        op, cl = _load_all(scope, project)
        for e in op + cl:
            if e.get("id") == iid:
                e["backlog_ref"] = backlog_ref
                e["updated_at"] = datetime.now().isoformat()
                e["links"] = dict(e.get("links") or {})
                e["links"]["backlog"] = backlog_ref
                _save_item(d, e)
                _write_indexes(d, [x for x in op if str(x.get("status")) not in _CLOSED],
                               [x for x in cl if str(x.get("status")) in _CLOSED])
                _hist(d, e, "link_backlog")
                it = e
                break
    finally:
        _unlock(lp)
    # reciprocal link on the backlog item (best-effort)
    try:
        from core import backlog
        bscope, bproj, bid = backlog.parse_ref(backlog_ref)
        if not bscope:
            bid = backlog_ref
            bscope, bproj = _norm_scope(scope), (project if _norm_scope(scope) == "project" else None)
        backlog.link(bscope, bproj, bid, issue=backlog.qualify(scope, project, iid))
    except Exception:
        pass
    return it


def stats(scope: str, project: Optional[str] = None) -> Dict:
    op, cl = _load_all(scope, project)
    by_pri: Dict[str, int] = {}
    by_mod: Dict[str, int] = {}
    for e in op:
        by_pri[e.get("priority", "?")] = by_pri.get(e.get("priority", "?"), 0) + 1
        by_mod[e.get("module", "?")] = by_mod.get(e.get("module", "?"), 0) + 1
    return {"scope": _norm_scope(scope), "project": project or "", "open": len(op), "closed": len(cl),
            "by_priority": by_pri, "by_module": by_mod,
            "unlinked_open": sum(1 for e in op if not e.get("backlog_ref"))}


def _cli(argv=None) -> int:
    import argparse
    try:
        import sys as _sys
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    p = argparse.ArgumentParser(prog="python -m core.issues", description="Issue tracker (findings + RCCA)")
    p.add_argument("--scope", default="product_forge")
    p.add_argument("--project", default="")
    p.add_argument("--list", action="store_true")
    p.add_argument("--show", metavar="ID")
    p.add_argument("--stats", action="store_true")
    a = p.parse_args(argv)
    proj = a.project or None
    if a.show:
        print(json.dumps(get(a.scope, proj, a.show), indent=2, ensure_ascii=False))
        return 0
    if a.stats:
        print(json.dumps(stats(a.scope, proj), indent=2, ensure_ascii=False))
        return 0
    for e in list_open(a.scope, proj):
        print(f"{e['id']}  {e.get('priority')}  [{e.get('module')}]  {e.get('title')}  "
              f"-> {e.get('backlog_ref') or '(no backlog)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
