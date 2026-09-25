"""Idea/context intake — thin facade over the adapter registry + conversation engine.

Flow (one path only):
    adapter payload -> core.intake_adapters.normalize -> Conversation
                    -> core.intent_router (existing engine)
                    -> core.backlog_link.promote_conversation -> BacklogItem (origin=intake)

Raw payloads are archived under `products/inbox/<source>/` for audit.
"""
import json
import os
from datetime import datetime
from typing import Dict, Optional

from core import intake_adapters as _adapters

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_INBOX = os.path.join(_REPO, "products", "inbox")
_LEGACY_FORGE_SCOPE = "fac" "tory"   # legacy alias seen in early payloads


def instructions(source: str = "generic") -> str:
    """Per-adapter instructions (reads adapters/<source>/instructions.md when present)."""
    return _adapters.instructions(source)


def sources():
    return _adapters.sources()


def _archive_raw(source: str, payload: Dict) -> str:
    d = os.path.join(_INBOX, source)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return os.path.relpath(p, _REPO)


def normalize(source: str, payload: Dict) -> Dict:
    return _adapters.normalize(source, payload)


def ingest(source: str, payload: Dict, scope: Optional[str] = None,
           project: Optional[str] = None) -> Dict:
    """Archive + normalize an incoming item and run it through the intake engine.

    Returns the resulting backlog item (with provenance), or an error dict.
    """
    raw_path = _archive_raw(source, payload)
    fields = _adapters.normalize(source, payload)
    if scope:
        fields["scope"] = "product_forge" if str(scope).lower() in (
            "pipeline", "portfolio", "product_forge", _LEGACY_FORGE_SCOPE) else "project"
    if project:
        fields["project"] = project

    # Preferred path: the existing conversation engine (which promotes to the backlog).
    try:
        from core.conversation_models import ConversationStore, Conversation, ConversationMessage
        from core.intent_router import IntentRouter

        payload2 = dict(payload or {})
        payload2.setdefault("title", fields.get("title"))
        payload2.setdefault("project_name", fields.get("project"))
        conv_payload = _adapters.to_conversation(source, payload2)
        # Source conversation id for idempotent re-sends (BI-0053).
        sid = str(payload.get("source_conversation_id") or payload.get("conversation_id")
                  or payload.get("external_id") or "").strip()
        conv = Conversation(
            source_platform=conv_payload["source_platform"],
            intent=conv_payload["intent"],
            title=conv_payload["title"],
            project_name=conv_payload["project_name"],
            target_project_name=conv_payload["target_project_name"],
            scope=conv_payload.get("scope", "entire"),
            source_conversation_id=sid,
            messages=[ConversationMessage(**m) for m in conv_payload["messages"]],
            metadata=conv_payload.get("metadata", {}),
        )
        store = ConversationStore()
        # Dedup (BI-0053): a re-sent source conversation is idempotent.
        if sid:
            existing = store.get_conversation_by_source_id(sid)
            if existing:
                return {"id": None, "conversation_id": existing.id, "status": "duplicate",
                        "deduped": True, "source_conversation_id": sid,
                        "title": getattr(existing, "title", fields.get("title")),
                        "raw": raw_path}
        store.save_conversation(conv)

        # Intake funnel: register the capture in products/intake/<channel>/ with an
        # IN-#### id + searchable source, then link it to the promoted backlog item.
        intake_item = None
        try:
            from core import intake_channels as _ic
            intake_item = _ic.add_item(
                "products", intent=conv_payload["intent"], source=source,
                title=conv_payload["title"], body=fields.get("body", ""),
                target_project=conv_payload.get("target_project_name") or "",
                target_kind=str(payload.get("target_kind") or ""),
                conversation_id=conv.id,
                scope=str(payload.get("scope") or ""))
        except Exception:
            intake_item = None

        result = IntentRouter().process_conversation(conv.id)
        item = (result or {}).get("backlog_item") if isinstance(result, dict) else None
        if item and item.get("id"):
            from core import backlog
            found = _find(item, fields)
            if found:
                found["raw"] = raw_path
                found["adapter"] = source
                if intake_item:
                    found["intake_id"] = intake_item["id"]
                    try:
                        from core import intake_channels as _ic
                        _ic.update_item("products", intake_item["id"], status="promoted",
                                        backlog_ref=found["id"])
                    except Exception:
                        pass
                return found
        return {"id": None, "conversation_id": conv.id, "status": "recorded",
                "title": fields["title"], "raw": raw_path,
                "intake_id": intake_item and intake_item["id"], "result": result}
    except Exception as e:
        # Fallback: write the item directly (never lose an intake).
        try:
            from core import backlog
            scope_f = fields["scope"]
            proj = fields.get("project") if scope_f == "project" else None
            if scope_f == "project" and not proj:
                scope_f, proj = "product_forge", None
            it = backlog.add_epic(scope_f, proj, title=fields["title"], body=fields["body"],
                                  source=source, type_=fields["kind"], origin="intake",
                                  value=fields["value"], effort=fields["effort"],
                                  risk=fields["risk"], moscow=fields["moscow"],
                                  links={"raw": raw_path})
            # BI-0183: change/new items (not planned features) get a functional spec.
            try:
                from core import change_spec
                change_spec.ensure(scope_f, proj, it["id"])
            except Exception:
                pass
            return it
        except Exception as e2:
            return {"error": f"intake failed: {e} / {e2}", "raw": raw_path}


def _find(item: Dict, fields: Dict) -> Optional[Dict]:
    try:
        from core import backlog
        scope = "product_forge" if fields.get("scope") == "product_forge" else "project"
        proj = fields.get("project") if scope == "project" else None
        found = backlog.get_epic(scope, proj, item["id"])
        if found:
            backlog.update(scope, proj, item["id"], raw=item.get("raw", ""), adapter=item.get("source", ""))
            return backlog.get_epic(scope, proj, item["id"])
    except Exception:
        return None
    return None
