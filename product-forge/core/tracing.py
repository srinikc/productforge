"""Minimal trace context (Section D / BI-PF-0244, phase P1).

`trace_id` == the run id (one trace per run); `span_id` identifies one record/operation
within the trace. Kept tiny and dependency-free so every emit point can tag records.
"""
import os
import uuid


def new_span_id() -> str:
    return uuid.uuid4().hex[:16]


def trace_id(project_dir: str = "", run_id: str = "") -> str:
    """The trace id for the current run: explicit run_id, else the project's current run."""
    if run_id:
        return str(run_id)
    try:
        from core.audit_trail import current_run_id
        return str(current_run_id(os.path.basename(str(project_dir).rstrip("/\\"))) or "")
    except Exception:
        return ""
