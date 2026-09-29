"""Single enforceable agent execution contract (M0.7 / BI-PF-0243).

Every dispatched task should carry a validated, immutable contract. Missing or
unverifiable fields are ``BLOCKED`` (fail closed) — never treated as PASS.
This is the contract *shape* + validator; dispatch wiring calls ``validate`` and
blocks on a non-OK result.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

# Fields that MUST be present and non-empty.
_REQUIRED = ("project", "run_id", "stage_id", "agent_id", "objective", "deliverables")
# Structured fields that MUST be present (dicts) — empty dicts are allowed but the key must exist.
_STRUCTURED = ("permissions", "limits", "verification", "recovery")


def build(project: str, run_id: str, stage_id: str, agent_id: str, objective: str,
          deliverables: List[str], *, permissions: Dict | None = None,
          limits: Dict | None = None, verification: Dict | None = None,
          recovery: Dict | None = None, upstream: Dict | None = None) -> Dict[str, Any]:
    """Assemble an immutable task contract (callers must not mutate after validate)."""
    return {
        "project": str(project or ""),
        "run_id": str(run_id or ""),
        "stage_id": str(stage_id or ""),
        "agent_id": str(agent_id or ""),
        "objective": str(objective or ""),
        "deliverables": list(deliverables or []),
        "permissions": dict(permissions or {}),          # tool allowlist, workspace, network, secrets
        "limits": dict(limits or {}),                    # max tokens/output/cost/wall/tool-calls/retries
        "verification": dict(verification or {}),        # required outputs/tests/approvals/hashes
        "recovery": dict(recovery or {}),                # checkpoint id, idempotency key, retry policy
        "upstream": dict(upstream or {}),                # dependency versions + input artifact hashes
        "created_at": datetime.now().isoformat(),
    }


def validate(contract: Dict[str, Any]) -> Dict[str, Any]:
    """Return {status, ok, missing}. status is OK | BLOCKED (fail closed)."""
    c = contract or {}
    missing: List[str] = [k for k in _REQUIRED if not str(c.get(k) or "").strip()]
    for k in _STRUCTURED:
        if not isinstance(c.get(k), dict):
            missing.append(k)
    return {"status": "BLOCKED" if missing else "OK", "ok": not missing, "missing": missing}
