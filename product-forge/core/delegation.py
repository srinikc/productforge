"""
Orchestrator-Routed Delegation (Agent-to-Agent)

Instead of free-form peer chat (a token multiplier), delegation is *routed* by
the orchestrator using the pipeline definition's `sub_agents`,
`can_invoke`, and `decision_logic`. Key safeguards:

  - Context firewall: the delegated agent receives a CAPPED payload
    (head+tail), never the full transcript.
  - Message budget: max invocations per stage and per run.
  - Optional transport: an AgentMessenger HANDOFF message is recorded for
    audit/telemetry (no full context is shipped through it).

This module is pure decision/accounting; the executor performs the actual
invocation.
"""
import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any


@dataclass
class DelegationRecord:
    stage_id: str
    from_agent: str
    to_agent: str
    signal: str
    payload_chars: int
    status: str = "requested"
    tokens: int = 0
    cost: float = 0.0
    message_id: str = ""
    timestamp: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)


class DelegationBudget:
    """Caps that stop delegation from becoming a token multiplier."""

    def __init__(self, max_invocations_per_stage: int = 2,
                 max_total_invocations: int = 8,
                 max_payload_chars: int = 4000):
        self.max_per_stage = max_invocations_per_stage
        self.max_total = max_total_invocations
        self.max_payload_chars = max_payload_chars
        self._per_stage: Dict[str, int] = {}
        self.total = 0

    def can_invoke(self, stage_id: str) -> bool:
        return (self.total < self.max_total and
                self._per_stage.get(stage_id, 0) < self.max_per_stage)

    def record(self, stage_id: str):
        self._per_stage[stage_id] = self._per_stage.get(stage_id, 0) + 1
        self.total += 1

    def status(self) -> Dict:
        return {"total": self.total, "max_total": self.max_total,
                "per_stage": self._per_stage, "max_per_stage": self.max_per_stage}


class DelegationRouter:
    def __init__(self, pipeline_def: Dict, project: str = "default",
                 products_dir: str = "products", budget: Optional[DelegationBudget] = None,
                 messenger=None):
        self.pipeline_def = pipeline_def or {}
        self.project = project
        self.products_dir = products_dir
        self.budget = budget or DelegationBudget()
        self.messenger = messenger
        self.records: List[DelegationRecord] = []

    # ── config ───────────────────────────────────────────────────
    def _stage_cfg(self, stage_id: str) -> Dict:
        return (self.pipeline_def.get("stages", {}) or {}).get(stage_id, {}) or {}

    def _agent_capabilities(self, from_agent: str) -> Dict:
        return (self.pipeline_def.get("agent_capabilities", {}) or {}).get(from_agent, {}) or {}

    # ── routing ──────────────────────────────────────────────────
    def resolve(self, stage_id: str, from_agent: str,
                candidate_signals: List[str]) -> Optional[str]:
        """Resolve a delegated target from decision_logic / can_invoke."""
        stage = self._stage_cfg(stage_id)
        subs = stage.get("sub_agents", {}) or {}
        entry = subs.get(from_agent, {}) or {}

        # 1) stage-level decision_logic
        decision_logic = entry.get("decision_logic", {}) or {}
        for sig in candidate_signals:
            if sig in decision_logic:
                return decision_logic[sig]

        # 2) stage-level can_invoke
        can_invoke = entry.get("can_invoke", []) or []
        for sig in candidate_signals:
            if sig in can_invoke:
                return sig

        # 3) global agent_capabilities fallback
        caps = self._agent_capabilities(from_agent)
        gdl = caps.get("decision_logic", {}) or {}
        for sig in candidate_signals:
            if sig in gdl:
                return gdl[sig]
        gci = caps.get("can_invoke", []) or []
        for sig in candidate_signals:
            if sig in gci:
                return sig
        return None

    # ── context firewall ─────────────────────────────────────────
    def cap_payload(self, text: str, max_chars: Optional[int] = None) -> str:
        """Head+tail truncation so delegated agents get a bounded payload."""
        max_chars = max_chars or self.budget.max_payload_chars
        if not text:
            return ""
        if len(text) <= max_chars:
            return text
        half = max_chars // 2
        return (text[:half] +
                f"\n\n...[delegation payload truncated: {len(text) - max_chars} chars dropped]...\n\n" +
                text[-half:])

    # ── dispatch ─────────────────────────────────────────────────
    def dispatch(self, stage_id: str, from_agent: str, to_agent: str,
                 signal: str, payload: str) -> DelegationRecord:
        message_id = ""
        if self.messenger is not None:
            try:
                from core.agent_messenger import MessageType
                msg = self.messenger.send(
                    sender=from_agent, recipient=to_agent,
                    message_type=MessageType.HANDOFF,
                    payload={"signal": signal, "stage": stage_id,
                             "payload_chars": len(payload or "")},
                    topic=f"delegation:{stage_id}")
                message_id = getattr(msg, "message_id", "") or ""
            except Exception:
                message_id = ""

        rec = DelegationRecord(
            stage_id=stage_id, from_agent=from_agent, to_agent=to_agent,
            signal=signal, payload_chars=len(payload or ""),
            message_id=message_id, timestamp=datetime.now().isoformat())
        self.records.append(rec)
        self._persist(rec)
        return rec

    def _persist(self, rec: DelegationRecord):
        try:
            path = os.path.join(self.products_dir, self.project, "delegations.json")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            data = []
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data.append(rec.to_dict())
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass


def read_delegations(project: str, products_dir: str = "products") -> List[Dict]:
    path = os.path.join(products_dir, project, "delegations.json")
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []
