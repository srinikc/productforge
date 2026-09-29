"""Deterministic markdown renderer for structured (JSON-first) agent output (BI-0224).

When enabled, sectioned agents (design / product-design-spec and other sectioned agents) emit a
compact JSON payload per section/feature; we render markdown here deterministically. This cuts
generation tokens and removes mid-output stalling, while keeping the final artifact shape stable.
Pure functions only (no LLM, no state) so output is reproducible.
"""
import json
import re
from typing import Any, Dict, List, Optional


def extract_json(text: str) -> Optional[Any]:
    """Parse a fenced ```json block (or the whole text) into an object, else None."""
    if not text:
        return None
    m = re.search(r"```json\s*(.*?)```", text, re.S | re.I)
    raw = m.group(1) if m else text
    raw = (raw or "").strip()
    if not raw or raw[0] not in "[{":
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _bullets(items) -> List[str]:
    out = []
    for it in items or []:
        if isinstance(it, str) and it.strip():
            out.append("- " + it.strip())
        elif isinstance(it, dict):
            t = str(it.get("text") or it.get("title") or "").strip()
            if t:
                out.append("- " + t)
    return out


def render_section(obj: Dict) -> str:
    """Render one section dict {heading|title, text|summary, bullets|items, subsections}."""
    if not isinstance(obj, dict):
        return ""
    h = str(obj.get("heading") or obj.get("title") or "").strip().lstrip("#").strip()
    lines = []
    if h:
        lines.append("## " + h)
    txt = str(obj.get("text") or obj.get("summary") or "").strip()
    if txt:
        lines.append(txt)
    lines += _bullets(obj.get("bullets") or obj.get("items") or [])
    for s in (obj.get("subsections") or []):
        b = render_section(s)
        if b:
            lines.append(b)
    return "\n".join(lines).strip()


def render_payload(payload: Any, title: str = "") -> str:
    """Render a payload (list of sections, or {title, sections|features}) to markdown."""
    if isinstance(payload, list):
        return "\n\n".join(x for x in (render_section(o) for o in payload) if x).strip()
    if not isinstance(payload, dict):
        return ""
    out = []
    t = str(payload.get("title") or title or "").strip()
    if t:
        out.append(t if t.startswith("#") else "# " + t)
    for s in (payload.get("sections") or payload.get("features") or []):
        b = render_section(s)
        if b:
            out.append(b)
    if not out:
        # A single section object passed directly.
        return render_section(payload)
    return "\n\n".join(out).strip()
