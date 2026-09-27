"""Brief sufficiency — GENERIC, config-driven, LLM-validated. No hardcoded thresholds.

Policy lives in config/agent-requirements.json -> "brief_check":
    mode:       "llm" (default) — validate every brief with a model; anything else
                disables model validation (then we simply cannot judge and we do NOT
                fabricate a verdict).
    on_unclear: "ask" (default) | "block" | "assume" — caller behaviour when the
                brief is judged unclear and no clarification arrives.

There are NO word counts or forbidden-word lists here — the only unconditional rule
is "empty is empty". Everything else is a model judgement (generic language skill),
so placeholders/gibberish/questions/instructions are caught without a hardcoded dict.
"""
import json
import os
import re
from typing import Dict, Optional

_CFG_REL = ("config", "agent-requirements.json")


def _cfg() -> Dict:
    try:
        from core.paths import ROOT
        p = os.path.join(str(ROOT), *_CFG_REL)
        with open(p, "r", encoding="utf-8-sig") as f:
            return ((json.load(f) or {}).get("brief_check") or {})
    except Exception:
        return {}


def policy() -> Dict:
    c = _cfg()
    return {"mode": str(c.get("mode", "llm")).lower(),
            "on_unclear": str(c.get("on_unclear", "ask")).lower()}


def assess(idea: str, llm=None) -> Dict:
    """Return {ok, source, reason, question}. Generic; llm optional (mode=llm)."""
    t = (idea or "").strip()
    if not t:
        return {"ok": False, "source": "empty", "reason": "empty brief",
                "question": "What product do you want to build? Describe the problem, "
                            "the target users, and 2-3 key features."}
    pol = policy()
    if pol["mode"] == "llm" and llm is not None:
        v = _llm_check(llm, t)
        if v is None:
            # Validator unavailable -> do NOT invent a verdict; let the caller decide.
            return {"ok": True, "source": "no-validator",
                    "reason": "brief validator unavailable", "question": ""}
        if not bool(v.get("usable", True)):
            return {"ok": False, "source": "llm", "reason": "model judged brief unusable",
                    "question": v.get("question") or
                    "Please describe the product: what it does, for whom, and its key features."}
        return {"ok": True, "source": "llm", "reason": "model validated brief", "question": ""}
    return {"ok": True, "source": "no-validator",
            "reason": "model validation disabled", "question": ""}


def _llm_check(llm, idea: str) -> Optional[Dict]:
    prompt = (
        "You validate product briefs. Decide whether the text below is a usable brief "
        "to build a product from. Judge language and intent only — there is no word list. "
        "Reply with ONLY compact JSON: "
        "{\"usable\": true|false, \"question\": \"<one clarifying question if not usable>\"}. "
        "Mark usable=false when it is a placeholder, a single word, gibberish, a question, "
        "an instruction to someone else, or otherwise does not describe something to build. "
        "If unsure, mark usable=false and ASK.\n\nBRIEF:\n" + idea)
    try:
        content, _ = llm._call_llm(prompt, "brief-check", "0")
    except Exception:
        return None
    try:
        m = re.search(r"\{.*\}", content or "", re.S)
        return json.loads(m.group(0)) if m else None
    except Exception:
        return None


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Brief sufficiency (config-driven, LLM)")
    ap.add_argument("idea", nargs="?", default="")
    a = ap.parse_args()
    print(json.dumps({"policy": policy(), "verdict": assess(a.idea)}, indent=2,
                     ensure_ascii=False))
