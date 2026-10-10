"""Backlog â€” the single work-item registry (one per scope).

Scopes:
  project        : products/<project>/backlog/
  product_forge  : product-forge/backlog/   (legacy read-fallback: products/backlog/)
  (legacy alias "portfolio" -> "product_forge")

Storage (per scope):
  items/<ID>.json      THE TRUTH - one full item per file (single writer)
  open.json            DERIVED index of non-terminal items (lean: id/status/one-liner/dates)
  closed.json          DERIVED index of terminal items
  counters.json        next "Backlog N" label
  history/<ID>.jsonl   append-only journal (status + content changes)

Ids: new items are ``BI-<TAG>-<nnn>`` where TAG is the destination (PF | DASH | IN |
<PROJECT-SLUG>); legacy ``BI-####`` ids remain valid and are read the same way.

Never read/write these files directly - use this module's API (list/get/update/history).

Model: BacklogItem
  id, tag, scope, project, origin(intake|pipeline), type(idea|project|change|feature|bug|tech-debt|explore),
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

import contextlib
import json
import os
import re
import time
from datetime import datetime, timedelta
from typing import Any

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

# ── PFSSOT (BI-PF-0362): first-class execution fields (all ADDITIVE; old items unaffected) ──
# analysis.status is versioned/stale-aware (doc §7/§8) - never a boolean.
ANALYSIS_STATUSES = ("NOT_ANALYZED", "IN_PROGRESS", "COMPLETE", "STALE")
ARCHITECTURE_FIT = ("REUSE", "EXTEND", "MODIFY", "NEW_COMPONENT", "NEW_CAPABILITY", "REFACTOR", "OTHER")
DRIFT_LEVELS = ("NONE", "LOW", "MEDIUM", "HIGH")
ANALYZE_MODES = ("on_entry", "defer")
DEP_TYPES = ("BLOCKS", "REQUIRES", "RELATED")
# fields whose change bumps `revision` (doc §38) - schedule/definition-affecting
_MATERIAL_FIELDS = ("title", "body", "deps", "dependencies", "priority", "priority_rank",
                    "moscow", "value", "effort", "risk", "links")
# fields whose change invalidates a COMPLETE analysis -> STALE (doc §8): requirement/architecture-
# affecting only. Priority/deps edits must NOT stale a completed analysis.
_STALE_FIELDS = ("title", "body", "dependencies", "links")


def _default_analysis() -> dict:
    return {"status": "NOT_ANALYZED", "analyzed_at": "", "analyzed_by": "", "revision_analyzed": 0,
            "architecture_fit": "", "implementation_strategy": "", "existing_components": [],
            "existing_apis": [], "existing_modules": [], "dependency_findings": [],
            "conflict_findings": [], "duplication_findings": [], "drift": "NONE",
            "rewrite_required": False, "new_component_required": False, "rationale": "",
            "assumptions": [], "risks": [], "evidence": [], "confidence": ""}


def _default_execution() -> dict:
    return {"worker_id": "", "assignment_id": "", "lease_id": "", "assigned_at": "",
            "lease_expires_at": "", "attempt": 0, "started_at": "", "completed_at": ""}


def _default_readiness(reasons: list[str] | None = None) -> dict:
    return {"ready": False, "reasons": reasons or [], "computed_at": ""}
_DASHBOARD_PROJECT = "ProductForge-Dashboard"   # dashboard scope for the reciprocity REVIEW rule


_LEGACY_FORGE_SCOPE = "fac" "tory"   # legacy scope alias found in early stored data


def _norm_scope(scope: str) -> str:
    return "product_forge" if scope in ("portfolio", "product_forge", _LEGACY_FORGE_SCOPE) else "project"


def _dir(scope: str, project: str | None = None) -> str:
    scope = _norm_scope(scope)
    if scope == "product_forge":
        legacy = os.path.join(_PRODUCTS, "backlog")
        new = os.path.join(_FORGE_DIR, "backlog")
        if not os.path.exists(new) and os.path.exists(legacy):
            return legacy
        return new
    return os.path.join(_PRODUCTS, project or "_unknown", "backlog")


def _paths(scope: str, project: str | None = None):
    d = _dir(scope, project)
    return (d, os.path.join(d, "open.json"), os.path.join(d, "closed.json"),
            os.path.join(d, "history"), os.path.join(d, "counters.json"))


def _rj(p, d):
    try:
        with open(p, encoding="utf-8") as f:
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


def _index_row(it: dict) -> dict:
    row = {k: it.get(k) for k in _INDEX_FIELDS}
    row["section"] = section(it)
    # PFSSOT: expose the schedule-relevant signals without loading every full item
    row["priority_rank"] = it.get("priority_rank")
    row["revision"] = int(it.get("revision") or 0)
    row["analysis_status"] = (it.get("analysis") or {}).get("status", "NOT_ANALYZED")
    row["ready"] = bool((it.get("readiness") or {}).get("ready"))
    row["worker_id"] = (it.get("execution") or {}).get("worker_id", "")
    return row


def _load_all(scope: str, project: str | None):
    """Return (open_items, closed_items) as FULL items from items/<ID>.json (the truth).

    Fallback: if `items/` is empty, read the legacy full-array open.json/closed.json so a
    not-yet-migrated scope still works (see `migrate_scope`).
    """
    d, of, cf, _h, _c = _paths(scope, project)
    idir = _items_dir(d)
    op: list[dict] = []
    cl: list[dict] = []
    try:
        names = [f for f in os.listdir(idir) if f.endswith(".json")] if os.path.isdir(idir) else []
    except Exception:
        names = []
    if names:
        seen = set()
        for fn in sorted(names):
            it = _rj(os.path.join(idir, fn), None)
            if not isinstance(it, dict) or not it.get("id"):
                continue
            (cl if _normalize_status(it.get("status", "new")) in _CLOSED else op).append(it)
            seen.add(str(it.get("id")))
        # BZ-C01/BU-C02: also surface legacy-only items so an interrupted/partial
        # migration never hides work; dedup by id (post-migration indexes share ids).
        lo, lc = _rj(of, []), _rj(cf, [])
        lo = lo.get("items") if isinstance(lo, dict) else lo
        lc = lc.get("items") if isinstance(lc, dict) else lc
        for it in list(lo or []) + list(lc or []):
            if isinstance(it, dict) and it.get("id") and str(it["id"]) not in seen:
                (cl if _normalize_status(it.get("status", "new")) in _CLOSED else op).append(it)
                seen.add(str(it["id"]))
        return op, cl
    lo, lc = _rj(of, []), _rj(cf, [])               # legacy layout
    lo = lo.get("items") if isinstance(lo, dict) else lo
    lc = lc.get("items") if isinstance(lc, dict) else lc
    return list(lo or []), list(lc or [])


def _save_item(d: str, item: dict) -> None:
    iid = str(item.get("id") or "")
    if not iid:
        return
    _wj(os.path.join(_items_dir(d), f"{iid}.json"), item)


def _write_indexes(scope: str, project: str | None, op: list[dict], cl: list[dict]) -> None:
    """Regenerate the DERIVED open/closed indexes (lean rows). Never hand-edited."""
    _d, of, cf, _h, _c = _paths(scope, project)
    _wj(of, [_index_row(i) for i in op])
    _wj(cf, [_index_row(i) for i in cl])


def migrate_scope(scope: str, project: str | None = None) -> dict:
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


_LOCK_STALE_SECONDS = 300


def _lock(d):
    os.makedirs(d, exist_ok=True)
    lp = os.path.join(d, ".lock")
    for _ in range(50):
        try:
            fd = os.open(lp, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return lp
        except FileExistsError:
            # Reclaim a lock left behind by a dead/hung writer (stale by mtime).
            try:
                if time.time() - os.path.getmtime(lp) > _LOCK_STALE_SECONDS:
                    os.remove(lp)
                    continue
            except Exception:
                pass
            time.sleep(0.1)
    # Fail closed (PF-025): never mutate the store without holding the lock.
    raise TimeoutError(f"[Backlog] could not acquire lock {lp} within timeout")


def _unlock(lp):
    with contextlib.suppress(Exception):
        os.remove(lp)


def _num(eid: str) -> int:
    """Sequence number from an id's final ``<nnn>`` segment.

    Only the substring after the LAST ``-`` is read, so digits embedded in the TAG/slug
    (e.g. ``BI-TESTBIPF02-0002``) never inflate the number (IS-PF-0033).
    """
    try:
        s = str(eid or "").strip()
        tail = s.rsplit("-", 1)[-1] if "-" in s else s
        m = re.search(r"\d+", tail)
        return int(m.group(0)) if m else 0
    except Exception:
        return 0


def _slug(project: str) -> str:
    """Uppercase alnum tag for a project name (max 10 chars)."""
    return re.sub(r"[^A-Za-z0-9]", "", str(project or "")).upper()[:10]


def tag_for(scope: str, project: str | None = None, origin: str = "",
            type_: str = "") -> str:
    """Short DESTINATION tag encoded in new ids (``BI-<TAG>-<nnn>``).

    Makes the destination recognizable from the id alone:
      * ``PF``     - Product Forge backend/pipeline (``scope=product_forge``)
      * ``DASH``   - the ProductForge-Dashboard
      * ``IN``     - a raw intake idea/explore/context not yet routed to a build target
      * ``<PROJ>`` - an uppercase slug of the project being built / existing project
    Legacy ``BI-####`` ids stay as-is (readers tolerate both).
    """
    p = str(project or "").strip()
    if p:
        if p.lower() == _DASHBOARD_PROJECT.lower():
            return "DASH"
        s = _slug(p)
        if s:
            return s
    if _norm_scope(scope) == "product_forge":
        if origin == "intake" and type_ in ("idea", "explore", "context"):
            return "IN"
        return "PF"
    return "PRJ"


def _next_id(open_items, closed_items, tagname: str, scope=None, project=None) -> str:
    mx = max([_num(e.get("id")) for e in list(open_items) + list(closed_items)] or [0])
    if scope is not None:
        try:
            from core import id_allocator
            if id_allocator.enabled():
                n = id_allocator.alloc(scope, project, existing_max=mx)
                return f"BI-{tagname or 'GEN'}-{n:04d}"
        except Exception:
            if id_allocator.strict():
                raise          # BI-PF-0966: strict must fail closed, never fall back to max+1
            pass
    return f"BI-{tagname or 'GEN'}-{mx + 1:04d}"


def _label_prefix(scope: str, project: str | None) -> str:
    return "PF" if _norm_scope(scope) == "product_forge" else (project or "Project")


def _next_label(counters: dict, scope: str, project: str | None) -> str:
    n = int(counters.get("next_label", 1))
    counters["next_label"] = n + 1
    return f"{_label_prefix(scope, project)} Backlog {n}"


def section(item: dict) -> str:
    st = _normalize_status(item.get("status", "new"))
    if st in _CLOSED:
        return "done"
    if st in _PIPELINE_STATUSES:
        return "pipeline"
    return "intake"


def score(e: dict) -> float:
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
                 "deps", "decisions", "follow_up", "dashboard_impact", "external_id",
                 "revision", "priority_rank", "analysis", "dependencies", "readiness", "execution")


def _diff_fields(old: dict, new: dict) -> dict:
    """Field-level before->after for the content journal (bodies summarized by length)."""
    out = {}
    for k in _JOURNAL_KEYS:
        a, b = old.get(k), new.get(k)
        if a == b:
            continue
        out[k] = ({"from_len": len(a or ""), "to_len": len(b or "")} if k == "body"
                  else {"from": a, "to": b})
    return out


def _find(op: list[dict], cl: list[dict], eid: str):
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


def _item_text(e: dict) -> str:
    return " ".join([str(e.get("title") or ""), str(e.get("body") or ""),
                     str(e.get("external_id") or "")])


def _scope_pairs(scope: str | None):
    """Resolve an optional scope selector -> [(scope, project), ...]."""
    if not scope:
        return _all_scopes()
    s = _norm_scope(scope)
    if s == "product_forge":
        return [("product_forge", None)]
    if scope == "project":
        return [(sc, pr) for sc, pr in _all_scopes() if sc == "project"]
    return [("project", scope)]


def find_similar(text: str, scope: str | None = None, limit: int = 5) -> list[dict]:
    """Rank existing items by token-set Jaccard similarity to ``text`` (title+body+external_id).

    Pure python (no external deps). Searches OPEN and CLOSED items so a just-merged
    duplicate is still surfaced. Returns candidates (score > 0) ranked high->low:
    ``{ref, id, scope, project, title, external_id, status, score}``.
    """
    q = _tokens(text)
    if not q:
        return []
    out: list[dict] = []
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


def duplicate_pairs(scope: str | None = None, threshold: float = 0.5,
                    limit: int = 50) -> list[dict]:
    """Near-duplicate OPEN-item pairs (Jaccard >= threshold), ranked by score."""
    out: list[dict] = []
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


def api_impact_warnings(scope: str = "product_forge", project: str | None = None) -> list:
    """BI-PF-1066 (E9): every OPEN item should record an ``api_impact`` DECISION.

    The decision is mandatory; the API is only built when needed (``needs_api=false`` + a reason is valid).
    Flags: (a) an open item with no ``api_impact`` decision, and (b) ``needs_api=true`` with no routes."""
    warns = []
    for it in list_open(scope, project):
        ai = it.get("api_impact")
        if not ai:
            warns.append(f"{it.get('id')}: no api_impact decision (needs_api + reason)")
        elif ai.get("needs_api") and not (ai.get("routes") or []):
            warns.append(f"{it.get('id')}: needs_api=true but no routes listed")
    return warns


def is_epic(item: dict | None) -> bool:
    """BI-PF-0446: an Epic is a container item (type == 'epic'), never directly executable."""
    return str((item or {}).get("type") or "") == "epic"


def _children_of(op: list, cl: list, epic_id: str) -> list:
    e = str(epic_id)
    return [i for i in (op + cl) if str(i.get("epic") or i.get("parent") or "") == e]


def _sync_epic_children(scope: str, project: str | None, epic_id: str) -> None:
    """Keep ``epic.children[]`` == the ids of items whose ``epic``/``parent`` == epic_id (bidirectional)."""
    if not epic_id:
        return
    op, cl = _load_all(scope, project)
    kids = [str(i.get("id")) for i in _children_of(op, cl, epic_id)]
    e = get_epic(scope, project, epic_id)
    if e is None:
        return
    if list(e.get("children") or []) != kids:
        update(scope, project, epic_id, children=kids, _note="epic children synced")


def epic_done(scope: str, project: str | None, epic_id: str) -> bool:
    """BI-PF-0446: an Epic is done iff it has children and ALL are terminal (computed rollup)."""
    op, cl = _load_all(scope, project)
    kids = _children_of(op, cl, epic_id)
    if not kids:
        return False
    return all(_normalize_status(str(k.get("status") or "")) in _CLOSED for k in kids)


_Ctx_FILE_RE = re.compile(r"[A-Za-z0-9_./-]+\.(?:py|json|md|yaml|yml|go|ts|tsx|js|toml|cfg)")


def _body_sections(body: str) -> dict:
    """Markdown heading -> section text (lower-cased heading keys)."""
    parts = re.split(r"(?m)^\s*#{1,6}\s*(.+?)\s*$", body or "")
    out = {"": parts[0].strip()}
    for i in range(1, len(parts) - 1, 2):
        out[parts[i].strip().lower()] = parts[i + 1].strip()
    return out


def _sec(sec: dict, *keys: str) -> str:
    for k, v in sec.items():
        if any(kk in k for kk in keys):
            return v
    return ""


def _ctx_bullets(text: str) -> list:
    return [re.sub(r"^\s*[-*]\s+", "", ln).strip() for ln in (text or "").splitlines()
            if re.match(r"^\s*[-*]\s+", ln) and re.sub(r"^\s*[-*]\s+", "", ln).strip()]


def _first_para(body: str) -> str:
    for blk in re.split(r"\n\s*\n", body or ""):
        t = re.sub(r"^\s*#{1,6}\s*.*$", "", blk, flags=re.M).strip()
        if len(t) >= 40:
            return t
    return ""


def _draft_context(title: str, body: str, origin: str = "", source: str = "", type_: str = "feature",
                   links: dict | None = None) -> dict:
    """Derive the FULL context set from the item's own body sections (BI-PF-0454/0563).

    Structured bodies (Problem/why, Goal/value, In scope, Out of scope, Approach, Acceptance, risks,
    rollback) yield concrete, implementable context; a body paragraph yields extracted context; an
    empty/insufficient body is flagged ``source='derived'`` (the open-item gate rejects derived).
    No ``(derived)`` placeholder text is ever emitted.
    """
    body = body or ""
    sec = _body_sections(body)
    title = title or "(unspecified)"
    problem = (_sec(sec, "problem", "why", "context") or _first_para(body) or "").strip()
    goal = (_sec(sec, "goal", "value", "what") or title).strip()
    in_scope = _ctx_bullets(_sec(sec, "in scope", "scope")) or [title]
    out_scope = _ctx_bullets(_sec(sec, "out of scope", "not in scope", "non-goal")) or ["Not specified."]
    ac = _ctx_bullets(_sec(sec, "acceptance", "testable", "definition of done")) or \
        [f"Objective achieved: {goal}"]
    approach = (_sec(sec, "approach", "plan", "design", "implementation").strip()
                or "; ".join(in_scope[:3]))
    caps = [c for c in ((links or {}).get("backend_capability") or []) if isinstance(c, str)]
    cap_paths = [c.split(":", 1)[1].strip() for c in caps
                 if c.startswith(("file:", "module:")) and "." in c.split(":", 1)[1]]
    files = sorted(set(_Ctx_FILE_RE.findall(body) + cap_paths)) or ["Not specified."]
    comps = sorted({f.split("/")[0] for f in files if "/" in f}) or ["Not specified."]
    structured = bool(_sec(sec, "problem", "goal", "in scope", "acceptance", "approach"))
    src = "authored" if structured else ("extracted" if problem else "derived")
    owner = {"review": "agent", "intake": "intake", "pipeline": "pipeline"}.get(str(origin), "unassigned")
    requester = "user" if "user" in str(source).lower() else (str(source) or str(origin) or "system")
    return {
        "brief": {"problem": (problem or goal)[:1200], "what_adds": goal[:600],
                  "why": (problem or goal)[:600],
                  "who_feels": "Product Forge maintainers and consumers.", "source": src},
        "objective": goal,
        "acceptance_criteria": ac,
        "in_scope": in_scope,
        "out_of_scope": out_scope,
        "affected_components": comps,
        "affected_files": files,
        "approach": approach,
        "review": {"reconciliation": {"prior_decisions": [], "existing_path": [], "assumptions": [],
                                      "divergences": [], "open_questions": []},
                   "impact_review": [], "reviewed_by": "derived", "at": ""},
        "verification": ac,
        "risks": _ctx_bullets(_sec(sec, "risk")) or ["Not specified."],
        "rollback": _sec(sec, "rollback").strip() or "Revert the change.",
        "evidence": ["pending"],
        "owner": owner,
        "requester": requester,
        "due": "",
        "target_release": "",
        "approvals": [],
        "summary": goal if str(type_) == "epic" else "",
    }


def add_epic(scope: str, project: str | None, title: str, body: str = "",
             source: str = "generic", type_: str = "feature", origin: str = "intake",
             value: int = 3, effort: int = 3, risk: int = 2, moscow: str = "Should",
             deps: list[str] | None = None, links: dict | None = None,
             external_id: str = "", tag: str = "",
             brief: dict | None = None, objective: str = "",
             acceptance_criteria: list[str] | None = None, epic: str = "",
             summary: str = "") -> dict:
    """Create a work item. `external_id` (e.g. feature_id/defect_id/conversation_id) makes it idempotent.

    `tag` overrides the destination tag encoded in the id (see ``tag_for``).
    """
    scope = _norm_scope(scope)
    _validate_fields({"links": links, "deps": deps})
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
        _tag = str(tag or "").strip().upper() or tag_for(scope, project, origin, type_)
        _draft_ctx = _draft_context(title, body, origin, source, type_, links=links)
        item = {
            "id": _next_id(op, cl, _tag, scope, project),
            "tag": _tag, "type": type_, "scope": scope, "project": project or "",
            "origin": origin, "external_id": external_id, "label": _next_label(counters, scope, project),
            "title": title, "body": body, "source": source, "status": "new",
            "priority": None, "moscow": moscow, "value": value, "effort": effort, "risk": risk,
            "deps": deps or [], "links": links or {}, "decisions": [], "follow_up": {},
            # BI-PF-0445: authored context (WHY/WHAT/WHERE/HOW/REVIEW/WHO/WHEN/APPROVAL/EVIDENCE)
            "brief": dict(brief or {}) or _draft_ctx["brief"], "objective": objective or _draft_ctx["objective"],
            "acceptance_criteria": list(acceptance_criteria or []) or _draft_ctx["acceptance_criteria"],
            "in_scope": [], "out_of_scope": [], "affected_components": [], "affected_files": [],
            "approach": "", "review": {}, "verification": [], "risks": [], "rollback": "",
            "evidence": [], "owner": "", "requester": "", "due": "", "target_release": "",
            "approvals": [], "summary": summary or "", "children": [],
            "epic": str(epic or ""), "parent": str(epic or ""),
            # PFSSOT first-class execution fields (additive; BI-PF-0362)
            "revision": 1, "priority_rank": None, "priority_class": "",
            "analyze_mode": "on_entry", "analysis": _default_analysis(),
            "dependencies": [], "blocked_by": [], "unlocks": [],
            "readiness": _default_readiness(), "execution": _default_execution(),
            "created_at": datetime.now().isoformat(), "updated_at": datetime.now().isoformat(),
        }
        for _k, _v in _draft_ctx.items():
            if _k not in ("brief", "objective", "acceptance_criteria") and not item.get(_k):
                item[_k] = _v
        item["score"] = score(item)
        op.append(item)
        _save_item(d, item)
        _write_indexes(scope, project, op, cl)
        _wj(ctr, counters)
        _hist(d, item, changes={"created": True}, event="created")
        created = item
    finally:
        _unlock(lp)
    if epic:
        with contextlib.suppress(Exception):
            _sync_epic_children(scope, project, str(epic))
    # PFSSOT-P3 (BI-PF-0364): deep analysis at grooming time, by default, so the item is scheduler-ready.
    # Runs AFTER the lock is released (it re-writes analysis via this module). Best-effort: never blocks create.
    # AUTOMATIC entry uses DETERMINISTIC deep analysis (fast, offline-safe); AI grooming is the default only
    # for the explicit/interactive groom call (`/pf groom`, POST /groom) - an automated create must never
    # block on a live model. (Follow-up: raise a background AI groom where a worker pool exists.)
    if created.get("analyze_mode", "on_entry") == "on_entry":
        with contextlib.suppress(Exception):
            from core import grooming
            grooming.groom(scope, project, created["id"], mode="deterministic",
                           depth=grooming.guidelines().get("default_depth", "deep"))
    return created


def ensure_item(scope: str, project: str | None, external_id: str, title: str,
                type_: str = "feature", origin: str = "pipeline", tag: str = "", **fields) -> dict:
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
                    external_id=external_id, tag=tag, **fields)


def set_status(scope: str, project: str | None, eid: str, status: str, note: str = "",
               force: bool = False) -> dict | None:
    # RCCA gate (1:1 with the issue tracker): a backlog item linked to an issue may only
    # reach a COMPLETED state after that issue records a complete RCCA (root_cause +
    # corrective + fixed_where). Fail closed unless forced with an audited override.
    if not force and status in {"completed", "closed", "done"}:
        it = get_epic(scope, project, eid)
        _ref = ((it or {}).get("links") or {}).get("issue")
        _refs = _ref if isinstance(_ref, list) else ([_ref] if _ref else [])
        for _r in _refs:
            try:
                from core import issues as _iss
                ok, reason = _iss.can_close_ref(_r)
            except Exception as e:
                ok, reason = False, f"issue check failed: {e}"
            if not ok:
                print(f"[Backlog] refusing to close {eid}: {reason}")
                return it
    return update(scope, project, eid, status=status, _note=note)


_BARE_BI_RE = re.compile(r"^BI-(?:[A-Za-z0-9]+-)?\d+$")


def link(scope: str, project: str | None, eid: str, **refs) -> dict | None:
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


def qualify(scope: str, project: str | None, eid: str) -> str:
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


def get_by_ref(ref: str) -> dict | None:
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


def canonical_links(links: dict | None) -> dict[str, list[str]]:
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
    out: dict[str, list[str]] = {"paired_with": [], "backend_capability": [], "capability_ref": []}
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


def _merge_links(links: dict | None, **refs) -> dict:
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


def pair(scope: str, project: str | None, eid: str, other_ref: str,
         capability: str | None = None) -> dict | None:
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
    mine: dict[str, Any] = {"paired_with": other_ref}
    if capability:
        mine["backend_capability"] = capability
    update(scope, project, eid, links=_merge_links(item.get("links"), **mine))
    if other:
        update(other.get("scope"), other.get("project"), other.get("id"),
               links=_merge_links(other.get("links"), paired_with=back_ref))
    return get_epic(scope, project, eid)


def set_dashboard_impact(scope: str, project: str | None, eid: str, needs_dashboard: bool,
                         reason: str, dashboard_item: str | None = None,
                         reviewed_by: str = "agent", reviewed_at: str = "") -> dict | None:
    """Record the required ``dashboard_impact`` REVIEW decision on a backend-scope item.

    Non-forced: ``needs_dashboard=False`` with a reason is valid. Only when
    ``needs_dashboard=True`` is a (reciprocally linked) dashboard item required.
    """
    dec = {"needs_dashboard": bool(needs_dashboard), "reason": reason,
           "dashboard_item": dashboard_item, "reviewed_by": reviewed_by,
           "reviewed_at": reviewed_at or datetime.now().isoformat()}
    return update(scope, project, eid, dashboard_impact=dec, _note="dashboard_impact reviewed")


def set_delivery(scope: str, project: str | None, eid: str, *, branch: str = "",
                 merge_sha: str = "", commits: list[str] | None = None, pr: str = "",
                 pr_url: str = "", note: str = "") -> dict | None:
    """Record delivery provenance on a work item: the branch, merge SHA and PR that delivered it.

    Completes the traceability loop (backlog item -> branch -> commit/merge -> PR) once work is reviewed,
    validated and merged. Stored under ``links.delivery`` (raw links preserved).
    """
    item = get_epic(scope, project, eid)
    if not item:
        return None
    delivery = {"branch": str(branch or ""), "merge_sha": str(merge_sha or ""),
                "commits": [str(c) for c in (commits or [])], "pr": str(pr or ""),
                "pr_url": str(pr_url or ""), "at": datetime.now().isoformat(), "note": str(note or "")}
    return update(scope, project, eid, links=_merge_links(item.get("links"), delivery=delivery),
                  _note="delivery recorded")


def set_execution_order(scope: str, project: str | None, epic_id: str, order: list) -> dict | None:
    """Persist the DERIVED epic execution order on the epic container (BI-PF-1222). Single writer.

    ``order`` is the ordered row list from ``core.scheduler.epic_order``; stored on the epic as
    ``execution_order[]`` (each ``{id, wave, status}``) plus ``execution_order_at``. This is the ORDER ONLY -
    ``children[]`` (membership) is never touched. Returns the updated epic, or ``None`` if not found.
    """
    if get_epic(scope, project, epic_id) is None:
        return None
    rows = [{"id": str(r.get("id")), "wave": int(r.get("wave") or 0), "status": str(r.get("status") or "")}
            for r in (order or []) if isinstance(r, dict) and r.get("id")]
    return update(scope, project, epic_id, execution_order=rows,
                  execution_order_at=datetime.now().isoformat(),
                  _note="epic execution order saved")


# ── PFSSOT (BI-PF-0362): first-class execution helpers (all reuse `update`, no new store) ──
def set_analysis(scope: str, project: str | None, eid: str, *, status: str = "",
                 architecture_fit: str = "", implementation_strategy: str = "",
                 analysis: dict | None = None, analyzed_by: str = "ai") -> dict | None:
    """Attach/refresh the architecture analysis block (doc §6.5/§7). Additive; marks STALE-aware."""
    item = get_epic(scope, project, eid)
    if not item:
        return None
    a = dict(item.get("analysis") or _default_analysis())
    if analysis:
        a.update(analysis)
    if status:
        st = str(status).upper()
        if st not in ANALYSIS_STATUSES:
            raise ValueError(f"analysis.status must be one of {list(ANALYSIS_STATUSES)}")
        a["status"] = st
        if st == "COMPLETE":
            a["analyzed_at"] = datetime.now().isoformat()
            a["analyzed_by"] = analyzed_by
            a["revision_analyzed"] = int(item.get("revision") or 0)
            a["arch_fingerprint"] = arch_fingerprint()  # BI-PF-0389: version-aware analysis
    if architecture_fit:
        fit = str(architecture_fit).upper()
        if fit not in ARCHITECTURE_FIT:
            raise ValueError(f"architecture_fit must be one of {list(ARCHITECTURE_FIT)}")
        a["architecture_fit"] = fit
    if implementation_strategy:
        a["implementation_strategy"] = implementation_strategy
    return update(scope, project, eid, analysis=a, _note="analysis updated")


def set_priority(scope: str, project: str | None, eid: str, *, priority: str | None = None,
                 priority_rank: int | None = None, priority_class: str = "",
                 moscow: str = "") -> dict | None:
    """Set/refine priority + deterministic priority_rank (doc §6.3)."""
    fields: dict = {}
    if priority is not None:
        fields["priority"] = priority
    if priority_rank is not None:
        fields["priority_rank"] = int(priority_rank)
    if priority_class:
        fields["priority_class"] = str(priority_class)
    if moscow:
        fields["moscow"] = moscow
    if not fields:
        return get_epic(scope, project, eid)
    fields["_note"] = "priority set"
    return update(scope, project, eid, **fields)


def _dep_reaches(graph: dict, start: str, goal: str, seen=None) -> bool:
    """True if ``goal`` is reachable from ``start`` following REQUIRES edges (cycle test)."""
    if start == goal:
        return True
    seen = seen if seen is not None else set()
    if start in seen:
        return False
    seen.add(start)
    return any(_dep_reaches(graph, str(m), goal, seen) for m in graph.get(start, []))


def _requires_graph(items: list, exclude: str = "") -> dict:
    """Map item id -> REQUIRES targets (dependencies whose type is REQUIRES)."""
    g = {}
    for i in items:
        x = str(i.get("id"))
        if x == exclude:
            continue
        g[x] = [str(d.get("task_id")) for d in (i.get("dependencies") or [])
                if isinstance(d, dict) and str(d.get("type") or "").upper() == "REQUIRES"]
    return g


def set_dependencies(scope: str, project: str | None, eid: str, *,
                     dependencies: list[dict] | None = None, blocked_by: list[str] | None = None,
                     unlocks: list[str] | None = None) -> dict | None:
    """Set structured dependencies (doc A6.4: BLOCKS/REQUIRES/RELATED + required_state).

    Fail-safe guard (single writer): a dependency is DROPPED (never stored) when it would be invalid,
    regardless of caller - self-reference, unknown id, a child depending on its own parent epic, or a
    REQUIRES edge that would form a cycle. Valid edges are kept; dropped ones are printed.

    Also keeps the flat ``deps`` list in sync (backward-compat with the scheduler).
    """
    fields: dict = {}
    rejected: list[str] = []
    if dependencies is not None or blocked_by is not None:
        op, cl = _load_all(scope, project)
        by_id = {str(i.get("id")): i for i in op + cl}
        me = by_id.get(str(eid)) or {}
        my_epic = str(me.get("epic") or me.get("parent") or "")
        graph = _requires_graph(op + cl, exclude=str(eid))

        def _ok(tid: str, hard: bool) -> bool:
            if tid == str(eid):
                rejected.append(f"{tid} (self)"); return False
            if tid not in by_id:
                rejected.append(f"{tid} (unknown)"); return False
            if my_epic and tid == my_epic:
                rejected.append(f"{tid} (parent epic)"); return False
            if hard and _dep_reaches(graph, tid, str(eid)):
                rejected.append(f"{tid} (cycle)"); return False
            return True

        if dependencies is not None:
            clean = []
            for d in dependencies:
                if not isinstance(d, dict) or not (d.get("task_id") or d.get("id")):
                    raise ValueError("each dependency needs a task_id")
                t = str(d.get("type") or "BLOCKS").upper()
                if t not in DEP_TYPES:
                    raise ValueError(f"dependency type must be one of {list(DEP_TYPES)}")
                tid = str(d.get("task_id") or d.get("id"))
                if not _ok(tid, t == "REQUIRES"):
                    continue
                clean.append({"task_id": tid, "type": t,
                              "required_state": str(d.get("required_state") or "completed")})
            fields["dependencies"] = clean
            fields["deps"] = [c["task_id"] for c in clean]
        if blocked_by is not None:
            fields["blocked_by"] = [str(x) for x in blocked_by if _ok(str(x), True)]
    if unlocks is not None:
        fields["unlocks"] = [str(x) for x in unlocks]
    if rejected:
        print(f"[Backlog] {eid}: dropped invalid dependencies: {rejected}")
    fields["_note"] = "dependencies set"
    return update(scope, project, eid, **fields)


def set_execution(scope: str, project: str | None, eid: str, **kw) -> dict | None:
    """Record worker assignment/lease state on the item (doc §13)."""
    item = get_epic(scope, project, eid)
    if not item:
        return None
    ex = dict(item.get("execution") or _default_execution())
    ex.update({k: v for k, v in kw.items() if k in ex})
    return update(scope, project, eid, execution=ex, _note="execution updated")


def set_readiness(scope: str, project: str | None, eid: str, ready: bool,
                  reasons: list[str] | None = None) -> dict | None:
    rd = {"ready": bool(ready), "reasons": [str(r) for r in (reasons or [])],
          "computed_at": datetime.now().isoformat()}
    return update(scope, project, eid, readiness=rd, _note="readiness computed")


# ── BI-PF-0389: architecture-version-aware analysis (staleness revalidation) ──
_DEFAULT_ARCH_SIGNIFICANT = (
    "config/store-registry.json", "config/engineering-flow.json", "config/engineering-workers.json",
    "config/env-flags.json", "config/grooming-guidelines.json", "config/pidl-profile.json",
    "config/approval-policy.json", "config/model-tier.json",
)


def _arch_significant_paths() -> list[str]:
    """Architecture-significant files (configurable via grooming-guidelines.arch_significant)."""
    import glob
    base = list(_DEFAULT_ARCH_SIGNIFICANT)
    try:
        from core import grooming
        cfg = grooming.guidelines().get("arch_significant")
        if isinstance(cfg, list) and cfg:
            base = [str(p) for p in cfg]
    except Exception:
        pass
    out: set[str] = set()
    for p in base:
        out.update(glob.glob(os.path.join(_REPO, p), recursive=True))
    return sorted(out)


def arch_fingerprint() -> str:
    """Stable hash of architecture-significant files. A change => COMPLETE analyses become STALE."""
    import hashlib
    h = hashlib.sha256()
    for p in _arch_significant_paths():
        h.update(os.path.relpath(p, _REPO).replace("\\", "/").encode("utf-8"))
        try:
            with open(p, "rb") as f:
                h.update(f.read())
        except Exception:
            h.update(b"?")
    return h.hexdigest()[:16]


def analysis_is_stale(item: dict[str, Any]) -> bool:
    """True if a COMPLETE analysis was recorded against a different architecture fingerprint.

    Legacy analyses without a fingerprint are NOT force-staled (backward compatible).
    """
    a = item.get("analysis") or {}
    st = str(a.get("status"))
    if st == "STALE":
        return True
    if st != "COMPLETE":
        return False
    rec = str(a.get("arch_fingerprint") or "")
    if not rec:
        return False
    return rec != arch_fingerprint()


def mark_stale(scope: str, project: str | None, eid: str, reason: str = "") -> dict | None:
    """Force an analysis to STALE (e.g. a related component changed)."""
    item = get_epic(scope, project, eid)
    if not item:
        return None
    a = dict(item.get("analysis") or _default_analysis())
    a["status"] = "STALE"
    if reason:
        a["stale_reason"] = str(reason)
    return update(scope, project, eid, analysis=a, _note="analysis marked stale")


def set_follow_up(scope: str, project: str | None, eid: str, at: str = "",
                  every_days: int = _DEFAULT_REVIEW_DAYS, snooze_days: int = 0) -> dict | None:
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


def list_open(scope: str, project: str | None = None, order: bool = True,
              origin: str = "", sec: str = "") -> list[dict]:
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


def order_by_priority(items: list[dict]) -> list[dict]:
    """Deterministic scheduler ordering (doc §6.3/§11): priority_rank -> moscow -> score -> created_at.

    ``priority_rank`` (low = higher priority) wins; items without it sort after ranked ones.
    Never depends on creation order alone.
    """
    def key(e: dict):
        pr = e.get("priority_rank")
        return (0 if pr is not None else 1, int(pr) if pr is not None else 10 ** 9,
                _MOSCOW_RANK.get(e.get("moscow", "Should"), 1),
                -float(e.get("score", 0)), e.get("created_at", ""))
    return sorted(items, key=key)


def list_closed(scope: str, project: str | None = None, origin: str = "") -> list[dict]:
    _op, cl = _load_all(scope, project)
    items = cl
    if origin:
        items = [i for i in items if i.get("origin") == origin]
    for it in items:
        it["section"] = "done"
    return items


def get_epic(scope: str, project: str | None, eid: str) -> dict | None:
    op, cl = _load_all(scope, project)
    for e in op + cl:
        if e.get("id") == eid:
            return e
    return None


def list_items(scope: str, project: str | None = None, status: str = "",
               section_: str = "") -> list[dict]:
    """All items (open + closed) for a scope, optionally filtered by status/section."""
    op, cl = _load_all(scope, project)
    items = list(op) + list(cl)
    if status:
        items = [i for i in items
                 if _normalize_status(i.get("status", "")) == _normalize_status(status)]
    if section_:
        items = [i for i in items if section(i) == section_]
    return items


def get(scope: str, project: str | None, eid: str) -> dict | None:
    """Full item by id - the API way. Do NOT read backlog files directly."""
    return get_epic(scope, project, eid)


def history(scope: str, project: str | None, eid: str) -> list[dict]:
    """The item's append-only journal (status + content-change entries)."""
    d, _of, _cf, h, _c = _paths(scope, project)
    out: list[dict] = []
    try:
        with open(os.path.join(h, f"{eid}.jsonl"), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    with contextlib.suppress(Exception):
                        out.append(json.loads(line))
    except Exception:
        pass
    return out


def backfill_journal(scope: str, project: str | None, eid: str) -> dict | None:
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


def index_view(scope: str, project: str | None = None) -> dict:
    """The DERIVED lean index (tracking view): open/closed rows (id/status/one-liner/dates)."""
    op, cl = _load_all(scope, project)
    return {"scope": _norm_scope(scope), "project": project or "",
            "open": [_index_row(i) for i in op], "closed": [_index_row(i) for i in cl]}


def archive(scope: str, project: str | None, eid: str, note: str = "archived") -> dict | None:
    """Non-destructive retire: move the item to the terminal 'archived' status."""
    return update(scope, project, eid, status="archived", _note=note)


def delete(scope: str, project: str | None, eid: str) -> dict | None:
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
            with contextlib.suppress(Exception):
                os.remove(p)
        _write_indexes(scope, project, op, cl)
        return target
    finally:
        _unlock(lp)


_STRUCT_FIELD_TYPES = {
    "analysis": (dict,),
    "dashboard_impact": (dict,),
    "links": (dict,),
    "delivery": (dict,),
    "decisions": (list,),
    "deps": (list,),
    # BI-PF-0445: authored context fields (type-checked like the rest)
    "brief": (dict,),
    "review": (dict,),
    "acceptance_criteria": (list,),
    "in_scope": (list,),
    "out_of_scope": (list,),
    "affected_components": (list,),
    "affected_files": (list,),
    "verification": (list,),
    "risks": (list,),
    "evidence": (list,),
    "approvals": (list,),
    "children": (list,),
    "api_impact": (dict,),
    "execution_order": (list,),
}


def _validate_fields(fields: dict) -> None:
    """Fail-closed (BI-PF-0441): reject a wrong-typed structured field BEFORE any write, so a bad call can
    never corrupt the item or crash a later index write. ``None`` is allowed for each (means 'clear')."""
    for k, types in _STRUCT_FIELD_TYPES.items():
        if k in fields and fields[k] is not None and not isinstance(fields[k], types):
            want = "|".join(t.__name__ for t in types)
            raise ValueError(f"backlog field {k!r} must be {want} or None, got {type(fields[k]).__name__}")


def update(scope: str, project: str | None, eid: str, **fields) -> dict | None:
    _validate_fields(fields)
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
        # PFSSOT (BI-PF-0362): bump revision when a schedule/definition field materially changes,
        # and mark a COMPLETE analysis STALE (revalidate before assignment, doc §8/§38) only when a
        # REQUIREMENT/ARCHITECTURE-affecting field changed - never on a priority/dep bookkeeping edit.
        if any(before.get(k) != target.get(k) for k in _MATERIAL_FIELDS):
            target["revision"] = int(target.get("revision") or 0) + 1
            an = dict(target.get("analysis") or {})
            if an.get("status") == "COMPLETE" and any(before.get(k) != target.get(k) for k in _STALE_FIELDS):
                an["status"] = "STALE"
                target["analysis"] = an
        st = str(target.get("status", ""))
        # BI-PF-0446: an Epic cannot be closed while any child is still open (done = rollup)
        if (str(target.get("type", "")) == "epic" and "status" in fields
                and _normalize_status(st) in _CLOSED):
            kids = _children_of(op, cl, str(target.get("id")))
            open_kids = [k for k in kids if _normalize_status(str(k.get("status") or "")) not in _CLOSED]
            if kids and open_kids:
                raise ValueError(f"epic {target.get('id')} cannot be closed: {len(open_kids)} child(ren) still open")
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


def triage(scope: str, project: str | None, eid: str,
           recommendation: str = "", value: int | None = None,
           effort: int | None = None, risk: int | None = None,
           moscow: str | None = None) -> dict | None:
    fields: dict[str, Any] = {"status": "triaged", "_note": recommendation}
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


def accept(scope: str, project: str | None, eid: str, when: str = "later",
           by: str = "hil") -> dict | None:
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


def parked_review(days: int = 0) -> list[dict]:
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


def stale(days: int = 7, scope: str = "", project: str | None = None) -> list[dict]:
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


def stats(scope: str, project: str | None = None) -> dict:
    op, cl = list_open(scope, project, order=False), list_closed(scope, project)
    by_status: dict[str, int] = {}
    by_origin: dict[str, int] = {}
    for e in op:
        by_status[e.get("status", "?")] = by_status.get(e.get("status", "?"), 0) + 1
        by_origin[e.get("origin", "?")] = by_origin.get(e.get("origin", "?"), 0) + 1
    return {"scope": _norm_scope(scope), "project": project or "", "open": len(op),
            "closed": len(cl), "by_status": by_status, "by_origin": by_origin}


def _dashboard_impact_ok(item: dict) -> bool:
    """A recorded REVIEW decision = ``needs_dashboard`` (bool) + a non-empty reason."""
    di = item.get("dashboard_impact")
    if not isinstance(di, dict) or "needs_dashboard" not in di:
        return False
    return bool(str(di.get("reason") or "").strip())


def _dashboard_capability_claims(item: dict) -> list[str]:
    cl = canonical_links(item.get("links"))
    return list(cl.get("backend_capability") or []) + list(cl.get("capability_ref") or [])


def _is_dashboard_item(item: dict) -> bool:
    return _norm_scope(str(item.get("scope", ""))) == "project" \
        and bool(_dashboard_capability_claims(item))


def _reciprocal(a: dict, b: dict) -> bool:
    """True when BOTH items carry a paired_with ref to the other."""
    aref = qualify(a.get("scope"), a.get("project"), a.get("id"))
    bref = qualify(b.get("scope"), b.get("project"), b.get("id"))
    a_pairs = canonical_links(a.get("links")).get("paired_with") or []
    b_pairs = canonical_links(b.get("links")).get("paired_with") or []
    return (bref in a_pairs) and (aref in b_pairs)


def reciprocity_warnings(scope: str = "", project: str | None = None) -> list[dict]:
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
    warns: list[dict] = []
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


def print_reciprocity_warnings(scope: str = "", project: str | None = None) -> int:
    """Print ``reciprocity_warnings()`` (advisory). Returns the warning count."""
    warns = reciprocity_warnings(scope, project)
    if not warns:
        print("[Backlog] reciprocity: 0 warnings")
        return 0
    print(f"[Backlog] reciprocity: {len(warns)} warning(s) (non-fatal)")
    for w in warns:
        print(f"  - {w['kind']}: {w['ref']} - {w['detail']}")
    return len(warns)


def verify(scope: str, project: str | None = None) -> dict:
    """Cross-store integrity check (BU-C02/BZ-C02): items/ truth vs derived indexes.

    Reads the truth (``items/<ID>.json``) and the derived ``open.json``/``closed.json`` lean
    indexes and reports drift: an index row with no item (``missing_item``), a status that
    disagrees with the item (``status_mismatch``), or an item absent from both indexes
    (``unindexed_item``). A legacy (not-yet-migrated) scope is treated as OK.
    """
    d, of, cf, _h, _c = _paths(scope, project)
    idir = _items_dir(d)
    ids: dict[str, str] = {}
    try:
        for fn in (os.listdir(idir) if os.path.isdir(idir) else []):
            if not fn.endswith(".json"):
                continue
            it = _rj(os.path.join(idir, fn), None)
            if isinstance(it, dict) and it.get("id"):
                ids[str(it["id"])] = _normalize_status(it.get("status", "new"))
    except Exception:
        pass
    drift: list[dict] = []
    indexed = set()
    for path in (of, cf):
        rows = _rj(path, [])
        rows = rows.get("items") if isinstance(rows, dict) else rows
        for r in (rows or []):
            if not isinstance(r, dict) or not r.get("id"):
                continue
            rid = str(r["id"])
            indexed.add(rid)
            if rid not in ids:
                drift.append({"kind": "missing_item", "id": rid})
                continue
            st = _normalize_status(r.get("status") or "")
            if st != ids[rid]:
                drift.append({"kind": "status_mismatch", "id": rid, "index": st, "item": ids[rid]})
    for rid in ids:
        if rid not in indexed:
            drift.append({"kind": "unindexed_item", "id": rid})
    return {"ok": (not ids) or (not drift), "scope": scope,
            "counts": {"items": len(ids), "indexed": len(indexed)}, "drift": drift}


def _cli(argv=None) -> int:
    """Dedup-before-add guard CLI: ``python -m core.backlog --similar "<text>"`` etc."""
    import argparse
    # BI-PF-0257: Windows consoles default to cp1252 and crash on non-Latin chars
    # (e.g. '→' in item titles). Force UTF-8 with replacement, never raise on print.
    try:
        import sys as _sys
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
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
