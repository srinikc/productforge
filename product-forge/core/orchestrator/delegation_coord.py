"""
Delegation coordinator (extracted from pipeline_executor - 1A.11).

Thin orchestration glue over core/delegation:
  - builds the router/budget/messenger from the pipeline definition
  - derives delegation signals from an agent outcome
  - dispatches capped delegations and records them

`execute_fn`/`log_fn` are injected by the executor so this stays decoupled
from executor state.
"""
import os
from typing import Callable, Dict, List, Optional

from core.delegation import DelegationRouter, DelegationBudget


class DelegationCoordinator:
    def __init__(self, products_dir: str, project: str,
                 records: Optional[List[Dict]] = None):
        self.products_dir = products_dir
        self.project = project
        self.enabled = False
        self.router: Optional[DelegationRouter] = None
        self.records: List[Dict] = records if records is not None else []

    def init(self, pipeline_def: Dict, enabled: bool) -> Optional[DelegationRouter]:
        """(Re)build the delegation router from the loaded pipeline definition."""
        self.enabled = bool(enabled)
        try:
            budget = DelegationBudget(
                max_invocations_per_stage=int(os.getenv("DELEGATION_MAX_PER_STAGE", "2")),
                max_total_invocations=int(os.getenv("DELEGATION_MAX_TOTAL", "8")),
                max_payload_chars=int(os.getenv("DELEGATION_MAX_PAYLOAD_CHARS", "4000")),
            )
            messenger = None
            try:
                from core.agent_messenger import AgentMessenger
                messenger = AgentMessenger(self.products_dir, self.project)
            except Exception:
                messenger = None
            self.router = DelegationRouter(
                pipeline_def, project=self.project,
                products_dir=self.products_dir, budget=budget, messenger=messenger)
        except Exception:
            self.router = None
        return self.router

    @staticmethod
    def signals(execution) -> List[str]:
        """Candidate delegation signals derived from an agent's outcome."""
        if execution.status in ("completed", "skipped"):
            return []
        return ["fix", "code_issue", "logic_issue", "api_issue", "db_issue",
                "ui_issue", "issues_found", "major_change_needed", "build_needed"]

    def maybe_delegate(self, stage_id: str, from_agent: str, execution,
                       execute_fn: Callable, log_fn: Optional[Callable] = None):
        """Orchestrator-routed delegation with capped payload + message budget."""
        if not self.enabled or not self.router:
            return
        signals = self.signals(execution)
        if not signals:
            return
        target = self.router.resolve(stage_id, from_agent, signals)
        if not target or target == from_agent:
            return
        if not self.router.budget.can_invoke(stage_id):
            print(f"  [DELEGATION] budget exhausted; skipping {from_agent} -> {target}")
            return
        payload = ""
        try:
            if execution.artifacts:
                with open(execution.artifacts[-1], 'r', encoding='utf-8') as f:
                    payload = self.router.cap_payload(f.read())
        except Exception:
            pass
        # BI-0104: pass a pre-built context bundle + fingerprint so the sub-agent
        # does NOT re-assemble context. Bundle = {signal, payload, artifact refs, fingerprint}.
        bundle = {}
        try:
            import hashlib as _h
            fp = _h.sha256((payload or "").encode("utf-8")).hexdigest()[:16]
            bundle = {"stage_id": stage_id, "from_agent": from_agent, "target": target,
                      "signal": signals[0], "payload": payload,
                      "artifacts": list(getattr(execution, "artifacts", []) or []),
                      "fingerprint": fp}
        except Exception:
            bundle = {"payload": payload, "signal": signals[0]}
        rec = self.router.dispatch(stage_id, from_agent, target, signals[0], payload)
        print(f"  [DELEGATION] {from_agent} -> {target} (signal={signals[0]}, "
              f"payload={rec.payload_chars} chars, bundle fp={bundle.get('fingerprint', '-')})")
        try:
            delegated = execute_fn(target, stage_id,
                                   f"Delegated from {from_agent}: {signals[0]}",
                                   context_bundle=bundle)
            rec.status = delegated.status
            rec.tokens = delegated.total_tokens
            rec.cost = delegated.cost
        except TypeError:
            # execute_fn does not accept a bundle yet -> fall back to the plain call
            try:
                delegated = execute_fn(target, stage_id, f"Delegated from {from_agent}: {signals[0]}")
                rec.status = delegated.status
                rec.tokens = delegated.total_tokens
                rec.cost = delegated.cost
            except Exception as e:
                print(f"[Delegation] failed: {e}")
        except Exception as e:
            print(f"[Delegation] failed: {e}")
        self.router.budget.record(stage_id)
        self.records.append(rec.to_dict())
        if log_fn:
            log_fn("delegation", f"{from_agent}->{target}@{stage_id}", signals[0])
