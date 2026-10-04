"""PFSSOT-P2 (BI-PF-0363): AI + user grooming for backlog items.

Grooming turns a raw backlog item into an execution-ready one: priority, structured dependencies,
architecture-fit/strategy, duplication/drift/conflict findings, risks, readiness, and missing-info.

- **AI grooming is the DEFAULT** (``mode="ai"``): reuses the existing agent runtime
  (``PipelineExecutor.execute_agent``) - NO new LLM client. The agent writes a proposal JSON which is
  read back and stored on the item's ``analysis`` block (single writer: ``core.backlog``).
- **Deterministic grooming** (``mode="deterministic"``): no model; uses existing signals
  (``backlog.find_similar``, ``deps``, ``links``, ``score``) - always available as a fallback.
- **User grooming** (``decide``) records APPROVE/MODIFY/REJECT/DEFER on the item (reuses backlog
  ``decisions[]`` + ``analysis`` state) - the gate that makes an analysis COMPLETE / item READY.

Guidelines + cadence are DATA in ``config/grooming-guidelines.json`` (not hardcoded).
One small concern, one writer per store; the item's ``analysis``/``decisions`` are written via
``core.backlog`` only.
"""
import contextlib
import json
import os
from datetime import datetime
from typing import Any

from core.paths import ROOT

GUIDELINES = os.path.join(str(ROOT), "config", "grooming-guidelines.json")
MODES = ("ai", "deterministic")
_AI_AGENT = "analyst"
_AI_STAGE = "groom"


def guidelines() -> dict[str, Any]:
    try:
        with open(GUIDELINES, encoding="utf-8-sig") as f:
            return json.load(f) or {}
    except Exception:
        return {"default_mode": "ai", "checklist": [], "decision_options": ["APPROVE", "MODIFY", "REJECT", "DEFER"]}


def default_mode() -> str:
    return str(guidelines().get("default_mode") or "ai")


# ── deterministic groomer (no model) ────────────────────────────────────────
def _item_dir(scope: str, project: str | None) -> str:
    from core import backlog
    return backlog._dir(backlog._norm_scope(scope), project)


def _gather_context(scope: str, project: str | None, item: dict) -> dict[str, Any]:
    """Cheap context the grooms need: similar items, deps, target module hints."""
    from core import backlog
    text = f"{item.get('title','')} {item.get('body','')}".strip()
    similar = []
    try:
        similar = [{"ref": s.get("ref"), "score": s.get("score"), "title": s.get("title")}
                   for s in backlog.find_similar(text, scope=scope, limit=5)
                   if s.get("ref") != item.get("id")]
    except Exception:
        similar = []
    return {"similar": similar, "deps": list(item.get("deps") or []),
            "affected_components": list(item.get("affected_components") or []),
            "score": item.get("score")}


def deterministic(scope: str, project: str | None, item: dict) -> dict[str, Any]:
    """Signals-only proposal: no AI. Always available."""
    ctx = _gather_context(scope, project, item)
    dup = [s for s in ctx["similar"] if float(s.get("score") or 0) >= 0.6]
    fit = "REUSE" if dup else ("EXTEND" if item.get("links") or item.get("deps") else "NEW_CAPABILITY")
    strategy = ("Merge/extend an existing item" if dup else
                "Extend an existing module/API" if item.get("deps") or item.get("links") else
                "New capability; design before building (reuse-first)")
    return {
        "analyzed_by": "deterministic",
        "architecture_fit": fit,
        "implementation_strategy": strategy,
        "duplication_findings": [f"{s['ref']} (score {s['score']:.2f})" for s in dup],
        "dependency_findings": [f"depends on {d}" for d in ctx["deps"]],
        "conflict_findings": [],
        "drift": "NONE",
        "rewrite_required": False,
        "new_component_required": fit in ("NEW_COMPONENT", "NEW_CAPABILITY"),
        "risks": (["possible duplicate"] if dup else []),
        "assumptions": [],
        "evidence": [f"similar={len(ctx['similar'])}", f"score={ctx['score']}"],
        "confidence": "low" if not item.get("deps") else "medium",
        "missing_info": ([] if item.get("title") and item.get("body") else ["body/acceptance criteria thin"]),
        "rationale": "deterministic grooming from backlog signals",
    }


# ── AI groomer (default) - reuses the existing agent runtime ────────────────
def _ai_prompt(item: dict, ctx: dict) -> str:
    gl = guidelines()
    checks = "\n".join(f"- {c.get('id')}: {c.get('ask')}" for c in gl.get("checklist", []))
    return (
        "You are grooming ONE Product Forge backlog item into an execution-ready spec (reuse-first).\n\n"
        f"ITEM: {item.get('id')} - {item.get('title')}\n"
        f"BODY: {item.get('body','')}\n"
        f"EXISTING deps: {ctx.get('deps')}\n"
        f"RELATED/SIMILAR backlog items: {ctx.get('similar')}\n\n"
        "Apply this checklist:\n" + checks + "\n\n"
        "Produce ONLY a JSON object (no prose) with keys:\n"
        "architecture_fit (REUSE|EXTEND|MODIFY|NEW_COMPONENT|NEW_CAPABILITY|REFACTOR|OTHER), "
        "implementation_strategy (string), duplication_findings (list), dependency_findings (list), "
        "conflict_findings (list), drift (NONE|LOW|MEDIUM|HIGH), rewrite_required (bool), "
        "new_component_required (bool), risks (list), assumptions (list), evidence (list), "
        "confidence (low|medium|high), missing_info (list), rationale (string), "
        "priority_class (P0|P1|P2|P3), priority_rank (int, lower=higher), moscow (Must|Should|Could|Wont), "
        "dependencies (list of {task_id,type(BLOCKS|REQUIRES|RELATED),required_state})."
    )


def _ai_enabled() -> bool:
    """AI grooming runs only when enabled - default ON, but auto-OFF in automation.

    Order: ``PF_GROOMING_AI`` (0/false disables), else disabled when ``PF_OFFLINE``/``CI`` is set,
    else enabled (ai is the product default). Keeps gates/CI from making slow live calls.
    """
    import os as _os
    v = None
    try:
        from core import env_flags
        v = env_flags.get("PF_GROOMING_AI", None)
    except Exception:
        v = _os.environ.get("PF_GROOMING_AI")
    if v is not None:
        return str(v).lower() not in ("0", "false", "no", "off")
    offline = str(_os.environ.get("PF_OFFLINE", "")).lower() in ("1", "true", "yes")
    return not (offline or _os.environ.get("CI"))


def _run_ai(item: dict, ctx: dict, project: str | None, product: str) -> dict | None:
    """Invoke the existing agent runtime; return the parsed proposal or None on failure.

    Reuses ``PipelineExecutor.execute_agent`` (no new LLM client). Writes the proposal to the project's
    engineering dir as ``groom-<id>.json`` and reads it back. Skipped when AI is disabled (automation).
    """
    if not _ai_enabled():
        return None
    try:
        from core.pipeline_executor import PipelineExecutor
        ex = PipelineExecutor(products_dir=os.path.join(str(ROOT), "products"), project=str(product or "default"))
        prompt = _ai_prompt(item, ctx) + (
            f"\n\nWrite the JSON to `engineering/groom-{item.get('id')}.json` and nothing else.")
        ex.execute_agent(_AI_AGENT, _AI_STAGE, prompt)
        out_path = os.path.join(ex.project_dir, "engineering", f"groom-{item.get('id')}.json")
        if os.path.exists(out_path):
            with open(out_path, encoding="utf-8-sig") as f:
                return json.load(f)
    except Exception:
        return None
    return None


# ── public API ──────────────────────────────────────────────────────────────
def groom(scope: str, project: str | None, item_id: str, mode: str = "", *,
          product: str = "") -> dict[str, Any]:
    """Groom one item. ``mode`` = ai (default) | deterministic. Stores the proposal on the item's analysis.

    AI is the default; if the AI path yields nothing, falls back to deterministic (never blocks).
    Returns ``{item_id, mode, proposal, applied, error}``.
    """
    from core import backlog
    it = backlog.get_epic(scope, project, item_id)
    if not it:
        return {"item_id": item_id, "error": "not found", "applied": False}
    m = str(mode or default_mode()).lower()
    if m not in MODES:
        m = "ai"
    ctx = _gather_context(scope, project, it)
    proposal = None
    used = m
    if m == "ai":
        proposal = _run_ai(it, ctx, project, product or (project or "default"))
        if proposal is None:
            used, proposal = "deterministic", deterministic(scope, project, it)
    else:
        proposal = deterministic(scope, project, it)

    # persist the proposal onto analysis{} (single writer: backlog)
    analysis = {k: v for k, v in proposal.items() if k in (
        "architecture_fit", "implementation_strategy", "duplication_findings", "dependency_findings",
        "conflict_findings", "drift", "rewrite_required", "new_component_required", "risks",
        "assumptions", "evidence", "confidence", "missing_info", "rationale")}
    analysis["status"] = "IN_PROGRESS"          # awaits user decision -> COMPLETE
    backlog.set_analysis(scope, project, item_id, status="IN_PROGRESS", analysis=analysis,
                         analyzed_by=used)
    # record groomer provenance on the analysis block too (survives later status-only updates)
    try:
        from core import backlog as _b
        _it = _b.get_epic(scope, project, item_id) or {}
        _a = dict(_it.get("analysis") or {})
        _a["analyzed_by"] = used
        _a["mode"] = used
        _b.update(scope, project, item_id, analysis=_a)
    except Exception:
        pass
    # optional priority proposal
    if proposal.get("priority_rank") is not None or proposal.get("priority_class") or proposal.get("moscow"):
        with contextlib.suppress(Exception):
            backlog.set_priority(scope, project, item_id,
                                 priority_rank=proposal.get("priority_rank"),
                                 priority_class=str(proposal.get("priority_class") or ""),
                                 moscow=str(proposal.get("moscow") or ""))
    if proposal.get("dependencies"):
        with contextlib.suppress(Exception):
            backlog.set_dependencies(scope, project, item_id, dependencies=proposal["dependencies"])
    return {"item_id": item_id, "mode": used, "proposal": proposal, "applied": True, "error": ""}


def decide(scope: str, project: str | None, item_id: str, decision: str,
           note: str = "", by: str = "user") -> dict[str, Any]:
    """User grooming decision: APPROVE -> analysis COMPLETE + item ready; MODIFY/REJECT/DEFER accordingly."""
    from core import backlog
    opts = [str(o).upper() for o in guidelines().get("decision_options", ["APPROVE", "MODIFY", "REJECT", "DEFER"])]
    d = str(decision or "").upper()
    if d not in opts:
        raise ValueError(f"decision must be one of {opts}")
    it = backlog.get_epic(scope, project, item_id)
    if not it:
        return {"item_id": item_id, "error": "not found", "applied": False}
    if d == "APPROVE":
        backlog.set_analysis(scope, project, item_id, status="COMPLETE", analyzed_by=by)
        backlog.set_readiness(scope, project, item_id, True, reasons=[])
    elif d == "MODIFY":
        backlog.set_analysis(scope, project, item_id, status="IN_PROGRESS")
    elif d == "DEFER":
        backlog.set_analysis(scope, project, item_id, status="NOT_ANALYZED")
    else:  # REJECT
        backlog.set_analysis(scope, project, item_id, status="STALE")
    backlog.update(scope, project, item_id, decisions=[
        *(it.get("decisions") or []), {"at": datetime.now().isoformat(), "decision": d,
                                        "by": by, "note": str(note or "")}])
    return {"item_id": item_id, "decision": d, "applied": True}
