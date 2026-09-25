"""Single insights store (Step 7 / U3) + Product Forge promotion (B8).

One canonical store: `products/insights.json` (cross-project; each entry carries `project`).
Producers (qa_intelligence per-project insights, cross_project_learning) import into it;
per-project generated files stay as *derived* evidence.

Also promotes actionable insights into the Product Forge backlog (origin=pipeline).
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
from typing import Any, Dict, List, Optional

_REPO = str(_PF_ROOT)
_DEFAULT = os.path.join(_REPO, "products", "insights.json")
_IMPACT_RANK = {"high": 3, "medium": 2, "low": 1}


def _path() -> str:
    return os.environ.get("PF_INSIGHTS_FILE", _DEFAULT)


def _read() -> List[Dict]:
    try:
        with open(_path(), "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, list) else d.get("insights", [])
    except Exception:
        return []


def _write(items: List[Dict]) -> None:
    p = _path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items[-5000:], f, indent=2, ensure_ascii=False, default=str)
    os.replace(tmp, p)


def _norm(entry: Dict, project: str = "", source: str = "insight") -> Dict:
    return {
        "id": entry.get("id") or f"{source}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        "kind": str(entry.get("kind") or entry.get("insight_type") or entry.get("severity") or "lesson"),
        "project": entry.get("project") or project,
        "title": str(entry.get("title") or entry.get("summary") or entry.get("description") or "")[:200],
        "description": str(entry.get("description") or entry.get("detail") or "")[:4000],
        "impact": str(entry.get("impact") or entry.get("severity") or "medium").lower(),
        "confidence": float(entry.get("confidence", 0.5) or 0.5),
        "tags": entry.get("tags") or [],
        "source": entry.get("source") or source,
        "created_at": entry.get("created_at") or datetime.now().isoformat(),
        "item_id": entry.get("item_id", ""),
    }


def add(entries: Any, project: str = "", source: str = "insight") -> List[Dict]:
    items = entries if isinstance(entries, list) else [entries]
    normed = [_norm(e, project, source) for e in items if e]
    if not normed:
        return _read()
    data = _read()
    seen = {(i.get("project"), i.get("title")) for i in data}
    for e in normed:
        if (e.get("project"), e.get("title")) in seen:
            continue
        data.append(e)
    _write(data)
    return data


def list_items(kind: str = "", project: str = "") -> List[Dict]:
    out = _read()
    if kind:
        out = [i for i in out if i.get("kind") == kind]
    if project:
        out = [i for i in out if i.get("project") == project]
    return out


def import_file(path: str, project: str = "", source: str = "import") -> Dict:
    """Import a per-project insights.json (e.g. test-framework results) into the canonical store."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {"imported": 0}
    entries = data.get("insights", data) if isinstance(data, dict) else data
    before = len(_read())
    after = len(add(entries or [], project, source))
    return {"imported": max(0, after - before), "total": after}


def import_legacy(results_dir: str = "") -> Dict:
    """One-time: import every test-framework results/<project>/insights.json."""
    root = results_dir or os.path.join(_REPO, "test-framework", "results")
    imported, files = 0, 0
    try:
        for name in os.listdir(root):
            p = os.path.join(root, name, "insights.json")
            if os.path.isfile(p):
                r = import_file(p, project=name, source="qa_intelligence")
                imported += r.get("imported", 0)
                files += 1
    except Exception:
        pass
    return {"files": files, "imported": imported}


def promote_to_backlog(min_impact: str = "high", types: Optional[List[str]] = None) -> Dict:
    """Create Product Forge backlog items from actionable insights (B8)."""
    threshold = _IMPACT_RANK.get(str(min_impact).lower(), 3)
    created = []
    try:
        from core import backlog
        for ins in _read():
            if ins.get("item_id"):
                continue
            if _IMPACT_RANK.get(str(ins.get("impact")).lower(), 0) < threshold:
                continue
            item = backlog.ensure_item(
                "product_forge", None, external_id=f"insight:{ins['id']}",
                title=ins.get("title") or "Insight",
                body=ins.get("description") or "",
                type_="tech-debt", origin="pipeline", source="insights",
                value=3, effort=3, risk=2, moscow="Should",
                links={"insight_id": ins["id"], **({"project": ins["project"]} if ins.get("project") else {})},
            )
            ins["item_id"] = item.get("id", "")
            created.append(item.get("id"))
        if created:
            _write(_read())
    except Exception:
        pass
    return {"created": len(created), "items": created}
