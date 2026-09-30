"""Learnings registry — de-duplicated, compact rules distilled from issues/RCCA.

Purpose: turn generalized RCCA into a SMALL, deduplicated set of rules that can be fed
into prompts/guidelines WITHOUT bloating them (agents are not overwhelmed and token
use stays bounded). We never just append: a new learning that is similar to an existing
one MERGES into it (bump count, add source_ref), and the store is capped.

Store: data/learnings.json (single writer). One global list of:
  {id, area, rule, sources[], count, at}
Rule text is capped; the whole store is capped (LEARN_MAX); render() caps output too.

Id scheme: LN-<nnn>.
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
from datetime import datetime
from typing import Dict, List, Optional

_FILE = os.path.join(str(_PF_ROOT), "data", "learnings.json")


def _file(project: str = "") -> str:
    """Resolve the learnings store: project-scoped when a project is given, else global.

    Project learnings live at products/<project>/learnings.json (single writer: this module).
    """
    p = str(project or "").strip()
    if p:
        return os.path.join(str(_PF_ROOT), "products", p, "learnings.json")
    return _FILE

RULE_MAX = 240          # max chars per rule
STORE_MAX = 120         # max learnings kept
MERGE_AT = 0.6          # similarity at/above which a new rule merges into an existing one
_STOP = {"the", "a", "an", "of", "to", "for", "and", "or", "in", "on", "with", "is", "be",
         "as", "by", "at", "from", "not", "no", "any", "all", "we", "it", "that", "this"}
_TOK = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set:
    return {t for t in _TOK.findall(str(text or "").lower()) if len(t) > 2 and t not in _STOP}


def _sim(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return (inter / min(len(a), len(b))) if inter else 0.0


def _load(project: str = "") -> List[Dict]:
    try:
        with open(_file(project), "r", encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, list) else []
    except Exception:
        return []


def _save(items: List[Dict], project: str = "") -> None:
    path = _file(project)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def _next_id(items: List[Dict]) -> str:
    mx = 0
    for e in items:
        try:
            mx = max(mx, int(re.sub(r"\D", "", str(e.get("id", ""))) or 0))
        except Exception:
            pass
    return f"LN-{mx + 1:04d}"


def add(rule: str, area: str = "", source_ref: str = "", project: str = "") -> Dict:
    """Add a learning, DE-DUPLICATING: a similar existing rule merges instead of appending.

    ``project`` scopes the write to products/<project>/learnings.json; empty = global store.
    """
    rule = " ".join(str(rule or "").split())[:RULE_MAX]
    if not rule:
        return {}
    items = _load(project)
    toks = _tokens(rule)
    for e in items:
        if _sim(toks, _tokens(e.get("rule", ""))) >= MERGE_AT:
            e["count"] = int(e.get("count", 1)) + 1
            e["at"] = datetime.now().isoformat(timespec="seconds")
            if area and not e.get("area"):
                e["area"] = area
            if source_ref and source_ref not in (e.get("sources") or []):
                e.setdefault("sources", []).append(source_ref)
                e["sources"] = e["sources"][-20:]
            _save(items, project)
            return e
    rec = {"id": _next_id(items), "area": area, "rule": rule,
           "sources": [source_ref] if source_ref else [], "count": 1,
           "at": datetime.now().isoformat(timespec="seconds")}
    items.append(rec)
    # Cap the store: keep the most reinforced / most recent rules.
    if len(items) > STORE_MAX:
        items = sorted(items, key=lambda e: (int(e.get("count", 1)), str(e.get("at", ""))),
                       reverse=True)[:STORE_MAX]
    _save(items, project)
    return rec


def all_learnings(project: str = "") -> List[Dict]:
    """Learnings for a project: UNION of global + project store (project wins on id, keeps both).

    With no project, returns the global list (unchanged legacy behavior).
    """
    if not project:
        return sorted(_load(), key=lambda e: int(e.get("count", 1)), reverse=True)
    glob = _load()
    proj = _load(project)
    seen_rules = set()
    merged: List[Dict] = []
    for e in proj:                       # project entries first (need-based)
        seen_rules.add(_sim_key(e))
        merged.append(e)
    for e in glob:
        # dedup by RULE (ids are per-store and can collide across stores)
        if _sim_key(e) not in seen_rules:
            merged.append(e)
    return sorted(merged, key=lambda e: int(e.get("count", 1)), reverse=True)


def _sim_key(e: Dict) -> str:
    return " ".join(str(e.get("rule", "")).lower().split())


def render(area: str = "", project: str = "", agent: str = "",
           max_learnings: int = 15, max_chars: int = 1600) -> str:
    """A COMPACT bullet block for prompt/guideline injection (bounded size), selected on need.

    ``project`` unions global + project learnings; ``area`` filters by module/area.
    """
    out, total = [], 0
    for e in all_learnings(project):
        if area and e.get("area") and e.get("area") != area:
            continue
        line = f"- {e.get('rule')}"
        if total + len(line) + 1 > max_chars:
            break
        out.append(line)
        total += len(line) + 1
        if len(out) >= max_learnings:
            break
    if not out:
        return ""
    return "\n\nLEARNINGS (de-duplicated, from prior issues - apply these):\n" + "\n".join(out)


def _cli(argv=None) -> int:
    import argparse
    try:
        import sys as _s
        _s.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    p = argparse.ArgumentParser(prog="python -m core.learnings", description="De-duplicated learnings registry")
    p.add_argument("--list", action="store_true")
    p.add_argument("--render", action="store_true")
    a = p.parse_args(argv)
    if a.render:
        print(render())
        return 0
    for e in all_learnings():
        print(f"{e['id']}  x{e.get('count')}  [{e.get('area') or '-'}]  {e.get('rule')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
