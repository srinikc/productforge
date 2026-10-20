"""BI-PF-1467/BI-PF-1468: review learnings applied at DESIGN/GROOMING time.

Single owner for the DESIGN GUARDRAILS block: the generic checklist, the CORRECTION-LEDGER rules ranked by
relevance to the item, and the recurring review findings. Grooming injects this block into its prompts and
records an idempotent evidence marker on the item, so the design pre-empts known review classes instead of
Gate 1.5 first-discovering them. ``scripts/dev/design_guardrails.py`` is the CLI/author-facing view.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from core.paths import ROOT

LEDGER = ROOT / "docs" / "CORRECTION-LEDGER.md"
CONFIG = ROOT / "config" / "architect-review.json"
LEARNINGS = ROOT / "engineering" / "learnings" / "review-findings.json"

_RULE_RE = re.compile(r"^\|\s*(CL-\d+)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*$")
_TOKEN_RE = re.compile(r"[a-z0-9]{4,}")
_STOP = {"with", "from", "that", "this", "into", "must", "should", "when", "than", "then", "have", "been",
         "will", "only", "also", "each", "they", "their", "does", "your", "over", "under", "more", "less"}


def block_digest(text: str) -> str:
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()[:16]


def checklist() -> list[str]:
    try:
        return [str(q) for q in (json.loads(CONFIG.read_text(encoding="utf-8")).get("design_checklist") or [])
                if str(q).strip()]
    except Exception:
        return []


def ledger_rules(path: Path | None = None) -> list[dict]:
    p = path or LEDGER
    out = []
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            m = _RULE_RE.match(line)
            if m:
                out.append({"id": m.group(1), "rule": m.group(2).replace("**", "").strip(),
                            "enforcement": m.group(3).strip()})
    except Exception:
        pass
    return out


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(str(text or "").lower()) if t not in _STOP}


def relevant_rules(item_text: str, rules: list[dict], limit: int = 6) -> list[dict]:
    """Rank ledger rules by token overlap with the item; stable by ledger order on ties."""
    toks = _tokens(item_text)
    scored = []
    for i, r in enumerate(rules):
        score = len(toks & _tokens(r["rule"] + " " + r["enforcement"]))
        scored.append((score, i, r))
    scored.sort(key=lambda x: (-x[0], x[1]))
    picked = [r for s, _i, r in scored if s > 0][:limit]
    return picked or rules[:limit]


def recurring(threshold: int = 2, limit: int = 5, stage: str = "") -> list[dict]:
    """Recurring findings; ``stage`` filters by review mode (``design`` = 1.5, ``diff`` = 2.5)."""
    try:
        d = json.loads(LEARNINGS.read_text(encoding="utf-8"))
    except Exception:
        return []
    rec = [r for r in (d.get("recurring") or []) if int(r.get("count") or 0) >= threshold]
    if stage:
        rec = [r for r in rec
               if not r.get("modes") or str(stage) in {str(m) for m in (r.get("modes") or [])}]
    rec.sort(key=lambda r: (-int(r.get("count") or 0), str(r.get("sig"))))
    return rec[:limit]


def item_text(item: dict, extra: str = "") -> str:
    if not isinstance(item, dict):
        return str(extra or "")
    parts = [extra, item.get("title"), item.get("body"), item.get("objective"), item.get("approach"),
             " ".join(item.get("in_scope") or []), " ".join(item.get("acceptance_criteria") or [])]
    return " ".join(str(p) for p in parts if p)


def render(item: dict, item_id: str, *, extra: str = "", limit_rules: int = 6, stage: str = "") -> str:
    rules = relevant_rules(item_text(item, extra), ledger_rules(), limit_rules)
    rec = recurring(stage=stage)
    where = {"design": "Gate 1.5 design review", "diff": "Gate 2.5 delivery review"}.get(stage, "review")
    if stage == "diff":
        head = [f"CODING GUARDRAILS (apply while implementing; item {item_id})",
                "Address each relevant correction in the implementation and tests; do not repeat these findings."]
    else:
        head = [f"DESIGN GUARDRAILS (apply in the design BEFORE Gate 1.5; item {item_id})",
                "Answer each checklist item in the design; pre-empt the relevant corrections below."]
    lines = head + ["Checklist:"]
    for i, q in enumerate(checklist(), 1):
        lines.append(f"  {i}. {q}")
    lines.append("Relevant corrections (CORRECTION-LEDGER):")
    lines += [f"  - {r['id']}: {r['rule']}  [enforced by: {r['enforcement']}]" for r in rules] or ["  - (none)"]
    if rec:
        lines.append(f"Recurring findings from the {where} to pre-empt:")
        lines += [f"  - x{r.get('count')} [{r.get('severity')}] {str(r.get('text'))[:160]}" for r in rec]
    return "\n".join(lines)


def marker(item_id: str, kind: str = "design") -> str:
    if kind == "implementation":
        return f"Implementation guardrails applied ({item_id}):"
    return f"Design guardrails applied ({item_id}):"


def record(scope: str, project: str | None, item_id: str, *, item: dict | None = None,
           block: str | None = None, kind: str = "design") -> bool:
    """Append the applied-guardrails marker to the item evidence (idempotent). Returns True if written."""
    from core import backlog
    it = item if isinstance(item, dict) and item else (backlog.get_epic(scope, project, item_id) or {})
    ev = list(it.get("evidence") or [])
    m = marker(item_id, kind)
    if any(str(x).startswith(m) for x in ev):
        return False
    stage = "diff" if kind == "implementation" else "design"
    block = block or render(it, item_id, stage=stage)
    ev.append(f"{m} sig:{block_digest(block)} ({len(block.splitlines())} lines)")
    backlog.update(scope, project, item_id, evidence=ev)
    return True
