"""OpenTelemetry-style span export (Section D P5 / BI-PF-0244).

Maps canonical events to spans and, when flag-gated on, writes them to
products/<project>/otel-spans.jsonl (an OTLP-style record set). Kept dependency-free.
"""
import os
from typing import Dict, List


def enabled() -> bool:
    return str(os.getenv("PIPELINE_OTEL", "0")).lower() in ("1", "true", "yes", "on")


def to_span(ev: Dict) -> Dict:
    return {
        "trace_id": ev.get("trace_id") or ev.get("run_id") or "",
        "span_id": ev.get("span_id") or "",
        "name": str(ev.get("type") or ev.get("kind") or "event"),
        "start_time": ev.get("ts") or ev.get("at") or "",
        "attributes": {"run_id": ev.get("run_id", ""), "stage": ev.get("stage", ""),
                       "agent": ev.get("agent", ""), "level": ev.get("level", "")},
    }


def export(project_dir: str) -> str:
    """Export spans (flag-gated). Returns the path written, or '' when disabled."""
    if not enabled():
        return ""
    out = os.path.join(project_dir, "otel-spans.jsonl")
    try:
        from core import events, log_router
        for ev in events.read(project_dir):
            log_router.append_jsonl(out, to_span(ev))
    except Exception:
        pass
    return out
