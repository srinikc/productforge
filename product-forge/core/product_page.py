"""Product one-stop page read model (BI-0216).

Composes a SINGLE payload for the per-product page (dashboard BI-0147/0148/0149)
by DERIVING from existing stores -- it adds no new source of truth and works the
same for a plain text product and a multi-modal one (media/sensor/BOM sections are
simply empty when those stores/packs do not exist).

Sections: identity+lifecycle, progress, features, artifacts, quality, cost, bom,
releases, activity. Every source is guarded; a missing store yields an empty section,
never an error.

Owner: this module (pure read). Wired in dashboard/api/app.py.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.paths import products as _products

LIFECYCLE = ("ideation", "designing", "building", "verifying", "built",
             "launching", "live", "maintaining", "on-hold", "archived")

# artifact stage ids that imply a lifecycle milestone (prefix match)
_BUILD_PREFIXES = ("4",)
_DESIGN_PREFIXES = ("0", "1", "2", "3")
_LAUNCH_STAGES = {"10", "10a", "11", "12"}


def _pdir(project: str) -> Path:
    return _products(project)


def _rj(p: Path, default):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


# ── identity + lifecycle ─────────────────────────────────────────────────────
def lifecycle(project: str) -> str:
    """Derived lifecycle state (explicit `product.json` wins).

    Heuristic order: archived > deployed/live > launching > built (quality gate) >
    building (any 4-* artifact) > designing (any 0-3 artifact or pipeline-state) >
    ideation. Overridable by `product.json: {"lifecycle": "..."}`.
    """
    pdir = _pdir(project)
    reg = _rj(pdir / "product.json", {}) or {}
    explicit = str(reg.get("lifecycle") or "").strip()
    if explicit in LIFECYCLE:
        return explicit
    state = _rj(pdir / "pipeline-state.json", {}) or {}
    if state.get("archived"):
        return "archived"
    if state.get("deployed"):
        return "live"
    try:
        from core import stage_paths as sp
        stages = {sid for sid, _p in sp.iter_stages(str(pdir))}
    except Exception:
        stages = set()
    if stages & _LAUNCH_STAGES:
        return "launching"
    q = _rj(pdir / "quality-gate.json", {}) or {}
    if q.get("passed"):
        return "built"
    if any(s.split("-")[0].startswith(_BUILD_PREFIXES) for s in stages):
        return "building"
    if stages or state.get("stages"):
        return "designing"
    return "ideation"


def identity(project: str) -> Dict[str, Any]:
    pdir = _pdir(project)
    reg = _rj(pdir / "product.json", {}) or {}
    return {
        "project": project,
        "name": reg.get("name") or project,
        "owner": reg.get("owner") or "",
        "created_at": reg.get("created_at") or "",
        "lifecycle": lifecycle(project),
        "links": reg.get("links") or {},
        "versions": reg.get("versions") or [],
        "exists": pdir.exists(),
    }


# ── sections ─────────────────────────────────────────────────────────────────
def progress(project: str) -> Dict[str, Any]:
    try:
        from core import progress as _prog
        return _prog.snapshot(str(_pdir(project)))
    except Exception as e:
        return {"error": str(e)}


def features(project: str) -> Dict[str, Any]:
    try:
        from core import backlog as _b
        items = _b.list_items("project", project)
    except Exception:
        items = []
    out = []
    for it in items or []:
        out.append({"id": it.get("id"), "title": it.get("title"),
                    "type": it.get("type"), "status": it.get("status"),
                    "section": it.get("section"), "priority": it.get("priority"),
                    "updated_at": it.get("updated_at")})
    return {"count": len(out), "items": out}


def artifacts(project: str) -> Dict[str, Any]:
    pdir = _pdir(project)
    stages: List[Dict[str, Any]] = []
    try:
        from core import stage_paths as sp
        for sid, path in sp.iter_stages(str(pdir)):
            try:
                files = sorted(f for f in os.listdir(path)
                               if os.path.isfile(os.path.join(path, f)))
            except Exception:
                files = []
            stages.append({"stage": sid, "dir": os.path.basename(path), "files": files})
    except Exception:
        pass
    return {"count": len(stages), "stages": stages}


def quality(project: str) -> Dict[str, Any]:
    pdir = _pdir(project)
    try:
        from core import run_quality_gate as qg
        latest = qg.latest(str(pdir))
    except Exception:
        latest = None
    return latest or {"passed": None, "checks": [], "reasons": [], "at": ""}


def cost(project: str) -> Dict[str, Any]:
    b = _rj(_pdir(project) / "budget.json", {}) or {}
    st = b.get("state") or {}
    return {"total_used": st.get("total_used"), "total_max": st.get("total_max"),
            "currency": st.get("currency") or "USD"}


def bom(project: str) -> Dict[str, Any]:
    """BOM/footprint (BI-0217). Empty until packaging emits it."""
    pdir = _pdir(project)
    for cand in (pdir / "artifacts" / "9 - Package" / "BOM.json",
                 pdir / "artifacts" / "9" / "BOM.json",
                 pdir / "BOM.json"):
        data = _rj(cand, None)
        if data:
            return {"available": True, "bom": data}
    return {"available": False, "bom": None}


def releases(project: str) -> Dict[str, Any]:
    reg = _rj(_pdir(project) / "product.json", {}) or {}
    rel = reg.get("releases") or reg.get("versions") or []
    return {"count": len(rel), "releases": rel}


def activity(project: str, limit: int = 50) -> Dict[str, Any]:
    try:
        from core import events as _ev
        rows = _ev.read(str(_pdir(project)), limit=limit)
    except Exception:
        rows = []
    return {"count": len(rows), "events": rows}


# ── aggregate (the one-stop payload) ─────────────────────────────────────────
def page(project: str, activity_limit: int = 50) -> Dict[str, Any]:
    """The single read-model payload for the product page (works for any product type)."""
    ident = identity(project)
    return {
        "identity": ident,
        "lifecycle": ident["lifecycle"],
        "progress": progress(project),
        "features": features(project),
        "artifacts": artifacts(project),
        "quality": quality(project),
        "cost": cost(project),
        "bom": bom(project),
        "releases": releases(project),
        "activity": activity(project, activity_limit),
    }


def _main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Product one-stop page read model (BI-0216)")
    ap.add_argument("--project", required=True)
    ap.add_argument("--section", default="", help="identity|progress|features|artifacts|quality|cost|bom|releases|activity")
    a = ap.parse_args(argv)
    data = globals()[a.section](a.project) if a.section in (
        "identity", "progress", "features", "artifacts", "quality", "cost",
        "bom", "releases", "activity") else page(a.project)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
