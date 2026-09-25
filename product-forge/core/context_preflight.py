"""Context preflight — check `instructions + context` against the model window BEFORE the call.

Soft by design:
  * instructions + context > 0.8*window  -> SOFT: compact the ambient CONTEXT (never instructions).
  * instructions ALONE   > 0.8*window    -> HARD: cannot shrink static instructions -> signal fail.
Never fabricates; returns a verdict + the action the caller should take.

Owner: this module (pure function). Wired in agent_runner._build_agent_prompt.
"""
from typing import Dict


def check(instruction_chars: int, context_chars: int, model_window_tokens: int,
          max_input_tokens: int = 0) -> Dict:
    """Return {ok, action, budget_chars, reasons}. action ∈ full|compact_context|hard_fail."""
    window = int(model_window_tokens or 0)
    budget_tokens = min(int(max_input_tokens) if max_input_tokens else window, int(window * 0.8)) \
        if window else (int(max_input_tokens) or 1)
    budget_chars = budget_tokens * 4
    ins_tokens = int(instruction_chars) // 4
    ctx_tokens = int(context_chars) // 4
    total = ins_tokens + ctx_tokens
    reasons = []

    if window and ins_tokens > int(window * 0.8):
        reasons.append(f"instructions alone ({ins_tokens} tok) exceed 80% of window ({window})")
        return {"ok": False, "action": "hard_fail", "budget_chars": budget_chars,
                "reasons": reasons}
    if total <= budget_tokens:
        reasons.append(f"fits ({total} <= {budget_tokens} tokens)")
        return {"ok": True, "action": "full", "budget_chars": budget_chars, "reasons": reasons}
    # over budget but instructions are fine -> compact the context
    reasons.append(f"over budget ({total} > {budget_tokens} tokens); compact CONTEXT")
    return {"ok": True, "action": "compact_context", "budget_chars": budget_chars,
            "reasons": reasons}


def log_verdict(agent_id: str, verdict: Dict) -> None:
    try:
        if verdict.get("action") == "hard_fail":
            print(f"  [Preflight] {agent_id}: HARD FAIL - {'; '.join(verdict.get('reasons') or [])}")
        elif verdict.get("action") == "compact_context":
            print(f"  [Preflight] {agent_id}: compacting context - {'; '.join(verdict.get('reasons') or [])}")
    except Exception:
        pass
