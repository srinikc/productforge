"""Intake adapter registry (B2).

Per-source adapters live as assets: `adapters/<source>/{schema.yaml,instructions.md}`
(chatgpt, claude, gemini, generic, ...). This module resolves them, normalizes incoming
payloads to one schema, and converts them into a Conversation for the existing intake
engine (`conversation_models` + `intent_router`). The engine promotes to backlog items.

No second intake path: adapters -> conversation -> item.
"""
import os
from typing import Any, Dict, List, Optional

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ADAPTERS_DIR = os.path.join(_REPO, "adapters")

# builtin fallbacks when an adapter has no assets on disk
_BUILTIN = {
    "generic": {
        "instructions": (
            "POST JSON to /api/intake (or /api/v1/intake).\n"
            "Fields: title* (string), body, scope ('project'|'pipeline'), project (name, "
            "required when scope=project), kind ('feature'|'bug'|'enhancement'|'idea'|'context'), "
            "value/effort/risk (1-5), moscow ('Must'|'Should'|'Could'), deps[], links{}.\n"
            "Anything else is preserved in the raw archive."),
    },
    "chatgpt": {"instructions": "Custom GPT 'send to Product Forge': title, description, product, category, priority."},
    "claude": {"instructions": "Claude MCP/desktop: send the conversation + title."},
    "gemini": {"instructions": "Gemini extension: title/name, prompt/body, project, type."},
    "dashboard": {"instructions": "Dashboard form maps 1:1 to the intake schema."},
    "file": {"instructions": "Offline drop: JSON/JSONL file with the intake schema (title required)."},
}

_KIND_ALIASES = {
    "bug": "bug", "bugfix": "bug", "defect": "bug",
    "feature": "feature", "enhancement": "change", "change": "change", "improvement": "change",
    "idea": "idea", "explore": "explore", "context": "context", "tech-debt": "tech-debt",
}


def sources() -> List[str]:
    found = set(_BUILTIN.keys())
    try:
        for name in os.listdir(_ADAPTERS_DIR):
            p = os.path.join(_ADAPTERS_DIR, name)
            if os.path.isdir(p) and name not in ("__pycache__",):
                found.add(name)
    except Exception:
        pass
    return sorted(found)


def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def instructions(source: str = "generic") -> str:
    """Adapter instructions (from adapters/<src>/instructions.md when present)."""
    p = os.path.join(_ADAPTERS_DIR, source, "instructions.md")
    txt = _read(p)
    if txt:
        return txt
    return (_BUILTIN.get(source) or _BUILTIN["generic"])["instructions"]


def schema_path(source: str = "generic") -> str:
    p = os.path.join(_ADAPTERS_DIR, source, "schema.yaml")
    return p if os.path.exists(p) else ""


def _pick(payload: Dict, keys) -> Optional[Any]:
    for k in keys or []:
        if isinstance(payload, dict) and payload.get(k) not in (None, ""):
            return payload[k]
    return None


_LEGACY_FORGE_SCOPE = "fac" "tory"   # legacy alias seen in early payloads

_FIELD_ALIASES = {
    "title": ("title", "name", "summary", "subject"),
    "body": ("body", "description", "content", "text", "details", "prompt"),
    "project": ("project", "product", "app", "target_project"),
    "kind": ("kind", "type", "category"),
    "scope": ("scope", "target"),
    "moscow": ("moscow", "priority"),
}


def normalize(source: str, payload: Dict) -> Dict:
    """Map any adapter payload to the intake schema (scope uses Product Forge naming)."""
    payload = payload if isinstance(payload, dict) else {}
    title = _pick(payload, _FIELD_ALIASES["title"]) or "Untitled item"
    kind = str(_pick(payload, _FIELD_ALIASES["kind"]) or "feature").strip().lower()
    scope = str(_pick(payload, _FIELD_ALIASES["scope"]) or "project").strip().lower()
    if scope in ("pipeline", "portfolio", _LEGACY_FORGE_SCOPE, "product_forge", "product-forge"):
        scope = "product_forge"
    moscow = str(_pick(payload, _FIELD_ALIASES["moscow"]) or "Should").capitalize()

    def _int(v, d):
        try:
            return int(v)
        except (TypeError, ValueError):
            return d

    return {
        "title": str(title)[:200],
        "body": str(_pick(payload, _FIELD_ALIASES["body"]) or "")[:8000],
        "project": _pick(payload, _FIELD_ALIASES["project"]) or "",
        "kind": _KIND_ALIASES.get(kind, "feature"),
        "scope": scope,
        "moscow": moscow if moscow in ("Must", "Should", "Could", "Wont") else "Should",
        "value": _int(payload.get("value"), 3),
        "effort": _int(payload.get("effort"), 3),
        "risk": _int(payload.get("risk"), 2),
        "deps": payload.get("deps") or [],
        "links": payload.get("links") or {},
        "source": source,
    }


def infer_intent(fields: Dict, payload: Dict) -> str:
    """Decide the conversation intent for the intake engine.

    Order matters: an EXPLICIT intent from the caller always wins (so the intake
    channel is routed correctly); otherwise it is inferred from the payload.
    """
    from core.conversation_models import IntentType
    _valid = {i.value for i in IntentType}
    explicit = str(_pick(payload, ("intent",)) or fields.get("intent") or "").strip().lower()
    if explicit in _valid:
        return explicit
    scope = fields.get("scope")
    kind = fields.get("kind")
    if kind in ("idea", "explore"):
        return IntentType.SAVE_IDEA.value
    if _pick(payload, ("new_project", "is_new_project")) or kind == "project":
        return IntentType.NEW_PROJECT.value
    if scope == "product_forge":
        return IntentType.PRODUCT_FORGE_IMPROVEMENT.value
    if kind == "context":
        return IntentType.ADD_CONTEXT.value
    if fields.get("project"):
        return IntentType.MODIFY_PROJECT.value
    return IntentType.SAVE_IDEA.value


def to_conversation(source: str, payload: Dict) -> Dict:
    """Build a conversation payload for ConversationStore/IntentRouter."""
    fields = normalize(source, payload)
    intent = infer_intent(fields, payload)
    body = fields.get("body") or fields.get("title")
    return {
        "source_platform": source if source in ("chatgpt", "gemini", "claude") else "manual",
        "intent": intent,
        "title": fields["title"],
        "project_name": fields.get("project") or payload.get("project_name") or "",
        "target_project_name": fields.get("project") or "",
        "scope": fields.get("scope"),
        "kind": fields.get("kind"),
        "messages": [{"role": "user", "content": body}],
        "metadata": {"adapter": source, "raw_payload": payload,
                     "value": fields["value"], "effort": fields["effort"],
                     "risk": fields["risk"], "moscow": fields["moscow"]},
    }
