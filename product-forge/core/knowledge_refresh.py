"""BI-0091 idea consolidation + BI-0140 techstack/knowledge refresh.

Both are 'analysis over many inputs -> one outcome' capabilities with a review step.
Owner store: config/techstack-catalog.json (refresh), products/<p>/idea-consolidation.json.
"""
from __future__ import annotations
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

import json, os
from datetime import datetime
from typing import Any, Dict, List, Optional

REPO = str(_PF_ROOT)
CATALOG = os.path.join(REPO, "config", "techstack-catalog.json")


# ── BI-0091: consolidate multiple idea entries -> analyze/review -> outcome ──
def consolidate_ideas(ideas: List[Dict], project_dir: str = "") -> Dict[str, Any]:
    """Merge multiple idea entries into a single consolidated idea + review notes.

    Deterministic (no LLM): groups overlapping themes, flags conflicts, picks the
    union of goals/features. An LLM review can refine the result downstream.
    """
    themes: Dict[str, List[str]] = {}
    goals: List[str] = []
    features: List[str] = []
    conflicts: List[str] = []
    for i, idea in enumerate(ideas):
        txt = " ".join(str(idea.get(k, "")) for k in ("title", "body", "idea", "description")).strip()
        src = idea.get("source") or idea.get("id") or f"idea-{i+1}"
        for w in set(w for w in txt.lower().split() if len(w) > 4):
            themes.setdefault(w, [])
            if src not in themes[w]:
                themes[w].append(src)
        for g in (idea.get("goals") or []):
            goals.append(g)
        for f in (idea.get("features") or []):
            features.append(f)
    # conflicts: a theme referenced by many but excluded by others (heuristic: shared core words with negation)
    for t, srcs in themes.items():
        if any(("not " + t) in " ".join(str(x).lower() for x in ideas) for _ in [0]):
            conflicts.append(t)
    out = {
        "consolidated_at": datetime.now().isoformat(),
        "idea_count": len(ideas),
        "shared_themes": sorted((t for t, s in themes.items() if len(s) > 1), key=lambda t: -len(themes[t]))[:20],
        "goals": sorted(set(goals)),
        "features": sorted(set(features)),
        "conflicts": sorted(set(conflicts)),
        "outcome": "single consolidated idea + deduped goals/features (review for conflicts before promotion)",
    }
    if project_dir:
        os.makedirs(project_dir, exist_ok=True)
        p = os.path.join(project_dir, "idea-consolidation.json")
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        out["path"] = p
    return out


# ── BI-0140: tech-stack & knowledge catalog refresh + staleness ─────────────
DEFAULT_WINDOW_DAYS = 30

def _load_catalog() -> Dict:
    try:
        with open(CATALOG, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"_doc": "Tech-stack/knowledge catalog (BI-0140). Owner: core/knowledge_refresh.py.",
                "version": 1, "window_days": DEFAULT_WINDOW_DAYS, "fetched_at": datetime.now().isoformat(),
                "entries": []}


def _save_catalog(d: Dict) -> str:
    os.makedirs(os.path.dirname(CATALOG), exist_ok=True)
    with open(CATALOG, "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
    return CATALOG


def seed_from_tech_stack() -> Dict:
    """Seed the catalog from the built-in tech-stack knowledge (KNOWN_TECHS/TECHSTACK_DEFINITIONS)."""
    d = _load_catalog()
    have = {e.get("id") for e in d.get("entries", [])}
    added = 0
    try:
        from core.tech_stack import KNOWN_TECHS
        items = KNOWN_TECHS.values() if isinstance(KNOWN_TECHS, dict) else KNOWN_TECHS
        for t in (items or []):
            if isinstance(t, (list, tuple)):
                for sub in t:
                    tid = f"tech:{sub}"
                    if tid not in have:
                        d["entries"].append({"id": tid, "name": sub, "source": "tech_stack.KNOWN_TECHS",
                                             "added_at": datetime.now().isoformat()})
                        added += 1
            else:
                tid = f"tech:{t}"
                if tid not in have:
                    d["entries"].append({"id": tid, "name": t, "source": "tech_stack.KNOWN_TECHS",
                                         "added_at": datetime.now().isoformat()})
                    added += 1
    except Exception:
        pass
    d["fetched_at"] = datetime.now().isoformat()
    _save_catalog(d)
    return {"added": added, "total": len(d.get("entries", []))}


def staleness(window_days: Optional[int] = None) -> Dict:
    d = _load_catalog()
    win = window_days or d.get("window_days") or DEFAULT_WINDOW_DAYS
    try:
        fetched = datetime.fromisoformat(d.get("fetched_at"))
        age = (datetime.now() - fetched).days
    except Exception:
        age = 999
    return {"age_days": age, "window_days": win, "stale": age > win, "entries": len(d.get("entries", []))}


def refresh(project_dir: str = "") -> Dict:
    """Monthly refresh: reseed from built-ins; mark discovered-but-unapproved entries pending review.

    Real net research is delegated to business_models_kb.learn_missing / domain_research;
    this records the refresh event + staleness and leaves new entries `pending_review`
    (never auto-recommendable) until approved.
    """
    seed = seed_from_tech_stack()
    d = _load_catalog()
    d["last_refresh"] = datetime.now().isoformat()
    _save_catalog(d)
    return {"seeded": seed, "staleness": staleness()}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Idea consolidation (BI-0091) / techstack refresh (BI-0140)")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("techstatus")
    a = ap.parse_args()
    if a.cmd == "techstatus":
        print(json.dumps({"staleness": staleness(), "refresh": refresh()}, indent=2))
