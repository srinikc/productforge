"""Service-level indicators (Section D P4 / BI-PF-0244).

SLIs are DERIVED from the canonical event stream + the call ledger (no new truth):
success rate, run counts, LLM/tool call volume and token totals.
"""
from typing import Dict, Optional


def summary(project_dir: str) -> Dict:
    started = completed = failed = 0
    try:
        from core import events as _ev
        for e in _ev.read(project_dir):
            t = str(e.get("type") or e.get("kind") or "")
            if t == "run_started":
                started += 1
            elif t == "run_completed":
                completed += 1
            elif t == "run_failed":
                failed += 1
    except Exception:
        pass
    denom = completed + failed
    try:
        from core import call_ledger as _cl
        tot = (_cl.summary(project_dir) or {}).get("totals", {}) or {}
    except Exception:
        tot = {}
    return {
        "runs_started": started, "runs_completed": completed, "runs_failed": failed,
        "success_rate": round(completed / denom, 3) if denom else None,
        "llm_calls": tot.get("llm_calls", 0), "prompt_tokens": tot.get("prompt_tokens", 0),
        "output_tokens": tot.get("output_tokens", 0), "tool_calls": tot.get("tool_calls", 0),
    }
