"""Requirement linking (BI-0016 / U8).

Links the three requirement-ish stores by id (no third copy):
  staging   : .conversations/requirements.json            (REQ-* from intake)
  plan      : product-plan.json  (requirements_index + feature.requirements[])
  trace     : traceability.json  (matrix rows REQ-* <-> F-*)

`synchronize(project)` is idempotent and non-destructive: it ensures every feature's
requirements appear in the index and the traceability matrix, and flags orphan staging
requirements (not linked to any feature).
"""
import json
import os
from typing import Any, Dict, List

_DEFAULT_PRODUCTS = "products"


def _rj(p: str, d: Any) -> Any:
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def _wj(p: str, data: Any) -> None:
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    os.replace(tmp, p)


def synchronize(project: str, products_dir: str = _DEFAULT_PRODUCTS) -> Dict:
    """Ensure plan.requirements_index and traceability.matrix reference REQ-* <-> F-*."""
    pdir = os.path.join(products_dir, project)
    plan_path = os.path.join(pdir, "product-plan.json")
    trace_path = os.path.join(pdir, "traceability.json")
    plan = _rj(plan_path, None)
    if not isinstance(plan, dict):
        return {"ok": False, "reason": "no product-plan"}
    index = plan.setdefault("requirements_index", {})
    changed = 0

    # 1) feature.requirements[] -> requirements_index
    for mod in (plan.get("modules") or []):
        for feat in (mod.get("features") or []):
            fid = feat.get("id", "")
            for req_id in (feat.get("requirements") or []):
                row = index.setdefault(req_id, {"title": feat.get("name", ""), "status": "planned",
                                                "features": [], "architecture_decisions": [],
                                                "test_coverage": 0.0, "security_issues": 0})
                if fid and fid not in row.setdefault("features", []):
                    row["features"].append(fid)
                    changed += 1
    if changed:
        _wj(plan_path, plan)

    # 2) traceability matrix rows REQ-* <-> F-* (BI-PF-1173: delegate the write to the single owner)
    rows = []
    for req_id, row in index.items():
        for fid in (row.get("features") or []):
            rows.append({"requirement_id": req_id, "feature_id": fid})
    try:
        from core import traceability as _trace
        res = _trace.merge_matrix(pdir, rows)
        added = res.get("merged", 0)
    except Exception:
        added = 0

    return {"ok": True, "index_links_added": changed, "matrix_rows_added": added,
            "requirements": len(index)}


def orphans(products_dir: str = _DEFAULT_PRODUCTS) -> List[Dict]:
    """Staging requirements (from intake) not linked to any feature in any plan."""
    linked = set()
    try:
        for name in os.listdir(products_dir):
            plan = _rj(os.path.join(products_dir, name, "product-plan.json"), None)
            if isinstance(plan, dict):
                for req_id, row in (plan.get("requirements_index") or {}).items():
                    if row.get("features"):
                        linked.add(req_id)
    except Exception:
        pass
    out = []
    staging = _rj(os.path.join(products_dir, ".conversations", "requirements.json"), {})
    if isinstance(staging, dict):
        for req_id in staging.keys():
            if req_id not in linked:
                out.append({"requirement_id": req_id, "linked_to": sorted(linked)[:0]})
    return out
