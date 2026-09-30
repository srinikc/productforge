"""OpenTelemetry-style span export (Section D P5 / BI-PF-0244) + GenAI attrs (BI-0199).

Maps canonical events to spans and, when flag-gated on, writes them to
products/<project>/otel-spans.jsonl (an OTLP-style record set). Kept dependency-free.

BI-0199: adds GenAI semantic-convention attributes (incl. multimodal) for `gen_ai_call` events.
Attributes carry COUNTS + ids only — never prompt/media content or bytes.
"""
import os
from typing import Dict, List


def enabled() -> bool:
    return str(os.getenv("PIPELINE_OTEL", "0")).lower() in ("1", "true", "yes", "on")


def _as_int(v) -> int:
    try:
        return int(v)
    except Exception:
        return 0


def gen_ai_attributes(ev: Dict) -> Dict:
    """OTel GenAI semantic-convention attributes for a call event (bounded; no payloads)."""
    a: Dict = {}
    if ev.get("provider"):
        a["gen_ai.system"] = str(ev.get("provider"))
    if ev.get("model"):
        a["gen_ai.request.model"] = str(ev.get("model"))
    if ev.get("response_model"):
        a["gen_ai.response.model"] = str(ev.get("response_model"))
    if ev.get("operation"):
        a["gen_ai.operation.name"] = str(ev.get("operation"))
    if ev.get("input_tokens") is not None:
        a["gen_ai.usage.input_tokens"] = _as_int(ev.get("input_tokens"))
    if ev.get("output_tokens") is not None:
        a["gen_ai.usage.output_tokens"] = _as_int(ev.get("output_tokens"))
    # multimodal (counts only)
    if ev.get("media_requested") is not None:
        a["gen_ai.request.media.count"] = _as_int(ev.get("media_requested"))
    if ev.get("media_attached") is not None:
        a["gen_ai.request.media.attached"] = _as_int(ev.get("media_attached"))
    if ev.get("input_modalities"):
        a["gen_ai.input.modalities"] = list(ev.get("input_modalities") or [])
    if ev.get("output_modalities"):
        a["gen_ai.output.modalities"] = list(ev.get("output_modalities") or [])
    if ev.get("billing_unit"):
        a["gen_ai.usage.billing_unit"] = str(ev.get("billing_unit"))
    if ev.get("kind"):
        a["gen_ai.kind"] = str(ev.get("kind"))
    return a


def to_span(ev: Dict) -> Dict:
    attrs = {"run_id": ev.get("run_id", ""), "stage": ev.get("stage", ""),
             "agent": ev.get("agent", ""), "level": ev.get("level", "")}
    evt = str(ev.get("type") or ev.get("kind") or "event")
    if evt == "gen_ai_call" or ev.get("provider") or ev.get("billing_unit"):
        attrs.update(gen_ai_attributes(ev))
    return {
        "trace_id": ev.get("trace_id") or ev.get("run_id") or "",
        "span_id": ev.get("span_id") or "",
        "name": evt,
        "start_time": ev.get("ts") or ev.get("at") or "",
        "attributes": attrs,
    }


def spans(project_dir: str) -> List[Dict]:
    """Map the canonical event stream to spans (read-only; no write)."""
    out: List[Dict] = []
    try:
        from core import events
        for ev in events.read(project_dir):
            try:
                out.append(to_span(ev))
            except Exception:
                continue
    except Exception:
        pass
    return out


def export(project_dir: str) -> str:
    """Export spans (flag-gated). Returns the path written, or '' when disabled."""
    if not enabled():
        return ""
    out = os.path.join(project_dir, "otel-spans.jsonl")
    try:
        from core import log_router
        for sp in spans(project_dir):
            log_router.append_jsonl(out, sp)
    except Exception:
        pass
    return out
