"""Multimodal LLM plumbing (BI-0186) — attach image/audio/video parts to LLM requests.

`llm_client` builds text-only messages; this module turns a caller-supplied media list into
OpenAI-style multimodal ``content`` parts, GATED by the selected model's ``input_modalities``
(from ``config/model-catalog.json``). Fail-closed: media whose modality the model does not accept
is DROPPED (reported), never sent, never an exception.

No store, no config. Pure helpers. See docs/MULTIMODAL-LLM-DESIGN.md.
"""

import base64
import os
from typing import Dict, List, Optional, Tuple

# media "type" -> (modality, part-type). ``file`` maps to the text-ish document part.
MODALITY_TO_PART = {
    "image": ("image", "image_url"),
    "audio": ("audio", "input_audio"),
    "video": ("video", "video_url"),
    "file": ("file", "text"),
}

MAX_BYTES = 8 * 1024 * 1024  # 8 MB cap per media item

_MIME = {"image": "image/png", "audio": "audio/wav", "video": "video/mp4", "file": "text/plain"}


def model_inputs(model_name: str) -> List[str]:
    """Input modalities the model accepts (from the model catalog). Unknown => ['text']."""
    try:
        from core import model_catalog as _mc
        caps = _mc.capabilities(model_name) or {}
        mods = caps.get("input_modalities") or caps.get("modalities") or []
        mods = [str(m).lower() for m in mods if m]
        return mods or ["text"]
    except Exception:
        return ["text"]


def _data_url(mime: str, raw: bytes) -> str:
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")


def coerce(media: Optional[List[Dict]]) -> List[Dict]:
    """Normalize caller media into canonical parts: {modality, part_type, value, ref}."""
    out: List[Dict] = []
    for m in media or []:
        if not isinstance(m, dict):
            continue
        typ = str(m.get("type") or m.get("modality") or "").lower()
        mapping = MODALITY_TO_PART.get(typ)
        if not mapping:
            continue
        modality, part_type = mapping
        mime = str(m.get("mime") or _MIME.get(modality, "application/octet-stream"))
        value = None
        ref = str(m.get("path") or m.get("url") or m.get("name") or "")
        if m.get("url"):
            value = str(m["url"])
        elif m.get("data"):
            d = str(m["data"])
            value = d if d.startswith("data:") else f"data:{mime};base64,{d}"
        elif m.get("path"):
            try:
                p = str(m["path"])
                if os.path.getsize(p) > MAX_BYTES:
                    out.append({"modality": modality, "part_type": part_type,
                                "value": None, "ref": ref, "error": "oversized"})
                    continue
                with open(p, "rb") as f:
                    value = _data_url(mime, f.read())
            except Exception as e:
                out.append({"modality": modality, "part_type": part_type,
                            "value": None, "ref": ref, "error": f"unreadable:{e}"})
                continue
        else:
            continue
        out.append({"modality": modality, "part_type": part_type, "value": value, "ref": ref})
    return out


def parts_for(model_name: str, media: Optional[List[Dict]]) -> Tuple[List[Dict], List[Dict]]:
    """(supported, dropped) media parts for a model. Dropped = unsupported/errored (fail-closed)."""
    supported_mods = set(model_inputs(model_name))
    supported: List[Dict] = []
    dropped: List[Dict] = []
    for p in coerce(media):
        if p.get("value") is None or p.get("modality") not in supported_mods:
            dropped.append(p)
        else:
            supported.append(p)
    return supported, dropped


def part_payload(part: Dict) -> Dict:
    """The wire form of one part (OpenAI multimodal content element)."""
    pt = part.get("part_type")
    v = part.get("value")
    if pt == "image_url":
        return {"type": "image_url", "image_url": {"url": v}}
    if pt == "video_url":
        return {"type": "video_url", "video_url": {"url": v}}
    if pt == "input_audio":
        # OpenAI input_audio wants raw base64 + format, not a data URL
        fmt = "wav"
        b64 = str(v)
        if b64.startswith("data:"):
            head, _, b64 = b64.partition(",")
            fmt = head.split(";")[0].split("/")[-1] or fmt
        return {"type": "input_audio", "input_audio": {"data": b64, "format": fmt}}
    return {"type": "text", "text": str(v)}


def user_content(prompt: str, parts: Optional[List[Dict]]):
    """Build the ``content`` value: a plain string when no parts, else a text+media list."""
    if not parts:
        return prompt
    content: List[Dict] = [{"type": "text", "text": prompt}]
    content.extend(part_payload(p) for p in parts)
    return content


def build(model_name: str, prompt: str,
          media: Optional[List[Dict]]) -> Tuple[object, List[Dict]]:
    """Convenience: (content, dropped). content is str or list."""
    supported, dropped = parts_for(model_name, media)
    return user_content(prompt, supported), dropped
