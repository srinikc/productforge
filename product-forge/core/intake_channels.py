"""Intake channels — the funnel's front door.

Every external capture (ChatGPT / Claude / Gemini / other / manual) lands in ONE
channel folder under ``products/intake/`` and is assigned an ``IN-####`` id, then
becomes exactly one backlog item in the correct scope. One writer (this module).

Layout (config: config/intake-channels.json):
  products/intake/ideas/
  products/intake/new-project/
  products/intake/existing-project/<project>/
  products/intake/productforge-backend/
  products/intake/productforge-dashboard/

Per channel:
  items.jsonl   append-only intake entries
  index.json    IN-id -> {channel, source, intent, status, backlog_ref, links}

Status flow: received -> analyzed -> (queued|scheduled) -> executing ->
implemented -> verifying -> closed   (blocked on failure). An intake item closes
ONLY when the linked backlog item is verified (see close_verified()).
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
from datetime import datetime
from typing import Dict, List, Optional

REPO_ROOT = str(_PF_ROOT)
_CONFIG = os.path.join(REPO_ROOT, "config", "intake-channels.json")

_DEFAULT = {
    "root": "products/intake",
    "channels": {
        "idea": "ideas",
        "new_project": "new-project",
        "existing_project": "existing-project",
        "productforge_backend": "productforge-backend",
        "productforge_dashboard": "productforge-dashboard",
    },
    "sources": ["chatgpt", "claude", "gemini", "other", "manual"],
}

_cfg_cache = None


def config() -> Dict:
    global _cfg_cache
    if _cfg_cache is not None:
        return _cfg_cache
    cfg = json.loads(json.dumps(_DEFAULT))
    try:
        with open(_CONFIG, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        if isinstance(data, dict):
            cfg.update({k: v for k, v in data.items() if not k.startswith("_")})
    except Exception:
        pass
    _cfg_cache = cfg
    return cfg


def _rj(path: str, default):
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return default


def _wj(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _norm_source(src: str) -> str:
    s = str(src or "manual").strip().lower()
    aliases = {"chatgpt": "chatgpt", "openai": "chatgpt", "gpt": "chatgpt",
               "claude": "claude", "anthropic": "claude", "claude-mcp": "claude",
               "gemini": "gemini", "google": "gemini",
               "manual": "manual", "cli": "manual"}
    return aliases.get(s, s if s in config().get("sources", []) else "other")


def channel_for(intent: str, target_project: str = "",
                target_kind: str = "") -> str:
    """Map an intent (or explicit target kind) to a channel key."""
    ch = config()["channels"]
    t = str(target_kind or "").strip().lower()
    if t in ("backend", "productforge_backend", "product-forge"):
        return "productforge_backend"
    if t in ("dashboard", "productforge_dashboard", "product-forge-dashboard"):
        return "productforge_dashboard"
    if t in ("existing", "existing_project") and target_project:
        return "existing_project"
    i = str(intent or "").strip().lower()
    if i in ("new_project", "new_project_quick"):
        return "new_project"
    if i in ("modify_project", "add_context", "change"):
        return "existing_project" if target_project else "productforge_backend"
    if i == "product_forge_improvement":
        return "productforge_backend"
    if i in ("save_idea", "idea", "explore", "prototype"):
        return "idea"
    return "idea"


def channel_dir(products_dir: str, channel: str, target_project: str = "",
                create: bool = True) -> str:
    root = os.path.join(products_dir, str(config()["root"]).split("/", 1)[-1]) \
        if str(config()["root"]).startswith("products/") else os.path.join(
            REPO_ROOT, config()["root"])
    name = config()["channels"].get(channel, channel)
    d = os.path.join(root, name)
    if channel == "existing_project" and target_project:
        d = os.path.join(d, target_project)
    if create:
        os.makedirs(d, exist_ok=True)
    return d


def _next_id(products_dir: str) -> str:
    root = os.path.join(products_dir, "intake")
    mx = 0
    if os.path.isdir(root):
        for dp, _dn, fs in os.walk(root):
            for fn in fs:
                if fn == "index.json":
                    idx = _rj(os.path.join(dp, fn), {})
                    for k in (idx.get("items") or {}):
                        try:
                            mx = max(mx, int(str(k).split("-")[1]))
                        except Exception:
                            pass
    return f"IN-{mx + 1:04d}"


def add_item(products_dir: str, *, intent: str, source: str = "manual",
             title: str = "", body: str = "", target_project: str = "",
             target_kind: str = "", conversation_id: str = "",
             idea_ids: Optional[List[str]] = None,
             scope: str = "") -> Dict:
    """Record one intake entry in its channel and return it (with IN-id)."""
    channel = channel_for(intent, target_project, target_kind)
    iid = _next_id(products_dir)
    d = channel_dir(products_dir, channel, target_project)
    item = {
        "id": iid, "channel": channel, "source": _norm_source(source),
        "intent": intent, "title": title or "", "body": body or "",
        "target_project": target_project, "target_kind": target_kind,
        "scope": scope or "",                       # research|explore|prototype|build|entire
        "conversation_id": conversation_id,
        "idea_ids": idea_ids or [],
        "status": "received", "backlog_ref": "",
        "created_at": datetime.now().isoformat(), "updated_at": datetime.now().isoformat(),
        "links": {},
    }
    # append to items.jsonl
    with open(os.path.join(d, "items.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")
    # update index.json
    ip = os.path.join(d, "index.json")
    idx = _rj(ip, {"channel": channel, "items": {}})
    idx.setdefault("items", {})[iid] = {
        "source": item["source"], "intent": intent, "status": "received",
        "target_project": target_project, "backlog_ref": "", "scope": item["scope"],
        "created_at": item["created_at"],
    }
    idx["updated_at"] = item["updated_at"]
    _wj(ip, idx)
    return item


def update_item(products_dir: str, iid: str, **fields) -> Optional[Dict]:
    """Update an item's status/links across every channel index + jsonl."""
    root = os.path.join(products_dir, "intake")
    if not os.path.isdir(root):
        return None
    for dp, dn, fs in os.walk(root):
        ip = os.path.join(dp, "index.json")
        if not os.path.exists(ip):
            continue
        idx = _rj(ip, {})
        if iid not in (idx.get("items") or {}):
            continue
        rec = idx["items"][iid]
        rec.update({k: v for k, v in fields.items()})
        rec["updated_at"] = datetime.now().isoformat()
        _wj(ip, idx)
        return {"channel_dir": dp, **rec}
    return None


def item(products_dir: str, iid: str) -> Optional[Dict]:
    root = os.path.join(products_dir, "intake")
    if not os.path.isdir(root):
        return None
    for dp, dn, fs in os.walk(root):
        ip = os.path.join(dp, "index.json")
        if os.path.exists(ip):
            idx = _rj(ip, {})
            if iid in (idx.get("items") or {}):
                return {"channel_dir": dp, "channel": idx.get("channel", ""),
                        **idx["items"][iid]}
    return None


def list_items(products_dir: str, channel: str = "", status: str = "",
               source: str = "", scope: str = "", target_project: str = "",
               text: str = "") -> List[Dict]:
    """Filter/search intake items. ``source`` (chatgpt/claude/gemini/other/manual),
    channel, status, scope, target and a free-text match are all supported."""
    root = os.path.join(products_dir, "intake")
    out: List[Dict] = []
    if not os.path.isdir(root):
        return out
    t = str(text or "").strip().lower()
    for dp, dn, fs in os.walk(root):
        ip = os.path.join(dp, "index.json")
        if not os.path.exists(ip):
            continue
        idx = _rj(ip, {})
        ch = idx.get("channel", "")
        for iid, rec in (idx.get("items") or {}).items():
            if channel and ch != channel and rec.get("channel") != channel:
                continue
            if status and rec.get("status") != status:
                continue
            if source and _norm_source(rec.get("source")) != _norm_source(source):
                continue
            if scope and rec.get("scope") != scope:
                continue
            if target_project and rec.get("target_project") != target_project:
                continue
            merged = {"id": iid, "channel": ch, **rec}
            if t and t not in json.dumps(merged, ensure_ascii=False).lower():
                continue
            out.append(merged)
    return sorted(out, key=lambda x: x.get("id", ""))


def sources(products_dir: str) -> Dict[str, int]:
    """Counts per source platform (for the filter UI / analytics)."""
    out: Dict[str, int] = {}
    for it in list_items(products_dir):
        s = it.get("source") or "other"
        out[s] = out.get(s, 0) + 1
    return dict(sorted(out.items()))


def channels(products_dir: str) -> Dict[str, int]:
    """Counts per channel."""
    out: Dict[str, int] = {}
    for it in list_items(products_dir):
        c = it.get("channel") or "unknown"
        out[c] = out.get(c, 0) + 1
    return dict(sorted(out.items()))


def close_verified(products_dir: str, iid: str, backlog_ref: str = "",
                   report_links: Optional[Dict] = None) -> Optional[Dict]:
    """Close an intake item ONLY when its backlog item is verified/implemented."""
    return update_item(products_dir, iid, status="closed", backlog_ref=backlog_ref,
                       links=(report_links or {}))


def find_by_backlog(products_dir: str, backlog_ref: str) -> Optional[Dict]:
    """Find the intake item linked to a backlog id (BI-####)."""
    if not backlog_ref:
        return None
    for it in list_items(products_dir):
        if it.get("backlog_ref") == backlog_ref:
            return it
    return None


# ── Actions: analyze / execute now / schedule / promote (→ JobManager) ────────

def _backlog_target(it: Dict):
    """(scope, project) for the backlog item this intake entry creates."""
    ch = it.get("channel")
    tp = it.get("target_project") or ""
    if ch == "existing_project" and tp:
        return "project", tp
    if ch == "productforge_dashboard":
        return "project", "ProductForge-Dashboard"
    return "product_forge", None


def _run_project(it: Dict) -> str:
    ch = it.get("channel")
    tp = it.get("target_project") or ""
    if ch == "existing_project":
        return tp
    if ch == "productforge_dashboard":
        return "ProductForge-Dashboard"
    if ch == "new_project":
        return tp
    if ch == "productforge_backend":
        return "product-forge"
    return ""


def ensure_backlog(products_dir: str, iid: str) -> Optional[str]:
    """Create (once) the backlog item in the correct scope; return its id."""
    it = item(products_dir, iid)
    if not it:
        return None
    if it.get("backlog_ref"):
        return it["backlog_ref"]
    scope, proj = _backlog_target(it)
    from core import backlog
    item_type = "idea" if it.get("channel") == "idea" else "feature"
    b = backlog.add_epic(scope, proj, it.get("title") or iid, body=it.get("body") or "",
                         source=it.get("source") or "intake", type_=item_type,
                         origin="intake", external_id=f"intake:{iid}", moscow="Should",
                         links={"intake_id": iid, "conversation_id": it.get("conversation_id", "")})
    if b and b.get("id"):
        update_item(products_dir, iid, backlog_ref=b["id"])
        return b["id"]
    return None


def analyze(products_dir: str, iid: str, scope: str = "") -> Optional[Dict]:
    """Mark analyzed + set the pipeline scope (research|explore|prototype|build|entire)."""
    bid = ensure_backlog(products_dir, iid)
    return update_item(products_dir, iid, status="analyzed", backlog_ref=bid or "",
                       scope=scope or "entire")


def execute_now(products_dir: str, iid: str, by: str = "operator",
                priority: int = 10) -> Dict:
    """Enqueue the intake item on the JobManager queue for immediate execution."""
    it = item(products_dir, iid)
    if not it:
        return {"error": "intake item not found"}
    if it.get("channel") == "idea":
        return {"error": "idea is not executable — promote to new_project/explore/prototype first",
                "intake_id": iid}
    bid = ensure_backlog(products_dir, iid)
    proj = _run_project(it)
    if not proj:
        return {"error": "no run target — set target_project (or promote first)", "intake_id": iid}
    from core import run_entry
    entry = run_entry.enqueue(proj, priority=priority, item_id=bid or "",
                              source=f"intake:{it.get('source') or 'manual'}", actor=by,
                              products_dir=products_dir)
    update_item(products_dir, iid, status="queued", backlog_ref=bid or "",
                links={"run_id": entry.get("run_id"), "project": proj})
    return {"ok": True, "intake_id": iid, "backlog": bid, "project": proj,
            "queued": entry}


def schedule(products_dir: str, iid: str, at: str, by: str = "operator",
             priority: int = 100) -> Dict:
    """Schedule the intake item to run at ``at`` (ISO timestamp) via the queue."""
    it = item(products_dir, iid)
    if not it:
        return {"error": "intake item not found"}
    if it.get("channel") == "idea":
        return {"error": "idea is not executable — promote first", "intake_id": iid}
    bid = ensure_backlog(products_dir, iid)
    proj = _run_project(it)
    if not proj:
        return {"error": "no run target — set target_project", "intake_id": iid}
    from core import run_entry
    entry = run_entry.enqueue(proj, scheduled_at=at, priority=priority, item_id=bid or "",
                              source=f"intake:{it.get('source') or 'manual'}", actor=by,
                              products_dir=products_dir)
    update_item(products_dir, iid, status="scheduled", backlog_ref=bid or "",
                links={"run_id": entry.get("run_id"), "project": proj, "scheduled_at": at})
    return {"ok": True, "intake_id": iid, "backlog": bid, "project": proj,
            "scheduled_at": at, "queued": entry}


def promote(products_dir: str, iid: str, to: str = "new_project", name: str = "",
            by: str = "operator", execute: bool = False) -> Dict:
    """Promote an idea into a pipeline target.

    ``to`` = new_project | explore | prototype | existing_project.
    new_project creates/registers the project; explore/prototype set the pipeline scope.
    """
    it = item(products_dir, iid)
    if not it:
        return {"error": "intake item not found"}
    to = str(to or "new_project").lower()
    scope = "entire"
    project = it.get("target_project") or ""
    if to == "new_project" or to == "prototype":
        project = name or project or "".join(
            ch if ch.isalnum() else "-" for ch in (it.get("title") or iid))[:40].strip("-")
        scope = "prototype" if to == "prototype" else "entire"
        try:
            from core import portfolio
            portfolio.register(project)
        except Exception:
            pass
    elif to == "explore":
        scope = "explore"
    from core import backlog
    scope_bk, proj_bk = ("project", project) if project else _backlog_target(it)
    bid = it.get("backlog_ref") or ensure_backlog(products_dir, iid)
    if bid:
        try:
            backlog.update(scope_bk, proj_bk, bid, type_="project",
                           scope=scope, _note=f"promoted to {to}")
        except Exception:
            pass
    update_item(products_dir, iid, status="analyzed", target_project=project, scope=scope,
                backlog_ref=bid or "")
    res = {"ok": True, "intake_id": iid, "promoted_to": to, "project": project,
           "scope": scope, "backlog": bid}
    if execute and project:
        res["execution"] = execute_now(products_dir, iid, by=by) if to != "explore" else None
    return res
