"""Unified Knowledge / Skills Registry — add · modify · view knowledge bases, skills,
techstacks, domains, guidelines, and MCP servers in ONE catalog.

This is the extensibility back door: new knowledge/skill/techstack/domain entries are
registered here (kind + name + layers/uri/path + provenance) and are then picked up by the
knowledge loader / router for agents — no code change. Owner: this module (single writer).

Store: config/knowledge-registry.json
CLI:   python -m core.knowledge_registry list|view|add|modify|remove ...
API:   GET  /api/knowledge           (list; ?kind=&agent=)
       GET  /api/knowledge/{id}      (view)
       POST /api/knowledge           ({"action":"add|modify|remove", ...})
"""
import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(REPO, "config", "knowledge-registry.json")
KINDS = ("knowledge", "skill", "techstack", "domain", "guideline", "mcp")


def _load() -> Dict:
    try:
        d = json.load(open(STORE, encoding="utf-8-sig"))
        if isinstance(d, dict) and isinstance(d.get("entries"), dict):
            return d
    except Exception:
        pass
    return {"entries": {}, "updated_at": ""}


def _save(d: Dict) -> None:
    d["updated_at"] = datetime.now().isoformat(timespec="seconds")
    os.makedirs(os.path.dirname(STORE), exist_ok=True)
    with open(STORE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(s or "").lower()).strip("-") or "item"


def list_entries(kind: str = "", agent: str = "") -> List[Dict]:
    out = []
    for eid, e in (_load().get("entries") or {}).items():
        if kind and e.get("kind") != kind:
            continue
        if agent and agent not in (e.get("agents") or []) and "*" not in (e.get("agents") or []):
            continue
        out.append({"id": eid, **e})
    return sorted(out, key=lambda x: (x.get("kind", ""), x.get("name", "")))


def view(eid: str) -> Optional[Dict]:
    e = (_load().get("entries") or {}).get(eid)
    return {"id": eid, **e} if e else None


def add(kind: str, name: str, *, layers: Optional[List[str]] = None, path: str = "",
        uri: str = "", source: str = "manual", license: str = "", notes: str = "",
        agents: Optional[List[str]] = None, added_by: str = "operator") -> Dict:
    """Register a new knowledge/skill/techstack/domain entry."""
    kind = str(kind).strip().lower()
    if kind not in KINDS:
        return {"error": f"kind must be one of {KINDS}"}
    d = _load()
    eid = f"{kind}-{_slug(name)}"
    d.setdefault("entries", {})[eid] = {
        "kind": kind, "name": name, "layers": layers or [name], "path": path, "uri": uri,
        "source": source, "license": license, "notes": notes,
        "agents": agents or ["*"], "status": "active",
        "added_at": datetime.now().isoformat(timespec="seconds"), "added_by": added_by,
    }
    _save(d)
    return {"id": eid, **d["entries"][eid]}


def modify(eid: str, **fields) -> Dict:
    d = _load()
    e = (d.get("entries") or {}).get(eid)
    if not e:
        return {"error": f"not found: {eid}"}
    for k, v in fields.items():
        if k in ("kind", "name", "layers", "path", "uri", "source", "license", "notes",
                 "agents", "status"):
            e[k] = v
    e["modified_at"] = datetime.now().isoformat(timespec="seconds")
    _save(d)
    return {"id": eid, **e}


def remove(eid: str) -> Dict:
    d = _load()
    if eid in (d.get("entries") or {}):
        d["entries"].pop(eid)
        _save(d)
        return {"removed": eid}
    return {"error": f"not found: {eid}"}


def for_agent(agent_id: str) -> List[Dict]:
    """Active entries that apply to this agent (agents lists it or '*')."""
    return [e for e in list_entries(agent=agent_id) if e.get("status") == "active"]


def resolve_layers(agent_id: str) -> List[str]:
    """Extra knowledge layers to inject for an agent, from registry entries."""
    out = []
    for e in for_agent(agent_id):
        for l in (e.get("layers") or []):
            if l not in out:
                out.append(l)
    return out


def _main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Knowledge/skills registry (add/modify/view)")
    sub = ap.add_subparsers(dest="cmd")
    l = sub.add_parser("list")
    l.add_argument("--kind", default="")
    l.add_argument("--agent", default="")
    v = sub.add_parser("view")
    v.add_argument("id")
    a = sub.add_parser("add")
    a.add_argument("kind")
    a.add_argument("name")
    a.add_argument("--layers", default="")
    a.add_argument("--uri", default="")
    a.add_argument("--path", default="")
    a.add_argument("--source", default="manual")
    a.add_argument("--license", default="")
    a.add_argument("--agents", default="*")
    m = sub.add_parser("modify")
    m.add_argument("id")
    m.add_argument("--set", default="", help="key=value,key=value")
    r = sub.add_parser("remove")
    r.add_argument("id")
    x = ap.parse_args(argv)
    c = x.cmd or "list"
    if c == "list":
        print(json.dumps(list_entries(getattr(x, "kind", ""), getattr(x, "agent", "")),
                         indent=2, ensure_ascii=False))
    elif c == "view":
        print(json.dumps(view(x.id), indent=2, ensure_ascii=False))
    elif c == "add":
        print(json.dumps(add(x.kind, x.name, layers=[s for s in x.layers.split(",") if s],
                             uri=x.uri, path=x.path, source=x.source, license=x.license,
                             agents=[s for s in x.agents.split(",") if s]),
                         indent=2, ensure_ascii=False))
    elif c == "modify":
        fields = {}
        for kv in x.set.split(","):
            if "=" in kv:
                k, val = kv.split("=", 1)
                fields[k.strip()] = val.strip()
        print(json.dumps(modify(x.id, **fields), indent=2, ensure_ascii=False))
    elif c == "remove":
        print(json.dumps(remove(x.id), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
