"""Business-models knowledge pack (BI-0119) + dynamic knowledge acquisition (BI-0118).

Refer-then-learn: the business agents consult a curated pack; if a needed model/skill
is absent, `learn_missing()` researches the net and registers what it learned.
Owner store: config/business-models-kb.json (pack) + products/<project>/.learned-knowledge.json (learned).
"""
from __future__ import annotations
import json, os
from datetime import datetime
from typing import Any, Dict, List, Optional

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB = os.path.join(REPO, "config", "business-models-kb.json")

# Curated baseline pack (seed). Extendable; each entry carries source + version.
SEED = {
    "revenue_models": [
        {"id": "saas-subscription", "name": "SaaS Subscription", "desc": "Recurring fee per seat/usage tier.", "source": "business-models-kb/seed"},
        {"id": "freemium", "name": "Freemium", "desc": "Free tier + paid upgrades.", "source": "business-models-kb/seed"},
        {"id": "usage-based", "name": "Usage-based", "desc": "Pay per unit of consumption.", "source": "business-models-kb/seed"},
        {"id": "marketplace", "name": "Marketplace", "desc": "Take-rate on transactions between two sides.", "source": "business-models-kb/seed"},
        {"id": "licensing", "name": "Licensing", "desc": "License IP/software for a fee.", "source": "business-models-kb/seed"},
        {"id": "advertising", "name": "Advertising", "desc": "Monetize attention via ads.", "source": "business-models-kb/seed"},
    ],
    "unit_economics": [
        {"id": "cac", "name": "CAC", "formula": "total S&M spend / new customers", "source": "seed"},
        {"id": "ltv", "name": "LTV", "formula": "ARPU * gross margin % / churn rate", "source": "seed"},
        {"id": "payback", "name": "CAC Payback (months)", "formula": "CAC / (ARPU * gross margin)", "source": "seed"},
        {"id": "ltv_cac", "name": "LTV:CAC", "formula": "LTV / CAC (target >= 3)", "source": "seed"},
        {"id": "gross_margin", "name": "Gross Margin", "formula": "(revenue - COGS) / revenue", "source": "seed"},
    ],
    "pricing_tactics": [
        {"id": "tiered", "name": "Tiered Packaging"}, {"id": "value-based", "name": "Value-based Pricing"},
        {"id": "good-better-best", "name": "Good/Better/Best"}, {"id": "usage-meters", "name": "Usage Meters"},
    ],
    "gtm_playbooks": [
        {"id": "plg", "name": "Product-led Growth"}, {"id": "sales-led", "name": "Sales-led"},
        {"id": "community-led", "name": "Community-led"}, {"id": "partner-led", "name": "Partner-led"},
    ],
    "growth_loops": [
        {"id": "viral", "name": "Viral Loop"}, {"id": "content", "name": "Content Loop"},
        {"id": "paid", "name": "Paid Loop"}, {"id": "sales", "name": "Sales Loop"},
    ],
    "market_sizing": [
        {"id": "tam", "name": "TAM"}, {"id": "sam", "name": "SAM"}, {"id": "som", "name": "SOM"},
        {"id": "top-down", "name": "Top-down"}, {"id": "bottom-up", "name": "Bottom-up"},
    ],
    "competition_frameworks": [
        {"id": "porter5", "name": "Porter's Five Forces"}, {"id": "swot", "name": "SWOT"},
        {"id": "positioning", "name": "Positioning Map"}, {"id": "jobs", "name": "Jobs-to-be-Done"},
    ],
}


def _load_kb() -> Dict:
    if os.path.exists(KB):
        try:
            with open(KB, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    d = {"_doc": "Curated business-models knowledge pack (BI-0119). Owner: core/business_models_kb.py. "
                 "Seed + learned entries; each carries source + added_at.", "version": 1,
         "fetched_at": datetime.now().isoformat(), "source": "seed",
         **{k: v for k, v in SEED.items()}}
    _save_kb(d)
    return d


def _save_kb(d: Dict) -> None:
    os.makedirs(os.path.dirname(KB), exist_ok=True)
    with open(KB, "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)


def sections() -> List[str]:
    return [k for k in _load_kb().keys() if not k.startswith("_") and k not in ("version", "fetched_at", "source")]


def lookup(section: str, query: str = "") -> List[Dict]:
    """Refer: entries in a section, optionally filtered by a query substring."""
    items = _load_kb().get(section, []) or []
    q = (query or "").lower()
    return [i for i in items if not q or q in json.dumps(i).lower()]


def has(section: str, entry_id: str) -> bool:
    return any(i.get("id") == entry_id for i in (_load_kb().get(section, []) or []))


def learn(section: str, entry: Dict, source: str = "") -> Dict:
    """Add a learned entry to the pack (idempotent by id)."""
    d = _load_kb()
    d.setdefault(section, [])
    if not any(i.get("id") == entry.get("id") for i in d[section]):
        entry = dict(entry)
        entry.setdefault("source", source or "learned")
        entry.setdefault("added_at", datetime.now().isoformat())
        entry.setdefault("learned", True)
        d[section].append(entry)
        _save_kb(d)
    return {"section": section, "id": entry.get("id"), "learned": True}


def _research_web(need: str, limit: int = 5) -> List[Dict]:
    """Best-effort net research for a missing model/skill. Returns [{title,url,snippet}].

    Uses core/domain_research (trends/report) when the topic maps to a domain, and a
    plain WebFetch of a search endpoint otherwise. Never fabricates: returns [] if
    nothing real is retrieved.
    """
    out: List[Dict] = []
    # 1) domain_research trends (real, offline corpus)
    try:
        from core.domain_research import DomainResearchEngine
        eng = DomainResearchEngine()
        trends = eng.search_trends(need) if hasattr(eng, "search_trends") else []
        for t in (trends or [])[:limit]:
            out.append({"title": getattr(t, "name", str(t)), "url": getattr(t, "source", ""),
                        "snippet": getattr(t, "description", "") or "", "via": "domain_research"})
    except Exception:
        pass
    # 2) net fetch (real HTTP only)
    if not out:
        try:
            import urllib.parse as _up
            import urllib.request as _ur
            q = _up.quote(need)
            req = _ur.Request(f"https://duckduckgo.com/html/?q={q}",
                              headers={"User-Agent": "product-forge-knowledge/1.0"})
            html = _ur.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
            import re as _re
            for m in list(_re.finditer(r'result__a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, _re.S))[:limit]:
                out.append({"title": _re.sub(r"<[^>]+>", "", m.group(2)).strip(),
                            "url": m.group(1), "snippet": "", "via": "web"})
        except Exception:
            pass
    return out


def learn_missing(project_dir: str, need: str) -> Dict:
    """Dynamic acquisition (BI-0118): research the net for a missing model/skill.

    Records what was actually retrieved (real sources only) to the pack and to the
    project's learned-knowledge store. If research is unavailable it records a
    `needs_research` marker instead of inventing content.
    """
    result = {"need": need, "learned": [], "status": "ok"}
    found = _research_web(need)
    if found:
        for f in found:
            learn("learned", {"id": f.get("title") or need, "name": f.get("title"),
                              "url": f.get("url"), "snippet": f.get("snippet")},
                  source=f.get("via", "web"))
            result["learned"].append(f.get("title") or f.get("url"))
    else:
        result["status"] = "needs_research"
        result["reason"] = "no source retrieved (offline or no results)"
    # record to project learned-knowledge store
    lp = os.path.join(project_dir, ".learned-knowledge.json")
    try:
        store = json.load(open(lp, encoding="utf-8")) if os.path.exists(lp) else {"entries": []}
    except Exception:
        store = {"entries": []}
    store.setdefault("entries", []).append({"need": need, "status": result["status"],
                                            "learned": result["learned"], "at": datetime.now().isoformat()})
    os.makedirs(project_dir, exist_ok=True)
    with open(lp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(store, f, indent=2, ensure_ascii=False)
    return result


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Business-models KB (BI-0119)")
    ap.add_argument("--sections", action="store_true")
    ap.add_argument("--lookup", nargs=2, metavar=("SECTION", "QUERY"))
    a = ap.parse_args()
    if a.lookup:
        print(json.dumps(lookup(a.lookup[0], a.lookup[1]), indent=2))
    else:
        print(json.dumps(sections(), indent=2))
