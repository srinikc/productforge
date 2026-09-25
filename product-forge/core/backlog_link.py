"""Plan <-> Backlog bridge (B1).

Keeps `product-plan.json` features and the backlog registry in sync **without duplicating data**:

  Feature (technical decomposition)  <-- feature_id -->  BacklogItem (work registry)
                                                          `feature.backlog_id` (reverse index)

Rules:
  * one writer per file: `core/backlog.py` owns the item; `core/product_plan.py` owns the feature.
  * status mirrors one way: feature -> item.
  * every call here is non-fatal (a bridge failure must never break a pipeline run).
"""
from typing import Any, Dict, Optional

# feature.status (product-plan) -> backlog item status
_FEATURE_TO_ITEM = {
    "planned": "accepted",
    "in-progress": "executing",
    "in_progress": "executing",
    "completed": "verifying",
    "verified": "done",
    "blocked": "blocked",
    "rejected": "rejected",
}

_MOSCOW = {"must-have": "Must", "should-have": "Should", "nice-to-have": "Could"}


def _backlog():
    from core import backlog
    return backlog


def external_id(project: str, feature_id: str) -> str:
    return f"feature:{project}:{feature_id}"


def ensure_feature_item(project: str, feature) -> Optional[Dict]:
    """Get-or-create the backlog item backing a plan feature. Idempotent."""
    try:
        fid = getattr(feature, "id", None) or (feature or {}).get("id")
        if not fid:
            return None
        name = getattr(feature, "name", None) or (feature or {}).get("name", "") or fid
        prio = getattr(feature, "priority", None) or (feature or {}).get("priority", "")
        item = _backlog().ensure_item(
            "project", project, external_id(project, fid), title=name,
            type_="feature", origin="pipeline", source="product-plan",
            moscow=_MOSCOW.get(str(prio), "Should"),
            links={"feature_id": fid},
        )
        return item
    except Exception:
        return None


def mirror_feature_status(project: str, feature_id: str, feature_status: str,
                          title: str = "", priority: str = "") -> Optional[Dict]:
    """Create-if-needed and set the item status from a feature status change."""
    try:
        item = _backlog().ensure_item(
            "project", project, external_id(project, feature_id),
            title=title or feature_id, type_="feature", origin="pipeline",
            source="product-plan", moscow=_MOSCOW.get(str(priority), "Should"),
            links={"feature_id": feature_id},
        )
        mapped = _FEATURE_TO_ITEM.get(str(feature_status), None)
        if mapped and item.get("status") != mapped:
            _backlog().set_status("project", project, item["id"], mapped,
                                  note=f"mirrored from feature {feature_id}: {feature_status}")
        return _backlog().get_epic("project", project, item["id"])
    except Exception:
        return None


def link_defect(project: str, feature_id: str, defect_id: str,
                title: str = "", severity: str = "") -> Optional[Dict]:
    """Record a defect against the feature's item (bug item + defect link)."""
    try:
        bug = _backlog().ensure_item(
            "project", project, f"defect:{project}:{defect_id}",
            title=title or f"Defect {defect_id}", type_="bug", origin="pipeline",
            source="defects", links={"defect_ids": [defect_id], "feature_id": feature_id},
        )
        return bug
    except Exception:
        return None


def resolve_defect(project: str, defect_id: str, note: str = "") -> Optional[Dict]:
    try:
        item = _backlog().get_epic("project", project, "")  # noqa: placeholder never matches
        items = _backlog().list_open("project", project, order=False)
        for it in items:
            if defect_id in (it.get("links", {}).get("defect_ids") or []):
                return _backlog().set_status("project", project, it["id"], "done",
                                             note=note or f"defect {defect_id} resolved")
        return item
    except Exception:
        return None


# ── B2: intake -> backlog promotion ────────────────────────────────
_INTENT_TO_ITEM = {
    "save_idea": ("idea", "parked", "product_forge"),
    "explore": ("explore", "parked", "product_forge"),
    "new_project": ("project", "accepted", "product_forge"),
    "new_project_quick": ("project", "accepted", "product_forge"),
    "modify_project": ("change", "new", "project"),
    "add_context": ("context", "new", "project"),
    "product_forge_improvement": ("change", "new", "product_forge"),
}


def promote_conversation(conv, project: str = "") -> Optional[Dict]:
    """Promote an intake conversation to exactly one backlog item (origin=intake).

    One item per conversation, provenance kept: links.conversation_id + idea_ids.
    Status: `save_idea`/explore -> parked (weekly follow-up); new project -> accepted;
    changes/context -> new in the target project (or Product Forge) backlog.
    """
    try:
        intent = str(getattr(conv, "intent", "") or "")
        item_type, status, default_scope = _INTENT_TO_ITEM.get(intent, ("idea", "new", "product_forge"))
        target_project = project or getattr(conv, "target_project_name", "") or getattr(conv, "project_name", "")
        scope = "project" if (default_scope == "project" and target_project) else "product_forge"
        idea_ids = [getattr(i, "id", "") for i in (getattr(conv, "extracted_ideas", None) or [])]
        title = getattr(conv, "title", "") or (f"{item_type.title()} from {getattr(conv, 'source_platform', 'intake')}")
        body = getattr(conv, "compiled_summary", "") or ""
        meta = dict(getattr(conv, "metadata", None) or {})
        item = _backlog().ensure_item(
            scope, target_project if scope == "project" else None,
            f"conversation:{getattr(conv, 'id', '')}",
            title=title, body=body, type_=item_type, origin="intake",
            source=str(getattr(conv, "source_platform", "") or "intake"),
            value=int(meta.get("value", 3) or 3), effort=int(meta.get("effort", 3) or 3),
            risk=int(meta.get("risk", 2) or 2), moscow=str(meta.get("moscow", "Should")),
            links={"conversation_id": getattr(conv, "id", ""),
                   **({"idea_ids": [i for i in idea_ids if i]} if idea_ids else {})},
        )
        if item and status and item.get("status") != status:
            _backlog().set_status(scope, target_project if scope == "project" else None,
                                  item["id"], status, note=f"intake promotion ({intent})")
        if item and status == "parked":
            _backlog().set_follow_up(scope, target_project if scope == "project" else None,
                                     item["id"], every_days=7)
        return _backlog().get_epic(scope, target_project if scope == "project" else None, item["id"])
    except Exception:
        return None
