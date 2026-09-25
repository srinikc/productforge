"""Backlog â€” the single work-item registry (one per scope).

Scopes:
  project        : products/<project>/backlog/
  product_forge  : product-forge/backlog/   (legacy read-fallback: products/backlog/)
  (legacy alias "portfolio" -> "product_forge")

Storage (per scope):
  items/<ID>.json      THE TRUTH - one full item per file (single writer)
  open.json            DERIVED index of non-terminal items (lean: id/status/one-liner/dates)
  closed.json          DERIVED index of terminal items
  counters.json        next BI id + next "Backlog N" label
  history/<ID>.jsonl   append-only journal (status + content changes)

Never read/write these files directly - use this module's API (list/get/update/history).

Model: BacklogItem
  id, scope, project, origin(intake|pipeline), type(idea|project|change|feature|bug|tech-debt|explore),
  section(derived: intake|pipeline|done), label("Backlog N"), title, body, source, status,
  moscow, value/effort/risk/score, deps[], links{feature_id,defect_ids,conversation_id,idea_ids,
  cp_ids,iteration_ids,commit,artifacts,paired_with,backend_capability,capability_ref},
  dashboard_impact (review decision), follow_up{at,review_every,snooze_until}, decisions[],
  created_at, updated_at

Single writer: this module. Everything else calls it (id-only references, no copies).
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
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

_REPO = str(_PF_ROOT)
_PRODUCTS = os.path.join(_REPO, "products")
_FORGE_DIR = os.path.join(_REPO, "data")

_CLOSED = {"completed", "done", "rejected", "wontfix", "duplicate", "merged", "archived"}
# Canonical terminal status is "completed" (= implemented + verified). Legacy spellings
# ("done", "closed") normalize to it so there is ONE finished status.
_STATUS_ALIASES = {"done": "completed", "closed": "completed", "complete": "completed",
                   "finished": "completed", "resolved": "completed"}


def _normalize_status(st: str) -> str:
    s = str(st or "new").strip().lower()
    return _STATUS_ALIASES.get(s, s)
_INTAKE_STATUSES = {"new", "received", "compiled", "triaged", "accepted", "parked"}
_PIPELINE_STATUSES = {"queued", "scheduled", "executing", "implemented", "verifying", "blocked"}
_MOSCOW_RANK = {"Must": 0, "Should": 1, "Could": 2, "Wont": 3}
_DEFAULT_REVIEW_DAYS = 7
_DASHBOARD_PROJECT = "ProductForge-Dashboard"   # dashboard scope for the reciprocity REVIEW rule


_LEGACY_FORGE_SCOPE = "fac" "tory"   # legacy scope alias found in early stored data


def _norm_scope(scope: str) -> str:
    return "product_forge" if scope in ("portfolio", "product_forge", _LEGACY_FORGE_SCOPE) else "project"


def _dir(scope: str, project: Optional[str] = None) -> str:
    scope = _norm_scope(scope)
    if scope == "product_forge":
        legacy = os.path.join(_PRODUCTS, "backlog")
        new = os.path.join(_FORGE_DIR, "backlog")
        if not os.path.exists(new) and os.path.exists(legacy):
            return legacy
        return new
    return os.path.join(_PRODUCTS, project or "_unknown", "backlog")


def _paths(scope: str, project: Optional[str] = None):
    d = _dir(scope, project)
    return (d, os.path.join(d, "open.json"), os.path.join(d, "closed.json"),
            os.path.join(d, "history"), os.path.join(d, "counters.json"))


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


def _items_dir(d: str) -> str:
    return os.path.join(d, "items")


# The lean DERIVED index (the "tracking" view): id/status/section/one-liner/dates ONLY.
# EVERYTHING else (type/origin/moscow/value/effort/risk/score, body, links, decisions,
# follow_up, dashboard_impact) lives only in items/<ID>.json (the truth).
_INDEX_FIELDS = ("id", "status", "section", "title", "created_at", "updated_at")


def _index_row(it: Dict) -> Dict:
    row = {k: it.get(k) for k in _INDEX_FIELDS}
    row["section"] = section(it)
    return row


def _load_all(scope: str, project: Optional[str]):
    """Return (open_items, closed_items) as FULL items from items/<ID>.json (the truth).

    Fallback: if `items/` is empty, read the legacy full-array open.json/closed.json so a
    not-yet-migrated scope still works (see `migrate_scope`).
    """
    d, of, cf, _h, _c = _paths(scope, project)
    idir = _items_dir(d)
    op: List[Dict] = []
    cl: List[Dict] = []
    try:
        names = [f for f in os.listdir(idir) if f.endswith(".json")] if os.path.isdir(idir) else []
    except Exception:
        names = []
    if names:
        for fn in sorted(names):
            it = _rj(os.path.join(idir, fn), None)
            if not isinstance(it, dict) or not it.get("id"):
                continue
            (cl if _normalize_status(it.get("status", "new")) in _CLOSED else op).append(it)
        return op, cl
    lo, lc = _rj(of, []), _rj(cf, [])               # legacy layout
    lo = lo.get("items") if isinstance(lo, dict) else lo
    lc = lc.get("items") if isinstance(lc, dict) else lc
    return list(lo or []), list(lc or [])


def _save_item(d: str, item: Dict) -> None:
    iid = str(item.get("id") or "")
    if not iid:
        return
    _wj(os.path.join(_items_dir(d), f"{iid}.json"), item)


def _write_indexes(scope: str, project: Optional[str], op: List[Dict], cl: List[Dict]) -> None:
    """Regenerate the DERIVED open/closed indexes (lean rows). Never hand-edited."""
    _d, of, cf, _h, _c = _paths(scope, project)
    _wj(of, [_index_row(i) for i in op])
    _wj(cf, [_index_row(i) for i in cl])


def migrate_scope(scope: str, project: Optional[str] = None) -> Dict:
    """Convert a legacy full-array scope -> items/<ID>.json + derived indexes. Idempotent.

    No-op (creates nothing) when the scope has no backlog dir yet.
    """
    scope = _norm_scope(scope)
    d, of, cf, _h, _c = _paths(scope, project)
    if not os.path.isdir(d):
        return {"scope": scope, "project": project or "", "migrated": 0, "items": 0, "skipped": True}
    lp = _lock(d)
    try:
        lo, lc = _rj(of, []), _rj(cf, [])
        lo = lo.get("items") if isinstance(lo, dict) else lo
        lc = lc.get("items") if isinstance(lc, dict) else lc
        legacy = [i for i in (list(lo or []) + list(lc or []))
                  if isinstance(i, dict) and i.get("id") and "body" in i]
        wrote = 0
        for it in legacy:
            if not os.path.exists(os.path.join(_items_dir(d), f"{it['id']}.json")):
                _save_item(d, it)
                wrote += 1
        op, cl = _load_all(scope, project)
        _write_indexes(scope, project, op, cl)
        return {"scope": scope, "project": project or "", "migrated": wrote,
                "items": len(op) + len(cl)}
    finally:
        _unlock(lp)


def _lock(d):
    os.makedirs(d, exist_ok=True)
    lp = os.path.join(d, ".lock")
    for _ in range(50):
        try:
            fd = os.open(lp, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return lp
        except FileExistsError:
            time.sleep(0.1)
    return None


def _unlock(lp):
    try:
        os.remove(lp)
    except Exception:
        pass


def _num(eid: str) -> int:
    try:
        return int(re.sub(r"\D", "", str(eid)) or 0)
    except Exception:
        return 0


def _next_id(open_items, closed_items) -> str:
    mx = max([_num(e.get("id")) for e in list(open_items) + list(closed_items)] or [0])
    return f"BI-{mx + 1:04d}"


def _label_prefix(scope: str, project: Optional[str]) -> str:
    return "PF" if _norm_scope(scope) == "product_forge" else (project or "Project")


def _next_label(counters: Dict, scope: str, project: Optional[str]) -> str:
    n = int(counters.get("next_label", 1))
    counters["next_label"] = n + 1
    return f"{_label_prefix(scope, project)} Backlog {n}"


def section(item: Dict) -> str:
    st = _normalize_status(item.get("status", "new"))
    if st in _CLOSED:
        return "done"
    if st in _PIPELINE_STATUSES:
        return "pipeline"
    return "intake"


def score(e: Dict) -> float:
    v = float(e.get("value", 3) or 3)
    ef = max(float(e.get("effort", 3) or 3), 1.0)
    r = float(e.get("risk", 2) or 2)
    conf = 1.0 - (max(1.0, min(5.0, r)) - 1.0) / 4.0   # risk 1..5 -> 1.0..0.0
    return round((v * conf) / ef, 2)


def _hist(d, item, changes=None, event=""):
    """Append one journal line: status/section/note AND (optionally) content changes."""
    try:
        h = os.path.join(d, "history")
        os.makedirs(h, exist_ok=True)
        rec = {"at": datetime.now().isoformat(), "event": event or "update",
               "status": item.get("status"), "section": section(item),
               "note": item.get("_note", "")}
        if changes:
            rec["changes"] = changes
        with open(os.path.join(h, f"{item['id']}.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


_JOURNAL_KEYS = ("title", "body", "links", "status", "moscow", "value", "effort", "risk",
                 "deps", "decisions", "follow_up", "dashboard_impact", "external_id")


def _diff_fields(old: Dict, new: Dict) -> Dict:
    """Field-level before->after for the content journal (bodies summarized by length)."""
    out = {}
    for k in _JOURNAL_KEYS:
        a, b = old.get(k), new.get(k)
        if a == b:
            continue
        out[k] = ({"from_len": len(a or ""), "to_len": len(b or "")} if k == "body"
                  else {"from": a, "to": b})
    return out


def _find(op: List[Dict], cl: List[Dict], eid: str):
    for e in op:
        if e.get("id") == eid:
            return e, op
    for e in cl:
        if e.get("id") == eid:
            return e, cl
    return None, op


_SIMILAR_WARN = 0.30   # similarity floor for the dedup-before-add advisory
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP = {"the", "a", "an", "of", "to", "for", "and", "or", "in", "on", "with", "via",
         "per", "is", "are", "be", "as", "by", "at", "from", "into", "not", "no", "any",
         "all", "new", "add", "use", "its", "this", "that", "bi", "mvp"}


def _tokens(text: str) -> set:
    """Lowercased alphanumeric token set (len>2, stopwords dropped) - no external deps."""
    return {t for t in _TOKEN_RE.findall(str(text or "").lower())
            if len(t) > 2 and t not in _STOP}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return (inter / len(a | b)) if inter else 0.0


def _similarity(a: set, b: set) -> float:
    """Blend of Jaccard and the overlap coefficient (Szymkiewicz-Simpson).

    The overlap term (|a&b| / min(|a|,|b|)) keeps a short query comparable to a
    long item body; the Jaccard term penalizes single-token coincidences.
    """
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if not inter:
        return 0.0
    return round(0.5 * (inter / len(a | b)) + 0.5 * (inter / min(len(a), len(b))), 4)


def _item_text(e: Dict) -> str:
    return " ".join([str(e.get("title") or ""), str(e.get("body") or ""),
                     str(e.get("external_id") or "")])


def _scope_pairs(scope: Optional[str]):
    """Resolve an optional scope selector -> [(scope, project), ...]."""
    if not scope:
        return _all_scopes()
    s = _norm_scope(scope)
    if s == "product_forge":
        return [("product_forge", None)]
    if scope == "project":
        return [(sc, pr) for sc, pr in _all_scopes() if sc == "project"]
    return [("project", scope)]


def find_similar(text: str, scope: Optional[str] = None, limit: int = 5) -> List[Dict]:
    """Rank existing items by token-set Jaccard similarity to ``text`` (title+body+external_id).

    Pure python (no external deps). Searches OPEN and CLOSED items so a just-merged
    duplicate is still surfaced. Returns candidates (score > 0) ranked high->low:
    ``{ref, id, scope, project, title, external_id, status, score}``.
    """
    q = _tokens(text)
    if not q:
        return []
    out: List[Dict] = []
    for sc, pr in _scope_pairs(scope):
        for e in list_open(sc, pr, order=False) + list_closed(sc, pr):
            scv = _similarity(q, _tokens(_item_text(e)))
            if scv <= 0:
                continue
            out.append({
                "ref": qualify(e.get("scope") or sc, e.get("project") or pr, e.get("id")),
                "id": e.get("id"), "scope": e.get("scope") or sc,
                "project": e.get("project") or pr or "",
                "title": e.get("title", ""), "external_id": e.get("external_id", ""),
                "status": e.get("status", ""), "score": round(scv, 4)})
    out.sort(key=lambda r: -r["score"])
    return out[:max(1, int(limit))]


def duplicate_pairs(scope: Optional[str] = None, threshold: float = 0.5,
                    limit: int = 50) -> List[Dict]:
    """Near-duplicate OPEN-item pairs (Jaccard >= threshold), ranked by score."""
    out: List[Dict] = []
    for sc, pr in _scope_pairs(scope):
        items = list_open(sc, pr, order=False)
        toks = [_tokens(_item_text(e)) for e in items]
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                scv = _similarity(toks[i], toks[j])
                if scv < threshold:
                    continue
                a, b = items[i], items[j]
                out.append({
                    "a": qualify(a.get("scope") or sc, a.get("project") or pr, a.get("id")),
                    "b": qualify(b.get("scope") or sc, b.get("project") or pr, b.get("id")),
                    "a_title": a.get("title", ""), "b_title": b.get("title", ""),
                    "score": round(scv, 3)})
    out.sort(key=lambda r: -r["score"])
    return out[:limit]


def add_epic(scope: str, project: Optional[str], title: str, body: str = "",
             source: str = "generic", type_: str = "feature", origin: str = "intake",
             value: int = 3, effort: int = 3, risk: int = 2, moscow: str = "Should",
             deps: Optional[List[str]] = None, links: Optional[Dict] = None,
             external_id: str = "") -> Dict:
    """Create a work item. `external_id` (e.g. feature_id/defect_id/conversation_id) makes it idempotent."""
    scope = _norm_scope(scope)
    d, of, cf, _h, ctr = _paths(scope, project)
    lp = _lock(d)
    try:
        op, cl = _load_all(scope, project)
        if external_id:
            for e in op + cl:
                if e.get("external_id") == external_id:
                    return e
        counters = _rj(ctr, {})
        try:
            _sims = [s for s in find_similar(f"{title} {body or ''}".strip(), scope=scope)
                     if s.get("score", 0) >= _SIMILAR_WARN]
        except Exception:
            _sims = []
        if _sims:
            print(f"[Backlog] DEDUP WARNING: possible near-duplicate(s) for {title!r} - "
                  "EXTEND/MERGE an existing item instead of creating a new one:")
            for s in _sims:
                print(f"   - {s['ref']} (score {s['score']}) [{s['status']}]: {s['title']}")
        item = {
            "id": _next_id(op, cl), "type": type_, "scope": scope, "project": project or "",
            "origin": origin, "external_id": external_id, "label": _next_label(counters, scope, project),
            "title": title, "body": body, "source": source, "status": "new",
            "priority": None, "moscow": moscow, "value": value, "effort": effort, "risk": risk,
            "deps": deps or [], "links": links or {}, "decisions": [], "follow_up": {},
            "created_at": datetime.now().isoformat(), "updated_at": datetime.now().isoformat(),
        }
        item["score"] = score(item)
        op.append(item)
        _save_item(d, item)
        _write_indexes(scope, project, op, cl)
        _wj(ctr, counters)
        _hist(d, item, changes={"created": True}, event="created")
        return item
    finally:
        _unlock(lp)


def ensure_item(scope: str, project: Optional[str], external_id: str, title: str,
                type_: str = "feature", origin: str = "pipeline", **fields) -> Dict:
    """Idempotent get-or-create keyed by `external_id` (for the bridges)."""
    scope = _norm_scope(scope)
    d, of, cf, _h, _c = _paths(scope, project)
    lp = _lock(d)
    try:
        op, cl = _load_all(scope, project)
        for e in op + cl:
            if e.get("external_id") == external_id:
                upd = {k: v for k, v in fields.items() if v not in (None, "")}
                if upd:
                    old = dict(e)
                    e.update(upd)
                    e["score"] = score(e)
                    e["updated_at"] = datetime.now().isoformat()
                    _save_item(d, e)
                    _write_indexes(scope, project, op, cl)
                    _hist(d, e, changes=_diff_fields(old, e), event="update")
                return e
    finally:
        _unlock(lp)
    return add_epic(scope, project, title, type_=type_, origin=origin,
                    external_id=external_id, **fields)


def set_status(scope: str, project: Optional[str], eid: str, status: str, note: str = "") -> Optional[Dict]:
    return update(scope, project, eid, status=status, _note=note)


_BARE_BI_RE = re.compile(r"^BI-\d+$")


def link(scope: str, project: Optional[str], eid: str, **refs) -> Optional[Dict]:
    """Merge references into item.links (ids only).

    Cross-scope item references MUST be scope-qualified (BI-0082), e.g.
    ``backend_item=backlog.qualify("product_forge", None, "BI-0042")``. A bare
    ``BI-####`` is ambiguous (ids collide across scopes) and warns.
    """
    item = get_epic(scope, project, eid)
    if not item:
        return None
    for _k, _v in refs.items():
        for _val in (_v if isinstance(_v, list) else [_v]):
            if isinstance(_val, str) and _BARE_BI_RE.match(_val):
                print(f"[Backlog] warning: unqualified ref {_val!r} in link(...) - "
                      f"use backlog.qualify(scope, project, id) to disambiguate across scopes")
    links = dict(item.get("links") or {})
    for k, v in refs.items():
        if v in (None, "", []):
            continue
        if isinstance(v, list) and not isinstance(links.get(k), list):
            links[k] = []
        if isinstance(v, list):
            links.setdefault(k, [])
            for x in v:
                if x not in links[k]:
                    links[k].append(x)
        else:
            links[k] = v
    return update(scope, project, eid, links=links)


def qualify(scope: str, project: Optional[str], eid: str) -> str:
    """Scope-qualified reference for an item id (BI-0082).

    ``BI-####`` ids are allocated per scope, so the same id exists in more than one
    scope. Always reference items with a scope-qualified ref:
      * ``product_forge:BI-0042``
      * ``project:ProductForge-Dashboard:BI-0015``
    """
    s = _norm_scope(scope)
    if s == "product_forge" or not project:
        return f"{s}:{eid}"
    return f"project:{project}:{eid}"


def parse_ref(ref: str):
    """Parse a qualified ref -> (scope, project, eid). Unqualified -> ('', None, ref)."""
    parts = str(ref or "").split(":")
    if len(parts) >= 2 and parts[0] == "product_forge":
        return "product_forge", None, parts[-1]
    if len(parts) >= 3 and parts[0] == "project":
        return "project", ":".join(parts[1:-1]), parts[-1]
    return "", None, str(ref or "")


def get_by_ref(ref: str) -> Optional[Dict]:
    """Resolve a (possibly qualified) reference to its item, across scopes."""
    scope, project, eid = parse_ref(ref)
    if not scope:
        return None
    return get_epic(scope, project, eid)


_CANON_LINK_ITEM_KEYS = ("backend_item", "backend_ref", "dashboard_item", "dashboard_ref",
                         "dashboard_scope_item", "dashboard_scope", "capability_ref")
_CANON_LINK_CAP_KEYS = ("backend_capability",)
_CANON_LINK_PAIR_KEYS = ("paired_with",) + _CANON_LINK_ITEM_KEYS


def _as_list(v):
    if v in (None, ""):
        return []
    return list(v) if isinstance(v, list) else [v]


def canonical_links(links: Optional[Dict]) -> Dict[str, List[str]]:
    """Canonical view of an item's ``links`` (back-compat: legacy keys still read).

    Canonical keys:
      * ``paired_with``        - scope-qualified ref(s) to the counterpart item; RECIPROCAL
                                 (set on both sides): backend item <-> dashboard item.
      * ``backend_capability`` - dashboard -> backend capability descriptor(s), e.g.
                                 ``module:core.x``, ``route:POST /api/v1/...``, ``stage:1a``,
                                 ``store:foo.json``.
      * ``capability_ref``     - item-ref bucket; read-compat alias folding the legacy
                                 ``backend_item`` / ``backend_ref`` / ``dashboard_item`` /
                                 ``dashboard_ref`` keys.
    """
    links = links or {}
    out: Dict[str, List[str]] = {"paired_with": [], "backend_capability": [], "capability_ref": []}
    for k in _CANON_LINK_PAIR_KEYS:
        for ref in _as_list(links.get(k)):
            if ref not in out["paired_with"]:
                out["paired_with"].append(ref)
    for k in _CANON_LINK_CAP_KEYS:
        for cap in _as_list(links.get(k)):
            if cap not in out["backend_capability"]:
                out["backend_capability"].append(cap)
    for k in _CANON_LINK_ITEM_KEYS:
        for ref in _as_list(links.get(k)):
            if ref not in out["capability_ref"]:
                out["capability_ref"].append(ref)
    return out


def _merge_links(links: Optional[Dict], **refs) -> Dict:
    """Merge ``refs`` (list-aware) into a copy of ``links`` (used by ``pair``)."""
    out = dict(links or {})
    for k, v in refs.items():
        if v in (None, "", []):
            continue
        if isinstance(v, list):
            cur = out.get(k)
            out[k] = list(cur) if isinstance(cur, list) else ([cur] if cur else [])
            for x in v:
                if x not in out[k]:
                    out[k].append(x)
        else:
            out[k] = v
    return out


def pair(scope: str, project: Optional[str], eid: str, other_ref: str,
         capability: Optional[str] = None) -> Optional[Dict]:
    """Cross-link two items RECIPROCALLY via canonical ``links.paired_with``.

    ``other_ref`` must be scope-qualified (``product_forge:BI-####`` /
    ``project:<p>:BI-####``). Writes ``paired_with`` on BOTH items. When called from the
    dashboard side, ``capability`` records the backend capability descriptor(s).
    """
    item = get_epic(scope, project, eid)
    if not item:
        return None
    other = get_by_ref(other_ref)
    if other is None:
        print(f"[Backlog] warning: pair(): cannot resolve {other_ref!r} (left one-sided)")
    back_ref = qualify(scope, project, eid)
    mine: Dict[str, Any] = {"paired_with": other_ref}
    if capability:
        mine["backend_capability"] = capability
    update(scope, project, eid, links=_merge_links(item.get("links"), **mine))
    if other:
        update(other.get("scope"), other.get("project"), other.get("id"),
               links=_merge_links(other.get("links"), paired_with=back_ref))
    return get_epic(scope, project, eid)


def set_dashboard_impact(scope: str, project: Optional[str], eid: str, needs_dashboard: bool,
                         reason: str, dashboard_item: Optional[str] = None,
                         reviewed_by: str = "agent", reviewed_at: str = "") -> Optional[Dict]:
    """Record the required ``dashboard_impact`` REVIEW decision on a backend-scope item.

    Non-forced: ``needs_dashboard=False`` with a reason is valid. Only when
    ``needs_dashboard=True`` is a (reciprocally linked) dashboard item required.
    """
    dec = {"needs_dashboard": bool(needs_dashboard), "reason": reason,
           "dashboard_item": dashboard_item, "reviewed_by": reviewed_by,
           "reviewed_at": reviewed_at or datetime.now().isoformat()}
    return update(scope, project, eid, dashboard_impact=dec, _note="dashboard_impact reviewed")


def set_follow_up(scope: str, project: Optional[str], eid: str, at: str = "",
                  every_days: int = _DEFAULT_REVIEW_DAYS, snooze_days: int = 0) -> Optional[Dict]:
    base = datetime.now()
    if at:
        try:
            base = datetime.fromisoformat(at)
        except Exception:
            base = datetime.now()
    fu = {"at": (base if at else base + timedelta(days=every_days)).isoformat(),
          "review_every": int(every_days)}
    if snooze_days:
        fu["snooze_until"] = (datetime.now() + timedelta(days=int(snooze_days))).isoformat()
    return update(scope, project, eid, follow_up=fu, _note="follow-up set")


def list_open(scope: str, project: Optional[str] = None, order: bool = True,
              origin: str = "", sec: str = "") -> List[Dict]:
    op, _cl = _load_all(scope, project)
    items = op
    if origin:
        items = [i for i in items if i.get("origin") == origin]
    if sec:
        items = [i for i in items if section(i) == sec]
    for it in items:
        it.setdefault("score", score(it))
        it["section"] = section(it)
    if order:
        items.sort(key=lambda e: (_MOSCOW_RANK.get(e.get("moscow", "Should"), 1),
                                  -float(e.get("score", 0)), e.get("created_at", "")))
    return items


def list_closed(scope: str, project: Optional[str] = None, origin: str = "") -> List[Dict]:
    _op, cl = _load_all(scope, project)
    items = cl
    if origin:
        items = [i for i in items if i.get("origin") == origin]
    for it in items:
        it["section"] = "done"
    return items


def get_epic(scope: str, project: Optional[str], eid: str) -> Optional[Dict]:
    op, cl = _load_all(scope, project)
    for e in op + cl:
        if e.get("id") == eid:
            return e
    return None


def list_items(scope: str, project: Optional[str] = None, status: str = "",
               section_: str = "") -> List[Dict]:
    """All items (open + closed) for a scope, optionally filtered by status/section."""
    op, cl = _load_all(scope, project)
    items = list(op) + list(cl)
    if status:
        items = [i for i in items
                 if _normalize_status(i.get("status", "")) == _normalize_status(status)]
    if section_:
        items = [i for i in items if section(i) == section_]
    return items


def get(scope: str, project: Optional[str], eid: str) -> Optional[Dict]:
    """Full item by id - the API way. Do NOT read backlog files directly."""
    return get_epic(scope, project, eid)


def history(scope: str, project: Optional[str], eid: str) -> List[Dict]:
    """The item's append-only journal (status + content-change entries)."""
    d, _of, _cf, h, _c = _paths(scope, project)
    out: List[Dict] = []
    try:
        with open(os.path.join(h, f"{eid}.jsonl"), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        pass
    except Exception:
        pass
    return out


def backfill_journal(scope: str, project: Optional[str], eid: str) -> Optional[Dict]:
    """Create ONE clearly-marked first journal line if an item has none (heals a pre-existing gap).

    Never fabricates a transition: event is 'backfill', timestamped at the item's created_at.
    No-op if a journal already exists.
    """
    it = get_epic(scope, project, eid)
    if not it:
        return None
    d, _of, _cf, h, _c = _paths(scope, project)
    fp = os.path.join(h, f"{eid}.jsonl")
    if os.path.exists(fp):
        return None
    try:
        os.makedirs(h, exist_ok=True)
        rec = {"at": it.get("created_at") or datetime.now().isoformat(), "event": "backfill",
               "status": it.get("status"), "section": section(it),
               "note": "journal created retroactively (pre-existing gap)"}
        with open(fp, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec
    except Exception:
        return None


def index_view(scope: str, project: Optional[str] = None) -> Dict:
    """The DERIVED lean index (tracking view): open/closed rows (id/status/one-liner/dates)."""
    op, cl = _load_all(scope, project)
    return {"scope": _norm_scope(scope), "project": project or "",
            "open": [_index_row(i) for i in op], "closed": [_index_row(i) for i in cl]}


def archive(scope: str, project: Optional[str], eid: str, note: str = "archived") -> Optional[Dict]:
    """Non-destructive retire: move the item to the terminal 'archived' status."""
    return update(scope, project, eid, status="archived", _note=note)


def delete(scope: str, project: Optional[str], eid: str) -> Optional[Dict]:
    """Remove an item's own files (item + journal) and refresh the index. Returns the item."""
    scope = _norm_scope(scope)
    d, _of, _cf, _h, _c = _paths(scope, project)
    lp = _lock(d)
    try:
        op, cl = _load_all(scope, project)
        target, bucket = _find(op, cl, eid)
        if target is None:
            return None
        bucket.remove(target)
        for p in (os.path.join(_items_dir(d), f"{eid}.json"),
                  os.path.join(d, "history", f"{eid}.jsonl")):
            try:
                os.remove(p)
            except Exception:
                pass
        _write_indexes(scope, project, op, cl)
        return target
    finally:
        _unlock(lp)


def update(scope: str, project: Optional[str], eid: str, **fields) -> Optional[Dict]:
    d, of, cf, _h, _c = _paths(scope, project)
    lp = _lock(d)
    try:
        op, cl = _load_all(scope, project)
        target, bucket = _find(op, cl, eid)
        if target is None:
            return None
        before = dict(target)
        target.update(fields)
        target["updated_at"] = datetime.now().isoformat()
        target["score"] = score(target)
        if "status" in fields:
            target["status"] = _normalize_status(target.get("status", ""))
        st = str(target.get("status", ""))
        if st in _CLOSED and bucket is op:
            op.remove(target)
            cl.append(target)
        elif st not in _CLOSED and bucket is cl:
            cl.remove(target)
            op.append(target)
        _save_item(d, target)
        _write_indexes(scope, project, op, cl)
        _hist(d, target, changes=_diff_fields(before, target), event="update")
        return target
    finally:
        _unlock(lp)


def triage(scope: str, project: Optional[str], eid: str,
           recommendation: str = "", value: Optional[int] = None,
           effort: Optional[int] = None, risk: Optional[int] = None,
           moscow: Optional[str] = None) -> Optional[Dict]:
    fields: Dict[str, Any] = {"status": "triaged", "_note": recommendation}
    if value is not None:
        fields["value"] = value
    if effort is not None:
        fields["effort"] = effort
    if risk is not None:
        fields["risk"] = risk
    if moscow:
        fields["moscow"] = moscow
    e = update(scope, project, eid, **fields)
    if e:
        dec = list(e.get("decisions") or [])
        dec.append({"at": datetime.now().isoformat(), "action": "triage", "note": recommendation})
        update(scope, project, eid, decisions=dec)
    return get_epic(scope, project, eid)


def accept(scope: str, project: Optional[str], eid: str, when: str = "later",
           by: str = "hil") -> Optional[Dict]:
    """when = 'now' (queue for scheduling) | 'later' (accepted, unscheduled)."""
    status = "queued" if when == "now" else "accepted"
    e = update(scope, project, eid, status=status, accepted_by=by, when=when,
               _note=f"accepted ({when}) by {by}")
    if e and _norm_scope(scope) == "project" and when == "now" and project:
        try:
            from core.portfolio import enqueue
            enqueue(project, "", 100, item_id=eid)
        except Exception:
            pass
    return e


def parked_review(days: int = 0) -> List[Dict]:
    """Parked items whose follow-up is due (weekly default) and not snoozed."""
    now = datetime.now()
    out = []
    for sc, pr in _all_scopes():
        for e in list_open(sc, pr, order=False):
            if e.get("status") != "parked":
                continue
            fu = e.get("follow_up") or {}
            due = fu.get("at", "")
            snooze = fu.get("snooze_until", "")
            try:
                if snooze and datetime.fromisoformat(snooze) > now:
                    continue
                if due and datetime.fromisoformat(due) > now:
                    continue
            except Exception:
                pass
            out.append(e)
    return out


def _all_scopes():
    scopes = [("product_forge", None)]
    try:
        for name in os.listdir(_PRODUCTS):
            if os.path.isdir(os.path.join(_PRODUCTS, name)) and not name.startswith((".", "_")):
                scopes.append(("project", name))
    except Exception:
        pass
    return scopes


def stale(days: int = 7, scope: str = "", project: Optional[str] = None) -> List[Dict]:
    """Open items untouched for > `days` (follow-up / event-router signal)."""
    scopes = [(scope, project)] if scope else _all_scopes()
    out = []
    for sc, pr in scopes:
        for e in list_open(sc, pr, order=False):
            if str(e.get("status")) in ("queued", "scheduled", "executing"):
                continue
            try:
                age = (datetime.now() - datetime.fromisoformat(
                    e.get("updated_at", e.get("created_at", "")))).days
            except Exception:
                age = 0
            if age >= days:
                out.append({**e, "_age_days": age})
    return out


def stats(scope: str, project: Optional[str] = None) -> Dict:
    op, cl = list_open(scope, project, order=False), list_closed(scope, project)
    by_status: Dict[str, int] = {}
    by_origin: Dict[str, int] = {}
    for e in op:
        by_status[e.get("status", "?")] = by_status.get(e.get("status", "?"), 0) + 1
        by_origin[e.get("origin", "?")] = by_origin.get(e.get("origin", "?"), 0) + 1
    return {"scope": _norm_scope(scope), "project": project or "", "open": len(op),
            "closed": len(cl), "by_status": by_status, "by_origin": by_origin}


def _dashboard_impact_ok(item: Dict) -> bool:
    """A recorded REVIEW decision = ``needs_dashboard`` (bool) + a non-empty reason."""
    di = item.get("dashboard_impact")
    if not isinstance(di, dict) or "needs_dashboard" not in di:
        return False
    return bool(str(di.get("reason") or "").strip())


def _dashboard_capability_claims(item: Dict) -> List[str]:
    cl = canonical_links(item.get("links"))
    return list(cl.get("backend_capability") or []) + list(cl.get("capability_ref") or [])


def _is_dashboard_item(item: Dict) -> bool:
    return _norm_scope(str(item.get("scope", ""))) == "project" \
        and bool(_dashboard_capability_claims(item))


def _reciprocal(a: Dict, b: Dict) -> bool:
    """True when BOTH items carry a paired_with ref to the other."""
    aref = qualify(a.get("scope"), a.get("project"), a.get("id"))
    bref = qualify(b.get("scope"), b.get("project"), b.get("id"))
    a_pairs = canonical_links(a.get("links")).get("paired_with") or []
    b_pairs = canonical_links(b.get("links")).get("paired_with") or []
    return (bref in a_pairs) and (aref in b_pairs)


def reciprocity_warnings(scope: str = "", project: Optional[str] = None) -> List[Dict]:
    """NON-FATAL warnings for the backend<->dashboard reciprocity REVIEW rule.

    Returns ``[{kind, ref, item, title, detail}]`` (never raises, never fails a build).
    Checks:
      1. ``missing_dashboard_impact`` - open backend-scope (product_forge) item with no
         recorded ``dashboard_impact`` decision (the REVIEW requirement).
      2. ``dashboard_capability_orphan`` - a dashboard item that claims a backend
         capability but has no RECIPROCAL ``paired_with`` link.
      3. ``needs_dashboard_unpaired`` - backend item whose decision says
         ``needs_dashboard=true`` but the ``dashboard_item`` ref is missing, unresolvable,
         or non-reciprocal.
    """
    warns: List[Dict] = []
    scopes = [(scope, project)] if scope else _all_scopes()
    for sc, pr in scopes:
        is_forge = _norm_scope(sc) == "product_forge"
        for e in list_open(sc, pr, order=False):
            ref = qualify(e.get("scope") or sc, e.get("project") or pr, e.get("id"))
            if is_forge:
                if str(e.get("status")) == "parked":
                    continue
                if not _dashboard_impact_ok(e):
                    warns.append({"kind": "missing_dashboard_impact", "ref": ref,
                                  "item": e.get("id"), "title": e.get("title", ""),
                                  "detail": "backend item has no recorded dashboard_impact review"})
                    continue
                di = e.get("dashboard_impact") or {}
                if di.get("needs_dashboard"):
                    dref = di.get("dashboard_item")
                    if not dref:
                        warns.append({"kind": "needs_dashboard_unpaired", "ref": ref,
                                      "item": e.get("id"), "title": e.get("title", ""),
                                      "detail": "needs_dashboard=true but dashboard_item is null"})
                    else:
                        other = get_by_ref(dref)
                        if other is None:
                            warns.append({"kind": "needs_dashboard_unpaired", "ref": ref,
                                          "item": e.get("id"), "title": e.get("title", ""),
                                          "detail": f"dashboard_item {dref} does not resolve"})
                        elif not _reciprocal(e, other):
                            warns.append({"kind": "needs_dashboard_unpaired", "ref": ref,
                                          "item": e.get("id"), "title": e.get("title", ""),
                                          "detail": f"dashboard_item {dref} is not reciprocally linked"})
            elif _is_dashboard_item(e):
                ok = False
                for pref in (canonical_links(e.get("links")).get("paired_with") or []):
                    other = get_by_ref(pref)
                    if other is not None and _reciprocal(e, other):
                        ok = True
                        break
                if not ok:
                    warns.append({"kind": "dashboard_capability_orphan", "ref": ref,
                                  "item": e.get("id"), "title": e.get("title", ""),
                                  "detail": "claims a backend capability without a reciprocal paired_with link"})
    return warns


def print_reciprocity_warnings(scope: str = "", project: Optional[str] = None) -> int:
    """Print ``reciprocity_warnings()`` (advisory). Returns the warning count."""
    warns = reciprocity_warnings(scope, project)
    if not warns:
        print("[Backlog] reciprocity: 0 warnings")
        return 0
    print(f"[Backlog] reciprocity: {len(warns)} warning(s) (non-fatal)")
    for w in warns:
        print(f"  - {w['kind']}: {w['ref']} - {w['detail']}")
    return len(warns)


def _cli(argv=None) -> int:
    """Dedup-before-add guard CLI: ``python -m core.backlog --similar "<text>"`` etc."""
    import argparse
    p = argparse.ArgumentParser(
        prog="python -m core.backlog",
        description="Backlog dedup guard: find near-duplicates BEFORE adding a work item.")
    p.add_argument("--similar", metavar="TEXT",
                   help="list near-duplicate items for TEXT (run this first)")
    p.add_argument("--scope", metavar="SCOPE", default=None,
                   help="product_forge | project | <project-name> (default: all scopes)")
    p.add_argument("--limit", type=int, default=10, help="max candidates (default 10)")
    p.add_argument("--duplicates", action="store_true",
                   help="list near-duplicate PAIRS among OPEN items")
    p.add_argument("--threshold", type=float, default=0.6,
                   help="similarity threshold for --duplicates (default 0.6)")
    a = p.parse_args(argv)

    if a.duplicates:
        pairs = duplicate_pairs(scope=a.scope, threshold=a.threshold)
        if not pairs:
            print(f"[Backlog] no near-duplicate OPEN pairs at threshold {a.threshold}")
            return 0
        print(f"[Backlog] {len(pairs)} near-duplicate OPEN pair(s) (threshold {a.threshold}):")
        for pr in pairs:
            print(f"   {pr['score']:.2f}  {pr['a']}  <->  {pr['b']}")
            print(f"        {pr['a_title']!r}")
            print(f"        {pr['b_title']!r}")
        return 0

    if a.similar is not None:
        res = find_similar(a.similar, scope=a.scope, limit=a.limit)
        if not res:
            print(f"[Backlog] no similar items for {a.similar!r} - safe to add")
            return 0
        print(f"[Backlog] {len(res)} similar item(s) for {a.similar!r} - "
              "EXTEND/MERGE instead of adding a new item:")
        for r in res:
            print(f"   {r['score']:.2f}  {r['ref']}  [{r['status']}]  {r['title']}")
        return 0

    p.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
