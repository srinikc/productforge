"""360-degree discovery panel — per-agent clarifying questions + recommendations.

Single concern: turn the raw project idea into a **panel** of clarifying questions,
one group per major pipeline agent (each lead covering its own sub-agents), where
every question carries the agent's *recommended* answer. The human accepts a
recommendation as-is or overrides it with their own clarification. The accepted
answers become the crisper brief that downstream stages consume.

Owner store (single writer = this module):
  ``products/<project>/discovery-panel.json``  — kind=intake-raw, scope=project

Design notes:
- The LLM is injected as ``llm_call(prompt, agent_id) -> str`` so this module has
  no dependency on the executor and is trivially testable.
- Offline/no-LLM safe: if generation fails for an agent, that agent falls back to
  the curated perspective questions so stage 0a never breaks.
- No import-time side effects.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Callable, Dict, List, Optional

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(REPO_ROOT, "config", "discovery-panel-settings.json")
HIERARCHY_PATH = os.path.join(REPO_ROOT, "config", "agent-hierarchy.json")
AGENTS_DIR = os.path.join(REPO_ROOT, "agents")

PANEL_FILENAME = "discovery-panel.json"

# The major (lead) agents — every one the pipeline can field before/through build.
DEFAULT_AGENTS: List[str] = [
    "product-analyzer", "researcher", "analyst", "strategist",
    "ux-ia", "design", "design_critic", "product-design-spec",
    "architect", "security", "implement", "code-review", "validate",
    "devops", "document", "package", "orchestrator", "guardian", "finops",
]

DEFAULTS: Dict = {
    "agents": DEFAULT_AGENTS,
    "include_sub_agents": True,
    "max_questions_per_agent": 3,
    # Live-only: questions must come from the agent's LLM call. The curated
    # perspective set is used ONLY in explicit offline mode (llm_call is None).
    "live_questions_only": True,
}

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _rj(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _wj(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def load_config(products_dir: str = "products", project: Optional[str] = None) -> Dict:
    """Panel settings: global config (`config/discovery-panel-settings.json`) > defaults."""
    cfg = dict(DEFAULTS)
    global_cfg = _rj(CONFIG_PATH, {}) or {}
    if isinstance(global_cfg, dict):
        cfg.update({k: v for k, v in global_cfg.items() if v is not None})
    try:
        cfg["max_questions_per_agent"] = max(1, int(cfg.get("max_questions_per_agent", 3)))
    except Exception:
        cfg["max_questions_per_agent"] = 3
    agents = cfg.get("agents") or DEFAULT_AGENTS
    if not isinstance(agents, list) or not agents:
        agents = list(DEFAULT_AGENTS)
    cfg["agents"] = [str(a) for a in agents]
    return cfg


def _hierarchy() -> Dict[str, List[str]]:
    data = _rj(HIERARCHY_PATH, {}) or {}
    parents = data.get("parents") or {}
    return {k: list(v or []) for k, v in parents.items() if isinstance(v, list)}


def _agent_spec(agent_id: str) -> Dict:
    return _rj(os.path.join(AGENTS_DIR, f"{agent_id}.agent.json"), {}) or {}


def sub_agents_of(agent_id: str) -> List[str]:
    """Direct sub-agents from the hierarchy config, merged with the agent spec."""
    subs: List[str] = []
    for sid in _hierarchy().get(agent_id, []):
        if sid not in subs:
            subs.append(sid)
    for sid in (_agent_spec(agent_id).get("sub_agents") or []):
        if sid not in subs:
            subs.append(sid)
    return subs


def agent_brief(agent_id: str) -> str:
    """One-line role description for an agent (from its card, else its id)."""
    spec = _agent_spec(agent_id)
    name = spec.get("name") or agent_id
    desc = (spec.get("description") or "").strip()
    instr = (spec.get("instructions") or "").strip().splitlines()
    if desc:
        return f"{name}: {desc}"
    if instr:
        return f"{name}: {instr[0]}"
    return name


def _strip_fences(text: str) -> str:
    m = _FENCE_RE.search(text or "")
    return (m.group(1) if m else (text or "")).strip()


def _parse_questions(text: str, cap: int) -> List[Dict[str, str]]:
    """Extract [{'question','recommendation'}] from a model reply (tolerant)."""
    raw = _strip_fences(text)
    out: List[Dict[str, str]] = []

    def _take(obj) -> None:
        items = obj.get("questions") if isinstance(obj, dict) else obj
        if not isinstance(items, list):
            return
        for it in items:
            if not isinstance(it, dict):
                continue
            q = str(it.get("question") or it.get("q") or "").strip()
            if not q:
                continue
            rec = str(it.get("recommendation") or it.get("recommended")
                      or it.get("recommended_answer") or it.get("answer") or "").strip()
            out.append({"question": q, "recommendation": rec})

    try:
        _take(json.loads(raw))
    except Exception:
        # Fallback: scan for a JSON array/object inside the text.
        for pat in (r"\[.*\]", r"\{.*\}"):
            m = re.search(pat, raw, re.DOTALL)
            if not m:
                continue
            try:
                _take(json.loads(m.group(0)))
                break
            except Exception:
                continue
    # Last resort: "Q: ..." / "- ..." lines.
    if not out:
        for line in raw.splitlines():
            s = line.strip().lstrip("-*0123456789. ").strip()
            if len(s) > 15 and ("?" in s):
                out.append({"question": s, "recommendation": ""})
    return out[:cap]


def _prompt_for(agent_id: str, idea: str, ideation_md: str, subs: List[str], cap: int,
                already_asked: Optional[List[str]] = None) -> str:
    sub_line = ""
    if subs:
        sub_line = ("Your sub-agents, whose concerns you must also represent: "
                    + ", ".join(subs) + ".\n")
    ask_block = ""
    if already_asked:
        lines = "\n".join(f"- {q}" for q in already_asked[:80] if q)
        ask_block = ("\nQuestions ALREADY asked by other agents — do NOT ask these or any close "
                     "rephrasing; only ask something genuinely NEW for your role:\n" + lines + "\n")
    return (
        "You are running 360-degree product discovery before any build work starts.\n"
        f"Agent role — {agent_brief(agent_id)}.\n{sub_line}"
        + ask_block +
        "Read the idea and the ideation output, then ask the FEW clarifying questions that "
        "would most change YOUR downstream work if answered. For each question, also state "
        "the answer you would recommend (your best guess from the material) so the human can "
        "simply accept it.\n\n"
        f"Return ONLY JSON: {{\"questions\":[{{\"question\":\"...\",\"recommendation\":\"...\"}}]}}\n"
        f"At most {cap} question(s). No prose outside the JSON.\n\n"
        f"=== IDEA ===\n{idea.strip()[:6000]}\n\n"
        f"=== IDEATION OUTPUT ===\n{(ideation_md or '').strip()[:6000]}\n"
    )


def _fallback_questions(agent_id: str, cap: int) -> List[Dict[str, str]]:
    """Offline fallback: curated perspective questions relevant to this role."""
    try:
        from core.discovery_engine import DISCOVERY_AGENTS
    except Exception:
        return []
    perspective = {
        "product-analyzer": "product_analyst", "researcher": "product_analyst",
        "analyst": "business_analyst", "strategist": "business_analyst",
        "finops": "business_analyst", "ux-ia": "ux_researcher",
        "design": "ux_researcher", "design_critic": "ux_researcher",
        "product-design-spec": "ux_researcher",
    }.get(agent_id, "business_analyst")
    cfg = DISCOVERY_AGENTS.get(perspective, {})
    return [{"question": q, "recommendation": ""} for q in (cfg.get("questions") or [])[:cap]]


def build_panel(idea: str, project: str, ideation_md: str = "",
                llm_call: Optional[Callable[[str, str], str]] = None,
                config: Optional[Dict] = None,
                already_asked: Optional[List[str]] = None) -> Dict:
    """Build the panel: one question group per configured agent.

    ``llm_call(prompt, agent_id) -> str`` — injected; when ``None`` or failing, the
    agent falls back to curated questions.
    """
    cfg = config or load_config(project=project)
    cap = int(cfg.get("max_questions_per_agent", 3))
    include_subs = bool(cfg.get("include_sub_agents", True))

    live_only = bool(cfg.get("live_questions_only", True))
    groups: List[Dict] = []
    skipped: List[str] = []
    asked: List[str] = list(already_asked or [])
    for agent_id in cfg.get("agents", DEFAULT_AGENTS):
        subs = sub_agents_of(agent_id) if include_subs else []
        qs: List[Dict[str, str]] = []
        if llm_call is not None:
            # Live-only: the agent's own model must produce the questions. Retry once.
            for _attempt in range(2):
                try:
                    reply = llm_call(_prompt_for(agent_id, idea, ideation_md, subs, cap,
                                                 already_asked=asked), agent_id)
                    qs = _parse_questions(reply or "", cap)
                except Exception:
                    qs = []
                if qs:
                    break
        # Curated fallback is allowed ONLY in explicit offline mode (no llm_call).
        if not qs and (llm_call is None or not live_only):
            qs = _fallback_questions(agent_id, cap)
        if not qs:
            skipped.append(agent_id)
            continue
        qs = [{"id": f"{agent_id}:{i + 1}", "question": q["question"],
               "recommendation": q.get("recommendation", ""), "answer": "",
               "accepted": False, "source_agent": agent_id}
              for i, q in enumerate(qs)]
        if not qs:
            continue
        asked.extend([q.get("question") for q in qs if q.get("question")])
        groups.append({"agent_id": agent_id, "name": agent_brief(agent_id),
                       "sub_agents": subs, "questions": qs})

    total = sum(len(g["questions"]) for g in groups)
    return {
        "project": project,
        "idea": idea,
        "generated_at": datetime.now().isoformat(),
        "config": {"max_questions_per_agent": cap, "include_sub_agents": include_subs,
                   "live_questions_only": live_only},
        "agents": groups,
        "skipped_agents": skipped,
        "totals": {"agents": len(groups), "questions": total, "answered": 0},
    }


def all_questions(panel: Dict) -> List[Dict]:
    return [q for g in (panel.get("agents") or []) for q in (g.get("questions") or [])]


def recount(panel: Dict) -> Dict:
    """Recompute ``totals`` from the CURRENT agents/questions.

    Needed because a re-run EXTENDS the panel with new agents (build_panel) but
    the stored totals were never refreshed, so they drifted (e.g. 19/57 stored vs
    30/90 actual). Deterministic; safe to call before every save.
    """
    qs = all_questions(panel)
    answered = sum(1 for q in qs if (q.get("answer") or "").strip() or q.get("accepted"))
    unanswered = sum(1 for q in qs if q.get("unanswered"))
    panel.setdefault("totals", {})
    panel["totals"]["agents"] = sum(1 for g in (panel.get("agents") or [])
                                    if (g.get("questions") or []))
    panel["totals"]["questions"] = len(qs)
    panel["totals"]["answered"] = answered
    panel["totals"]["unanswered"] = unanswered
    return panel


def record_answers(panel: Dict, answers: Dict[str, str]) -> Dict:
    """Write answers into the panel.

    BI-0048: an EMPTY answer must NOT be silently treated as 'accept the
    recommendation'. Only an EXPLICIT acceptance (the owner typed the sentinel
    'accept'/'accept-recommendation', or explicitly accepted) marks `accepted`.
    An empty/timed-out answer is recorded as `unanswered` so the owner can verify
    each one instead of it being auto-accepted.
    """
    ACCEPT = {"accept", "accepted", "accept-recommendation", "yes", "ok"}
    for q in all_questions(panel):
        qid = q.get("id")
        if qid not in answers:
            continue
        val = answers.get(qid)
        rec = q.get("recommendation") or ""
        if val in (None, ""):
            # No explicit decision -> record as unanswered, do NOT accept silently.
            q["answer"] = ""
            q["accepted"] = False
            q["unanswered"] = True
            q["needs_verification"] = True
        elif str(val).strip().lower() in ACCEPT and rec:
            q["answer"] = rec
            q["accepted"] = True
            q.pop("unanswered", None)
        else:
            q["answer"] = str(val)
            q["accepted"] = str(val).strip() == rec.strip()
            q.pop("unanswered", None)
    qs = all_questions(panel)
    answered = sum(1 for q in qs if (q.get("answer") or "").strip() or q.get("accepted"))
    unanswered = sum(1 for q in qs if q.get("unanswered"))
    panel.setdefault("totals", {})["answered"] = answered
    panel["totals"]["unanswered"] = unanswered
    panel["answered_at"] = datetime.now().isoformat()
    return panel


def panel_path(project_dir: str) -> str:
    return os.path.join(project_dir, PANEL_FILENAME)


def save_panel(project_dir: str, panel: Dict) -> str:
    path = panel_path(project_dir)
    _wj(path, panel)
    return path


def load_panel(project_dir: str) -> Optional[Dict]:
    data = _rj(panel_path(project_dir), None)
    return data if isinstance(data, dict) else None


# Panel agent id -> discovery_engine synthesis bucket (product_analyst /
# business_analyst / ux_researcher). The synthesizers bucket answers by these ids,
# so answers must be stamped with the bucket, not the panel agent (BI-0080).
_SYNTH_AGENT = {
    "product-analyzer": "product_analyst", "researcher": "product_analyst",
    "analyst": "product_analyst", "strategist": "business_analyst",
    "finops": "business_analyst",
    "ux-ia": "ux_researcher", "design": "ux_researcher",
    "design_critic": "ux_researcher", "product-design-spec": "ux_researcher",
}


def synthesis_agent(panel_agent: str) -> str:
    """Map a panel agent id to its discovery synthesis perspective bucket."""
    return _SYNTH_AGENT.get((panel_agent or "").strip().lower(), "business_analyst")


def to_discovery_answers(panel: Dict):
    """Panel -> list[DiscoveryAnswer] for core.discovery_engine synthesis.

    Stamps each answer with the SYNTHESIS bucket (not the panel agent) so the
    domain/stakeholder/persona synthesizers actually pick them up (BI-0080).
    """
    from core.discovery_engine import DiscoveryAnswer
    out = []
    for q in all_questions(panel):
        ans = (q.get("answer") or q.get("recommendation") or "").strip()
        if ans:
            out.append(DiscoveryAnswer(question=q.get("question", ""), answer=ans,
                                       agent=synthesis_agent(q.get("source_agent", ""))))
    return out


def needs_followup(panel: Dict) -> List[Dict]:
    """BI-0037: questions whose answer is vague or overrides the recommendation.

    A question needs a round-2 follow-up when:
      * it is unanswered / needs_verification, OR
      * the owner OVERRODE the recommendation (answer set, accepted False, differs from rec), OR
      * the answer is 'vague' (too short / generic filler).
    """
    VAGUE = {"n/a", "na", "none", "-", "?", "idk", "tbd", "not sure", "maybe", "yes", "no"}
    out: List[Dict] = []
    for q in all_questions(panel):
        ans = (q.get("answer") or "").strip()
        rec = (q.get("recommendation") or "").strip()
        vague = (ans.lower() in VAGUE) or (0 < len(ans) < 12)
        overridden = bool(ans) and not q.get("accepted") and ans != rec
        if q.get("unanswered") or q.get("needs_verification") or overridden or vague:
            out.append({"id": q.get("id"), "question": q.get("question"),
                        "answer": ans, "reason": ("unanswered" if q.get("unanswered")
                                                  else "overridden" if overridden else "vague")})
    return out


def build_round2(panel: Dict, llm_call=None,
                 config: Optional[Dict] = None) -> Dict:
    """BI-0037: generate a round-2 follow-up question for each vague/overridden answer.

    Follow-ups are appended to the SAME panel (grouped per agent), each carrying
    `round: 2` and `follows: <original question id>`. Falls back to a sharpened
    template question when no LLM is available.
    """
    cfg = config or {}
    todo = needs_followup(panel)
    if not todo:
        panel.setdefault("round2", {})["status"] = "not_needed"
        return panel
    by_agent: Dict[str, List[Dict]] = {}
    for item in todo:
        agent = (item["id"] or "").split(":")[0] or "general"
        q2 = None
        if llm_call is not None:
            try:
                prompt = ("You are following up on a vague/overridden discovery answer.\n"
                          f"Question: {item['question']}\nOwner answer: {item['answer']!r}\n"
                          f"Reason it needs follow-up: {item['reason']}\n"
                          "Ask ONE sharper, specific follow-up question that closes the gap, "
                          "and state your recommended answer. Return JSON "
                          '{\"questions\":[{\"question\":\"...\",\"recommendation\":\"...\"}]}.')
                reply = llm_call(prompt, agent)
                parsed = _parse_questions(reply or "", 1)
                if parsed:
                    q2 = parsed[0]
            except Exception:
                q2 = None
        if not q2:
            q2 = {"question": (f"You answered {item['answer']!r} to: {item['question']} "
                               f"({item['reason']}). Can you be more specific?"),
                  "recommendation": ""}
        q2["id"] = f"{agent}:r2-{len(by_agent.get(agent, [])) + 1}"
        q2["round"] = 2
        q2["follows"] = item["id"]
        by_agent.setdefault(agent, []).append(q2)

    existing = {g.get("id"): g for g in (panel.get("agents") or [])}
    for agent, qs in by_agent.items():
        g = existing.get(agent)
        if g is None:
            g = {"id": agent, "title": agent, "questions": []}
            panel.setdefault("agents", []).append(g)
        g.setdefault("questions", []).extend(qs)
    panel.setdefault("round2", {})
    panel["round2"] = {"status": "generated", "followups": sum(len(v) for v in by_agent.values()),
                       "at": datetime.now().isoformat()}
    t = panel.setdefault("totals", {})
    allq = all_questions(panel)
    t["questions"] = len(allq)
    t["round2"] = t.get("round2", 0) + panel["round2"]["followups"]
    return panel


def reanalyze_recommendations(panel: Dict, idea: str, ideation_md: str = "", llm_call=None) -> Dict:
    """Re-analyze the panel ONCE and refresh each question's recommendation from the
    current idea/context. The new recommendation may be the SAME or DIFFERENT from the
    previous answer. Marks `recommendation_changed` when it differs from the old rec.
    """
    if llm_call is None:
        return panel
    qs = all_questions(panel)
    if not qs:
        return panel
    listing = "\n".join(
        f"{i + 1}. [{q.get('id')}] {q.get('question')}  (previous answer: {(q.get('answer') or '(none)')})"
        for i, q in enumerate(qs[:120]))
    prompt = ("You are re-analyzing 360-degree discovery questions for the CURRENT product idea.\n"
              "For EACH question give the best recommendation NOW (it may be the same as, or DIFFERENT "
              "from, the previous answer). Return JSON only: "
              '{"answers":[{"id":"<id>","recommendation":"..."}]}.\n\n'
              f"IDEA:\n{idea[:3000]}\n\nCONTEXT:\n{(ideation_md or '')[:2000]}\n\nQUESTIONS:\n{listing}")
    try:
        reply = llm_call(prompt, "discovery")
        raw = _strip_fences(reply or "")
        start, end = raw.find("{"), raw.rfind("}")
        data = json.loads(raw[start:end + 1]) if start >= 0 and end > start else {}
        recs = {a.get("id"): (a.get("recommendation") or "").strip()
                for a in (data.get("answers") or []) if a.get("id")}
    except Exception:
        recs = {}
    changed = 0
    for q in qs:
        new = recs.get(q.get("id"))
        if new:
            old = (q.get("recommendation") or "").strip()
            q["recommendation"] = new
            q["recommendation_changed"] = (old != new)
            if q["recommendation_changed"]:
                changed += 1
    panel.setdefault("reanalysis", {})["changed"] = changed
    return panel



def dedupe_questions(panel: Dict, threshold: float = 0.7) -> Dict:
    """Merge ONLY true near-duplicates (very high token overlap) across agents.

    Deliberately CONSERVATIVE: differently-worded questions are NOT merged (the
    generator already avoids repeating what earlier agents asked). Later duplicates
    are marked skip=True + duplicate_of so _ask_panel does not ask them again.
    """
    import re as _re

    def _toks(s):
        return {w for w in _re.findall(r"[a-z0-9]+", (s or "").lower()) if len(w) > 3}

    seen = []
    merged = 0
    for g in panel.get("agents", []):
        for q in (g.get("questions") or []):
            if q.get("round", 1) != 1:
                continue
            tx = _toks(q.get("question"))
            dup = None
            for (sid, stx) in seen:
                j = (len(tx & stx) / max(1, len(tx | stx))) if (tx and stx) else 0.0
                if j >= threshold:
                    dup = sid
                    break
            if dup:
                q["skip"] = True
                q["duplicate_of"] = dup
                merged += 1
            else:
                seen.append((q.get("id"), tx))
    panel.setdefault("dedupe", {})["merged"] = merged
    return panel


# ── canonical stage artifact + one-shot review file (BI-0144 / BI-0141) ──

def _askable(panel: Dict, only_round: int = 0) -> List[Dict]:
    """Questions that are asked/answered: skip deduped ones, honour the round filter."""
    out: List[Dict] = []
    for q in all_questions(panel):
        if q.get("skip"):
            continue
        if only_round and int(q.get("round", 1)) != only_round:
            continue
        out.append(q)
    return out


def render_output(panel: Dict, refined_md: str = "") -> str:
    """Render the 360-degree panel to the canonical ``discovery-output.md`` content.

    BI-0144: stage 0a owns ``artifacts/0a/discovery-output.md``; this is its body.
    Deterministic (no LLM) so it can be regenerated from the saved panel at any time.
    """
    project = panel.get("project", "")
    totals = panel.get("totals") or {}
    lines: List[str] = []
    lines.append(f"# 360-degree Discovery - {project}")
    lines.append("")
    idea = " ".join((panel.get("idea") or "").split())
    if idea:
        lines.append(f"> {idea}")
        lines.append("")
    lines.append(f"_Generated {panel.get('generated_at', '')}. "
                 f"{totals.get('agents', 0)} agents - "
                 f"{totals.get('questions', 0)} questions - "
                 f"{totals.get('answered', 0)} answered._")
    lines.append("")
    lines.append("| Agent | Questions | Answered |")
    lines.append("| --- | --- | --- |")
    for g in (panel.get("agents") or []):
        qs = [q for q in (g.get("questions") or []) if not q.get("skip")]
        if not qs:
            continue
        _a = sum(1 for q in qs if (q.get("answer") or "").strip() or q.get("accepted"))
        lines.append(f"| {g.get('agent_id', '')} | {len(qs)} | {_a} |")
    lines.append(f"| **Total** | **{totals.get('questions', 0)}** | "
                 f"**{totals.get('answered', 0)}** |")
    lines.append("")
    for g in (panel.get("agents") or []):
        qs = [q for q in (g.get("questions") or []) if not q.get("skip")]
        if not qs:
            continue
        agent = g.get("agent_id", "")
        lines.append(f"## {agent} - {g.get('name', '')}".rstrip(" -"))
        lines.append("")
        for q in qs:
            ans = (q.get("answer") or "").strip()
            rec = (q.get("recommendation") or "").strip()
            if q.get("accepted"):
                status = "accepted"
            elif ans:
                status = "overridden"
            else:
                status = "unanswered"
            lines.append(f"### {q.get('id', '')} - {q.get('question', '')}")
            lines.append("")
            if rec:
                lines.append(f"- **Recommendation:** {rec}")
            lines.append(f"- **Answer:** {ans or '_(none)_'}")
            lines.append(f"- **Status:** {status}"
                         + (" _(round 2)_" if int(q.get("round", 1)) == 2 else ""))
            if q.get("needs_verification") or q.get("unanswered"):
                lines.append("- **Needs verification:** yes")
            lines.append("")
    if refined_md:
        lines.append("---")
        lines.append("")
        lines.append("## Refined idea / product plan")
        lines.append("")
        lines.append(refined_md.strip())
        lines.append("")
    return "\n".join(lines)


REVIEW_BEGIN = "---BEGIN---"
REVIEW_END = "---END---"


def emit_review_file(panel: Dict, path: str, only_round: int = 0) -> str:
    """BI-0141: write ALL questions to ONE review file for the human to edit.

    Format is line-based and forgiving: each block carries ``ID:`` / ``QUESTION:`` /
    ``RECOMMENDATION:`` and an ``ANSWER:`` section the human edits (everything up to
    ``---END---``). Blank answer keeps the recommendation; the sentinel ``accept``
    accepts the recommendation.
    """
    qs = _askable(panel, only_round)
    lines: List[str] = []
    lines.append(f"# Discovery review - {panel.get('project', '')}")
    lines.append("")
    lines.append("Edit ONLY the text under each 'ANSWER:' line (up to '---END---').")
    lines.append("Do NOT change the 'ID:' / 'QUESTION:' / 'RECOMMENDATION:' lines.")
    lines.append("Leave an answer blank to keep the recommendation; type 'accept' to accept it.")
    lines.append(f"Total questions in this file: {len(qs)}.")
    lines.append("")
    for q in qs:
        lines.append(REVIEW_BEGIN)
        lines.append(f"ID: {q.get('id', '')}")
        lines.append(f"AGENT: {q.get('source_agent', '')}")
        lines.append(f"QUESTION: {(q.get('question') or '').strip()}")
        lines.append(f"RECOMMENDATION: {(q.get('recommendation') or '').strip()}")
        lines.append("ANSWER:")
        lines.append((q.get("answer") or "").strip())
        lines.append(REVIEW_END)
        lines.append("")
    text = "\n".join(lines)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return path


def parse_review_file(path: str) -> Dict[str, str]:
    """Parse an edited review file back into ``{question_id: answer}``.

    Robust to missing markers: falls back to splitting on 'ID:' lines if the
    BEGIN/END markers were removed by the editor.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
    except Exception:
        return {}
    blocks = text.split(REVIEW_END) if REVIEW_END in text else text.split(REVIEW_BEGIN)
    out: Dict[str, str] = {}
    for block in blocks:
        qid = None
        for line in block.splitlines():
            if line.strip().startswith("ID:"):
                qid = line.strip()[3:].strip()
                break
        if not qid:
            continue
        lines = block.splitlines()
        idx = None
        for i, line in enumerate(lines):
            if line.strip().upper() == "ANSWER:":
                idx = i
                break
        if idx is None:
            continue
        ans_lines = [ln for ln in lines[idx + 1:]
                     if ln.strip() not in (REVIEW_BEGIN, REVIEW_END)]
        out[qid] = "\n".join(ans_lines).strip()
    return out
