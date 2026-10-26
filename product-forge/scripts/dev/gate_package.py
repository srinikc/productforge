"""One Gate 1/2 package: plain language, Gate 0 impact, review table + recommendation, decision (BI-PF-1486).

`gate_decide` renders and persists this before recording a HIL decision, so the HIL always sees the same package.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "scripts" / "dev")):
    if p not in sys.path:
        sys.path.insert(0, p)

import architect_review as ar  # noqa: E402
import gate0_check as g0  # noqa: E402

OUT = ROOT / "engineering" / "gate-packages"


def render(item_id: str, gate: int) -> str:
    from core import backlog, execution_trail as tr
    item = backlog.get_epic("product_forge", None, item_id) or {}
    brief = item.get("brief") or {}
    mode = "design" if int(gate) == 1 else "diff"
    lines = [f"# Gate {gate} package - {item_id}", f"**{item.get('title')}**", ""]
    if brief.get("problem") or brief.get("what_adds"):
        lines += ["## Plain language", f"**What/why:** {brief.get('problem')} -> {brief.get('what_adds')}"]
        if brief.get("success"):
            lines.append(f"**Success:** {brief.get('success')}")
        lines.append("")
    lines += ["## Gate 0 reconciliation + impact", g0.render(item), ""]
    lines += ["## Current stage", f"**{tr.current_stage(item_id, item.get('status') or '')}**", ""]
    view = ar.gate_view(item_id, mode)
    if view:
        lines += [f"## Gate {1.5 if mode == 'design' else 2.5} findings + architect recommendation",
                  ar.render_gate_view(view, mode), ""]
    else:
        lines += [f"## Gate {1.5 if mode == 'design' else 2.5}", "(no review evidence)", ""]
    if int(gate) == 2:
        lines += ["## AC verification"]
        for a in item.get("ac_verification") or []:
            lines.append(f"- {a.get('ac')}: {a.get('result')} | {'; '.join(a.get('evidence') or [])}")
        if not item.get("ac_verification"):
            lines.append("- not recorded")
        lines += ["", "## Tests"]
        tests = tr.latest_tests(tr.events(item_id))
        for t in tests:
            lines.append(f"- {t.get('command')}: {t.get('result')} "
                         f"({t.get('passed')} passed / {t.get('failed')} failed)")
        if not tests:
            lines.append("- none recorded")
        fr = item.get("final_report") or {}
        lines += ["", "## Final report", f"- persisted: {'yes' if fr else 'no'}",
                  f"- total_time_ms: {fr.get('total_time_ms')}",
                  f"- cost_usd: {(fr.get('usage') or {}).get('cost_usd')}"]
    lines += ["", "## HIL decision", f"- Gate {gate}: PENDING (to be recorded with --hil-confirmed)"]
    return "\n".join(lines)


def persist(item_id: str, gate: int, text: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{item_id}-gate{gate}.json"
    p.write_text(json.dumps({"item": item_id, "gate": gate,
                             "at": datetime.now(timezone.utc).isoformat(), "text": text}, indent=2), encoding="utf-8")
    return p


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--item", required=True)
    ap.add_argument("--gate", type=int, choices=(1, 2), required=True)
    a = ap.parse_args()
    text = render(a.item, a.gate)
    print(text)
    print(f"gate-package: wrote {persist(a.item, a.gate, text)}")
