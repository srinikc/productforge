"""Media context selector (BI-PF-0287) — the link from the asset store to an agent's LLM call.

Given an agent + the chosen model, decide what media it should receive:

  * model accepts the modality  -> NATIVE parts (asset_store.to_media: tiles/segments/frames first)
  * otherwise (text-only model) -> a bounded TEXT SUMMARY (never raw bytes)

Also estimates the media token cost so the context budget can react. Pure: no store, no writes.

Reuses (never duplicates): ``core.asset_store`` (assets + to_media), ``core.multimodal`` (modality gating),
``core.model_catalog`` (via multimodal). Fail-closed: unknown model/asset => summary/nothing, never raises.

See docs/MEDIA-CONTEXT-DESIGN.md.
"""

import os
import re
from typing import Dict, List, Optional, Tuple

# agents that should receive media by modality (media agents + analysts)
_MEDIA_AGENTS = {"media-analyst", "media-generator", "media-editor", "asset-librarian",
                 "doc-analyst", "sensor-analyst"}

_REF_RE = re.compile(r"(AS-[0-9a-fA-F]{6,}(?:-\d+)?)")
_MD_LINK_RE = re.compile(r"!?\[[^\]]*\]\(\s*(?:\./)?assets/(AS-[0-9a-fA-F]{6,}(?:-\d+)?)[^)]*\)")
MAX_PARTS = 6                    # bound parts per call
MAX_SUMMARY_CHARS = 2000


def _mode() -> str:
    try:
        from core import env_flags as _ef
        return str(_ef.get("PIPELINE_MEDIA_CONTEXT", "summary") or "summary").lower()
    except Exception:
        return os.getenv("PIPELINE_MEDIA_CONTEXT", "summary").lower()


def _budget_tokens() -> int:
    try:
        from core import env_flags as _ef
        return int(_ef.get("PIPELINE_MEDIA_BUDGET_TOKENS", "6000") or 6000)
    except Exception:
        return 6000


def _summary_budget() -> int:
    try:
        from core import env_flags as _ef
        return int(_ef.get("PIPELINE_MEDIA_SUMMARY_CHARS", str(MAX_SUMMARY_CHARS)) or MAX_SUMMARY_CHARS)
    except Exception:
        return MAX_SUMMARY_CHARS


def _referenced_assets(text: str) -> List[str]:
    """Resolve asset ids referenced in text: bare AS-* tokens AND markdown asset links."""
    found = _MD_LINK_RE.findall(text or "") + _REF_RE.findall(text or "")
    return list(dict.fromkeys(found))


def select_assets(project_dir: str, agent_id: str = "",
                  upstream_text: str = "") -> List[Dict]:
    """Choose assets for an agent: media agents get all media assets; others only referenced ones."""
    try:
        from core import asset_store as _as
        all_assets = [a for a in _as.list_assets(project_dir) if a.get("type") != "file"]
    except Exception:
        return []
    if not all_assets:
        return []
    if agent_id in _MEDIA_AGENTS:
        return all_assets
    refs = set(_referenced_assets(upstream_text))
    if not refs:
        return []
    return [a for a in all_assets if a.get("asset_id") in refs]


def estimate_tokens(parts: List[Dict]) -> int:
    """Conservative media token estimate: image tiles ~1k, audio ~ seconds*25, video frames ~1k."""
    total = 0
    for p in (parts or []):
        # parts may carry a size hint; else a flat per-part estimate
        b = int(p.get("bytes") or 0)
        total += max(250, min(4000, b // 2048)) if b else 1000
    return total


def _summary(project_dir: str, assets: List[Dict]) -> str:
    """Bounded text summary of assets (+ docs/media/analysis.md if present)."""
    lines: List[str] = []
    for a in assets:
        meta = a.get("metadata") or {}
        dims = meta.get("dimensions") or ""
        dur = meta.get("duration") or ""
        extra = f" dims={dims}" if dims else (f" dur={dur}s" if dur else "")
        lines.append(f"- {a.get('asset_id')} [{a.get('type')}] {a.get('name','')}{extra} "
                     f"({a.get('bytes',0)}B)")
    txt = "MEDIA ASSETS (summaries; raw media not attached):\n" + "\n".join(lines)
    try:
        p = os.path.join(project_dir, "docs", "media", "analysis.md")
        if os.path.isfile(p):
            with open(p, encoding="utf-8", errors="ignore") as f:
                txt += "\n\nMEDIA ANALYSIS:\n" + f.read()
    except Exception:
        pass
    return txt[:max(200, _summary_budget())]


def chunk_media(project_dir: str, parts: List[Dict], budget_tokens: int = 0) -> List[Dict]:
    """Bound parts to a token budget by dropping the least-priority parts (children come first).

    Fail-closed: if even the first part exceeds the budget, return [] (caller falls back to summary)."""
    budget = budget_tokens or _budget_tokens()
    out: List[Dict] = []
    used = 0
    for p in (parts or []):
        cost = estimate_tokens([p])
        if out and used + cost > budget:
            break
        if not out and cost > budget:
            return []  # a single part already over budget -> summary-only
        out.append(p)
        used += cost
        if len(out) >= MAX_PARTS:
            break
    return out


def for_agent(project_dir: str, agent_id: str, model_name: str = "",
              contract: Optional[Dict] = None,
              upstream_text: str = "") -> Tuple[List[Dict], str, int]:
    """Return (parts, summary_text, media_tokens). Fail-closed; never raises.

    ``parts`` is non-empty only when mode == 'native' AND the model accepts every selected modality.
    ``summary_text`` is always available (bounded) when assets exist.
    """
    try:
        assets = select_assets(project_dir, agent_id, upstream_text)
        if not assets:
            return [], "", 0
        summary = _summary(project_dir, assets)
        mode = _mode()
        if mode != "native":
            return [], summary, 0
        # gate on the model's input modalities (fail-closed)
        from core import multimodal as _mm
        accepted = set(_mm.model_inputs(model_name)) if model_name else {"text"}
        parts: List[Dict] = []
        from core import asset_store as _as
        for a in assets:
            if a.get("type") not in accepted:
                continue
            parts.extend(_as.to_media(project_dir, a))
            if len(parts) >= MAX_PARTS:
                parts = parts[:MAX_PARTS]
                break
        if not parts:
            return [], summary, 0
        # BI-PF-0288: bound media to the per-call budget (drop least-priority parts; summary fallback).
        parts = chunk_media(project_dir, parts)
        if not parts:
            return [], summary, 0
        return parts, summary, estimate_tokens(parts)
    except Exception:
        return [], "", 0
