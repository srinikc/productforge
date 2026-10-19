"""BI-PF-1467 (RCCA): inject review learnings at DESIGN/GROOMING time.

The correction ledger and the review-recurrence report must shape the design *before* Gate 1.5, so the
review verifies instead of first-discovering. This module builds a DESIGN GUARDRAILS block from:
  - the generic design pre-check checklist (config/architect-review.json),
  - the CORRECTION-LEDGER rules, ranked by relevance to the item, and
  - recurring review findings (engineering/learnings/review-findings.json).

Usage:
  python scripts/dev/design_guardrails.py --item <ID>            # print the block (author reads it)
  python scripts/dev/design_guardrails.py --item <ID> --record   # store it on the item evidence (idempotent)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "docs" / "CORRECTION-LEDGER.md"
CONFIG = ROOT / "config" / "architect-review.json"
LEARNINGS = ROOT / "engineering" / "learnings" / "review-findings.json"
if str(ROOT / "scripts" / "dev") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "dev"))
from review_sig import digest as _digest  # noqa: E402

_RULE_RE = re.compile(r"^\|\s*(CL-\d+)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*$")
_TOKEN_RE = re.compile(r"[a-z0-9]{4,}")
_STOP = {"with", "from", "that", "this", "into", "must", "should", "when", "than", "then", "have", "been",
         "will", "only", "also", "each", "they", "their", "does", "your", "over", "under", "more", "less"}


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


def recurring(threshold: int = 2, limit: int = 5) -> list[dict]:
    try:
        d = json.loads(LEARNINGS.read_text(encoding="utf-8"))
    except Exception:
        return []
    rec = [r for r in (d.get("recurring") or []) if int(r.get("count") or 0) >= threshold]
    rec.sort(key=lambda r: (-int(r.get("count") or 0), str(r.get("sig"))))
    return rec[:limit]


def item_text(item: dict, extra: str = "") -> str:
    if not isinstance(item, dict):
        return str(extra or "")
    parts = [extra, item.get("title"), item.get("objective"), item.get("approach"),
             " ".join(item.get("in_scope") or []), " ".join(item.get("acceptance_criteria") or [])]
    return " ".join(str(p) for p in parts if p)


def render(item: dict, item_id: str, *, extra: str = "", limit_rules: int = 6) -> str:
    rules = relevant_rules(item_text(item, extra), ledger_rules(), limit_rules)
    rec = recurring()
    lines = [f"DESIGN GUARDRAILS (apply in the design BEFORE Gate 1.5; item {item_id}; BI-PF-1467)",
             "Answer each checklist item in the design; pre-empt the relevant corrections below.",
             "Checklist:"]
    for i, q in enumerate(checklist(), 1):
        lines.append(f"  {i}. {q}")
    lines.append("Relevant corrections (CORRECTION-LEDGER):")
    lines += [f"  - {r['id']}: {r['rule']}  [enforced by: {r['enforcement']}]" for r in rules] or ["  - (none)"]
    if rec:
        lines.append("Recurring review findings to pre-empt:")
        lines += [f"  - x{r.get('count')} [{r.get('severity')}] {str(r.get('text'))[:160]}" for r in rec]
    return "\n".join(lines)


def _record(item_id: str, block: str) -> bool:
    import backlog_api as ba  # lazy: pulls the API app
    item = ba.get_item(item_id) or {}
    marker = f"Design guardrails applied ({item_id}):"
    ev = list(item.get("evidence") or [])
    if any(str(x).startswith(marker) for x in ev):
        return False
    ev.append(f"{marker} sig:{_digest(block)} ({len(block.splitlines())} lines)")
    ba.set_context(item_id, {"evidence": ev})
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Design-time guardrails (BI-PF-1467)")
    ap.add_argument("--item", required=True)
    ap.add_argument("--record", action="store_true", help="store the applied guardrails on item evidence (idempotent)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    import backlog_api as ba
    item = ba.get_item(a.item) or {}
    block = render(item, a.item)
    if a.json:
        print(json.dumps({"item": a.item, "rules": [r["id"] for r in relevant_rules(item_text(item), ledger_rules())],
                          "recurring": len(recurring()), "block": block}, indent=2))
    else:
        print(block)
    if a.record:
        print("recorded on item evidence" if _record(a.item, block) else "already recorded (idempotent)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
