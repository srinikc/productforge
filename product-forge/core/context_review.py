"""LLM-judged backlog context review (BI-PF-0565).

Answers: is this item's context implementable by a standalone engineer/agent with no further digging?
Judges the four dimensions — WHAT / WHY / HOW / WHERE — via the single LLM owner (core/orchestrator/
llm_client), following the ``brief_check`` pattern (inject an ``llm`` callable; when no validator is
available, return ``ok=None`` — NEVER invent a verdict).

ADVISORY by default (``ok`` may be None). ``review`` is a pure read over the item dict; no store/engine.
"""
import json
import os
import re
from typing import Callable, Optional

_RUBRIC = (
    "You review backlog work items. Decide whether the item's CONTEXT is sufficient for a standalone "
    "engineer or autonomous agent to implement it with NO further digging. A sufficient item states: "
    "WHAT is required, WHY (problem/value), HOW it will be done (approach), and WHERE (affected "
    "components/files). Reply with ONLY compact JSON: "
    '{"implementable": true|false, "missing": ["what"|"why"|"how"|"where"], "reason": "<short>"}.'
)

_RENDER_FIELDS = ("objective", "in_scope", "out_of_scope", "affected_components", "affected_files",
                  "approach", "acceptance_criteria", "verification")


def _render(item: dict) -> str:
    lines = [f"TITLE: {item.get('title') or ''}"]
    b = item.get("brief") or {}
    for k in ("problem", "what_adds", "why", "who_feels"):
        if b.get(k):
            lines.append(f"{k.upper()}: {b.get(k)}")
    for k in _RENDER_FIELDS:
        v = item.get(k)
        if v:
            lines.append(f"{k.upper()}: {json.dumps(v, default=str, ensure_ascii=False)}")
    return "\n".join(lines)


def _extract_json(text: str) -> Optional[dict]:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def default_llm(project: str = "default", products_dir: Optional[str] = None) -> Callable[[str], str]:
    """Build a one-shot LLM callable from the single LLM owner (no new client)."""
    from core.paths import PRODUCTS_DIR
    from core.model_registry import ModelCapabilityRegistry
    from core.orchestrator.model_router import ModelRouter
    from core.orchestrator.storage import LLMCache
    from core.orchestrator.llm_client import LLMClient

    pd = str(products_dir or PRODUCTS_DIR)
    project_dir = os.path.join(pd, project)
    os.makedirs(project_dir, exist_ok=True)
    reg = ModelCapabilityRegistry()
    router = ModelRouter(reg, pd, project_dir, None)
    client = LLMClient(reg, router.get_agent_model_config, LLMCache(project_dir), project=project)
    try:
        client.project_dir = project_dir
    except Exception:
        pass

    def llm(prompt: str) -> str:
        text, _meta = client._call_llm(prompt, "context-review", "0")
        return text or ""

    return llm


def review(item: dict, llm: Optional[Callable[[str], str]] = None, *, fallback_llm: bool = True) -> dict:
    """Return {ok, source, implementable, missing, reason}. ``ok`` is True/False, or None when no validator."""
    if llm is None and fallback_llm:
        try:
            llm = default_llm()
        except Exception:
            llm = None
    if llm is None:
        return {"ok": None, "source": "no-validator", "implementable": None, "missing": [],
                "reason": "context reviewer unavailable"}
    try:
        raw = llm(_RUBRIC + "\n\nITEM:\n" + _render(item))
    except Exception as e:  # noqa: BLE001
        return {"ok": None, "source": "no-validator", "implementable": None, "missing": [],
                "reason": f"reviewer error: {type(e).__name__}"}
    v = _extract_json(raw)
    if v is None:
        return {"ok": None, "source": "llm-unparseable", "implementable": None, "missing": [],
                "reason": "reviewer returned no JSON"}
    impl = bool(v.get("implementable"))
    return {"ok": impl, "source": "llm", "implementable": impl,
            "missing": [str(x) for x in (v.get("missing") or [])],
            "reason": str(v.get("reason") or "")}
