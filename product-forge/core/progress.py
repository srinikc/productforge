#!/usr/bin/env python3
"""E2E pipeline progress banner.

Single concern: render "where are we" at every agent start/end — the phase, the
stage, the agent, the position in the whole E2E pipeline, and what comes next.

Reads (never writes): `pipeline-definition.json` (stages/agents),
`<project>/agents-live.json` (who is running), `<project>/pipeline-state.json`
(stage statuses), `<project>/budget.json`, `<project>/project.json`.

Wired into `core/orchestrator/stage_runner.py` (agent start + end) and usable
standalone:  ``python -m core.progress --project <p>``

Note: the position is measured over the canonical stage order below (the Build
phase expands to the implementation iterations present in this pipeline).
"""
try:
    from core.paths import ROOT as _PF_ROOT
except ImportError:  # executed as a script: seed the repo root on sys.path, then retry
    import os as _pf_os
    import sys as _pf_sys
    _pf_d = _pf_os.path.abspath(__file__)
    for _pf_i in range(3):
        _pf_d = _pf_os.path.dirname(_pf_d)
        if _pf_os.path.isfile(_pf_os.path.join(_pf_d, 'core', 'paths.py')):
            _pf_sys.path.insert(0, _pf_d)
            break
    from core.paths import ROOT as _PF_ROOT

import argparse
import json
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

from core import id_index

# Fallback phase map (used only if the definition can't be read). The banner normally
# DERIVES phases from pipeline-definition.json `phase` metadata so it never drifts.
_FALLBACK_PHASES: List[Tuple[str, List[str]]] = [
    ("Ideation & Discovery", ["0", "0a"]),
    ("Design", ["1", "1a", "1b", "1c", "1d"]),
    ("Architecture", ["2", "3", "3a"]),
    ("Build", ["4-0", "4a", "4a-vqa", "4b", "4b-vqa", "4c", "4c-vqa",
               "4d", "4d-vqa", "4e", "4e-vqa", "4f", "4f-vqa"]),
    ("Verify", ["5", "6", "7"]),
    ("Release", ["8", "9"]),
    ("Deploy", ["10", "10a", "11", "12"]),
]


def _derive_phases() -> List[Tuple[str, List[str]]]:
    """Build (label, stage-ids) per phase from pipeline-definition.json phase metadata."""
    try:
        defn = json.load(open(os.path.join(
            str(_PF_ROOT),
            "pipeline-definition.json"), encoding="utf-8-sig"))
        stages = defn.get("stages") or {}
        groups: "Dict[str, List[str]]" = {}
        for sid, st in stages.items():
            ph = (st or {}).get("phase") or "Unphased"
            groups.setdefault(ph, []).append(sid)
        if not groups:
            return _FALLBACK_PHASES

        def _pnum(ph: str) -> int:
            m = re.match(r"P(\d+)", ph or "")
            return int(m.group(1)) if m else 999
        ordered = sorted(groups.items(), key=lambda kv: _pnum(kv[0]))
        total = len(ordered)
        return [(f"{i}/{total} " + (re.sub(r"^P\d+\s*", "", ph) or ph), sids)
                for i, (ph, sids) in enumerate(ordered, 1)]
    except Exception:
        return _FALLBACK_PHASES


PHASES: List[Tuple[str, List[str]]] = _derive_phases()

ORDER: List[str] = [sid for _n, sids in PHASES for sid in sids]
_STAGE_PHASE = {sid: name for name, sids in PHASES for sid in sids}
GATES = {"1": "AG-scope-change", "2": "AG-architecture", "5": "AG-security-critical",
         "10": "AG-deploy", "11": "AG-deploy"}
_DONE = ("completed", "skipped")

_REPO = str(_PF_ROOT)


def _rj(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _pipeline_def() -> Dict:
    return _rj(os.path.join(_REPO, "pipeline-definition.json"), {})


def stage_name(defn: Dict, sid: str) -> str:
    return (((defn.get("stages") or {}).get(sid) or {}).get("name") or sid)


def stage_agents(defn: Dict, sid: str) -> List[str]:
    stage = (defn.get("stages") or {}).get(sid) or {}
    flow = stage.get("ideal_flow") or []
    return list(flow) if flow else [sid]


def _stage_status(state: Dict, sid: str) -> str:
    st = ((state.get("stages") or {}).get(sid) or {})
    return st.get("status") or ("completed" if sid in (state.get("completed_stages") or []) else "pending")


def snapshot(project_dir: str) -> Dict:
    """Compute the current E2E position for a project directory (read-only)."""
    defn = _pipeline_def()
    state = _rj(os.path.join(project_dir, "pipeline-state.json"), {})
    live = _rj(os.path.join(project_dir, "agents-live.json"), {})
    budget = _rj(os.path.join(project_dir, "budget.json"), {})
    cfg = _rj(os.path.join(project_dir, "project.json"), {})

    running = None
    for key, info in (live or {}).items():
        if isinstance(info, dict) and info.get("status") == "running":
            running = info
            break

    if running:
        sid = str(running.get("stage"))
        agent = running.get("agent_id")
        status = "running"
    else:
        sid, agent = None, None
        for cand in ORDER:
            if _stage_status(state, cand) not in _DONE:
                sid = cand
                break
        if sid is None:
            sid = state.get("current_stage") or ORDER[-1]
        status = _stage_status(state, sid)

    agents = stage_agents(defn, sid)
    if agent is None:
        agent = agents[0] if agents else sid

    si = ORDER.index(sid) + 1 if sid in ORDER else 0
    ai = (agents.index(agent) + 1) if agent in agents else 1

    total_agents = sum(len(stage_agents(defn, s)) for s in ORDER)
    done_agents = 0
    for s in ORDER[: max(0, si - 1)]:
        done_agents += len(stage_agents(defn, s))
    done_agents += max(0, ai - 1)

    # next: next agent in this stage, else first agent of the next stage
    nxt = None
    if ai < len(agents):
        nxt = f"agent {agents[ai]} (this stage)"
    else:
        for cand in ORDER[si:]:
            if _stage_status(state, cand) not in _DONE:
                nxt_agents = stage_agents(defn, cand)
                nxt = f"stage {cand} {stage_name(defn, cand)} -> agent {nxt_agents[0]}"
                break

    return {
        "project": state.get("project") or cfg.get("name") or os.path.basename(project_dir.rstrip("/\\")),
        "phase": _STAGE_PHASE.get(sid, "?"),
        "stage_id": sid,
        "stage_name": stage_name(defn, sid),
        "stage_index": si,
        "stage_total": len(ORDER),
        "agent": agent,
        "agent_index": ai,
        "agent_total_stage": len(agents),
        "agent_index_global": done_agents + 1,
        "agent_total_global": total_agents,
        "status": status,
        "gate": GATES.get(sid, ""),
        "next": nxt or "pipeline complete",
        "tokens_used": (budget.get("state") or {}).get("total_used"),
        "tokens_max": (budget.get("state") or {}).get("total_max"),
        "target": ((cfg.get("deploy") or {}).get("target")) or "",
    }


def render(s: Dict, event: str = "") -> str:
    head = "PIPELINE PROGRESS" + (f" | {event}" if event else "")
    tok = ""
    if s.get("tokens_used") is not None:
        tok = f"   |   tokens {s['tokens_used']:,}"
        if s.get("tokens_max"):
            tok += f" / {s['tokens_max']:,}"
    tgt = f"   |   target {s['target']}" if s.get("target") else ""
    gate = f"   |   GATE {s['gate']}" if s.get("gate") else ""
    lines = [
        "=" * 76,
        f" {head} | {s['project']}",
        f" Phase {s['phase']}   |   Stage {s['stage_index']}/{s['stage_total']} "
        f"({s['stage_id']} {s['stage_name']})   |   "
        f"Agent {s['agent_index']}/{s['agent_total_stage']} ({s['agent']})"
        f"  ~ overall agent {s['agent_index_global']}/{s['agent_total_global']}",
        f" Status: {str(s['status']).upper()}{gate}{tok}{tgt}",
        f" Next:   {s['next']}",
        "=" * 76,
    ]
    return "\n".join(lines)


def agent_banner(project_dir: str, stage_id: str, agent_id: str, status: str) -> str:
    """Banner for an agent start/end at a known stage (no recompute required)."""
    try:
        s = snapshot(project_dir)
        s["stage_id"] = stage_id
        s["stage_name"] = stage_name(_pipeline_def(), stage_id)
        s["phase"] = _STAGE_PHASE.get(stage_id, s.get("phase", "?"))
        if stage_id in ORDER:
            s["stage_index"] = ORDER.index(stage_id) + 1
        s["agent"] = agent_id
        s["status"] = {"running": "running"}.get(status, status)
        return render(s, event="AGENT START" if status == "running" else "AGENT END")
    except Exception:
        return f"[progress] stage {stage_id} | agent {agent_id} | {status}"


def _cli():
    ap = argparse.ArgumentParser(description="Show E2E pipeline position for a project")
    ap.add_argument("--project", required=True)
    ap.add_argument("--products-dir", default="products")
    args = ap.parse_args()
    project_dir = os.path.join(args.products_dir, args.project)
    if not os.path.isdir(project_dir):
        print(f"no such project: {project_dir}")
        sys.exit(1)
    print(render(snapshot(project_dir)))


def next_stage(stage_id: str) -> Optional[str]:
    """The stage after `stage_id` in canonical order (None if last)."""
    try:
        i = ORDER.index(stage_id)
        return ORDER[i + 1] if i + 1 < len(ORDER) else None
    except Exception:
        return None


def artifact_bullets(paths: Optional[List[str]], limit: int = 4) -> List[str]:
    """Content bullets describing what an agent produced (from the artifact itself)."""
    import re as _re
    out: List[str] = []
    for p in list(paths or [])[:3]:
        try:
            t = open(p, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        heads = [h.strip() for h in _re.findall(r"(?m)^#{1,3}\s+(.+)$", t)]
        heads = [h for h in heads if h.lower() not in ("token usage", "output")
                 and not h.lower().startswith("ideation output")]
        if heads:
            out.append(f"{os.path.basename(p)}: {len(heads)} sections - {', '.join(heads[:6])}")
        feats = sorted({int(x) for x in _re.findall(r"\bF-(\d+)\b", t)})
        if feats:
            out.append(f"features defined: {len(feats)} (F-{feats[0]}..F-{feats[-1]})")
        fr = id_index.ids(t, ["FR"])
        nfr = id_index.ids(t, ["NFR"])
        us = id_index.ids(t, ["US"])
        if fr or nfr or us:
            out.append(f"requirements: {len(fr)} FR, {len(nfr)} NFR, {len(us)} US")
        adrs = sorted(id_index.ids(t, ["ADR"]))
        if adrs:
            out.append(f"architecture decisions: {len(adrs)} (ADR-*)")
        risks = len(_re.findall(r"(?im)^\s*[-*+•]?\s*\**\s*risk", t))
        if risks:
            out.append(f"risk items: {risks}")
    return out[:limit]


def artifact_stats(paths: Optional[List[str]]) -> "Tuple[int, float]":
    """Best-effort (tokens, cost) parsed from an artifact's header (for gate summaries)."""
    import re as _re
    for p in list(paths or []):
        try:
            t = open(p, encoding="utf-8", errors="ignore").read()[:2000]
        except Exception:
            continue
        m = _re.search(r"Total Tokens[^0-9]*([\d,]+)", t)
        c = _re.search(r"Cost[^$]*\$([\d.]+)", t)
        tok = int(m.group(1).replace(",", "")) if m else 0
        cost = float(c.group(1)) if c else 0.0
        if tok or cost:
            return tok, cost
    return 0, 0.0


def _stage_decisions(project_dir: str, stage_id: str, agent_id: str) -> List[str]:
    """Human/pipeline decisions recorded for this stage+agent (approval + decision log)."""
    out: List[str] = []
    if not project_dir:
        return out
    ap = os.path.join(project_dir, "approvals", str(stage_id), f"{agent_id}-approval.json")
    try:
        with open(ap, encoding="utf-8") as f:
            a = json.load(f)
        st = str(a.get("status") or "").strip()
        if st:
            note = (a.get("notes") or "").strip()
            out.append(f"approval: {st}" + (f" - {note}" if note else ""))
    except Exception:
        pass
    try:
        with open(os.path.join(project_dir, "pipeline-state.json"), encoding="utf-8") as f:
            stt = json.load(f)
        for d in (stt.get("decision_log") or []):
            txt = json.dumps(d) if isinstance(d, (dict, list)) else str(d)
            if str(stage_id) in txt and agent_id in txt:
                out.append(txt[:160])
    except Exception:
        pass
    return out


def stage_summary(defn: Dict, stage_id: str, agent_id: str, status: str = "",
                  artifacts: Optional[List[str]] = None, tokens: int = 0,
                  cost: float = 0.0, seconds: float = 0.0,
                  project_dir: str = "") -> str:
    """Plain 4-5 bullet summary of what the agent/stage did (+ a Decision: block if any)."""
    import re as _re
    name = stage_name(defn, stage_id)
    arts = list(artifacts or [])
    nxt = next_stage(stage_id)
    bullets: List[str] = []

    # 1) what it did, from the agent role + the artifact headings
    text = ""
    if arts:
        try:
            text = open(arts[0], encoding="utf-8", errors="ignore").read()
        except Exception:
            text = ""
    heads = [h.strip() for h in _re.findall(r"(?m)^#{1,3}\s+(.+)$", text)]
    heads = [h for h in heads if h.lower() not in ("token usage", "output")
             and not h.lower().startswith(("ideation output", "design output",
                                           "product-design-spec output", "discovery output"))]
    role = name
    try:
        role = (defn.get("stages", {}).get(stage_id, {}) or {}).get("name") or name
    except Exception:
        pass
    if heads:
        bullets.append(f"Covered {len(heads)} sections: {', '.join(heads[:6])}.")
    # 2) features
    feats = sorted({int(x) for x in _re.findall(r"\bF-(\d+)\b", text)})
    if feats:
        bullets.append(f"Defined {len(feats)} features (F-{feats[0]}..F-{feats[-1]}).")
    # 3) requirements
    fr = id_index.ids(text, ["FR"]); nfr = id_index.ids(text, ["NFR"])
    us = id_index.ids(text, ["US"])
    if fr or nfr or us:
        bullets.append(f"Specified {len(fr)} functional, {len(nfr)} non-functional, {len(us)} user-story items.")
    # 4) decisions / risks
    adrs = id_index.ids(text, ["ADR"])
    if adrs:
        bullets.append(f"Recorded {len(adrs)} architecture decisions (ADR-*).")
    risks = len(_re.findall(r"(?im)^\s*[-*+]?\s*\**\s*risk", text))
    if risks:
        bullets.append(f"Captured {risks} risk item(s).")
    # 5) what it produced + next
    if arts:
        bullets.append("Produced " + ", ".join(os.path.basename(a) for a in arts) + ".")
    if nxt:
        agents = ", ".join(stage_agents(defn, nxt)) or "-"
        bullets.append(f"Next: stage {nxt} ({stage_name(defn, nxt)}) -> {agents}.")
    if not bullets:
        bullets = [f"{agent_id} ran in stage {stage_id} ({status or 'completed'})."]
    lines = [f"  - {b}" for b in bullets[:5]]
    dec = _stage_decisions(project_dir, stage_id, agent_id)
    if dec:
        lines.append("  Decision:")
        for d in dec[:3]:
            lines.append(f"    - {d}")
    return "\n".join(lines)


if __name__ == "__main__":
    _cli()
