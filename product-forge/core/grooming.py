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
        similar = [{"ref": s.get("ref"), "id": s.get("id"), "scope": s.get("scope"),
                    "project": s.get("project"), "score": s.get("score"), "title": s.get("title")}
                   for s in backlog.find_similar(text, scope=scope, limit=5)
                   if str(s.get("id")) != str(item.get("id"))]
    except Exception:
        similar = []
    deep = _search_codebase(scope, project, item)
    return {"similar": similar, "deps": list(item.get("deps") or []),
            "affected_components": list(item.get("affected_components") or []),
            "score": item.get("score"),
            "existing_components": deep["existing_components"],
            "existing_apis": deep["existing_apis"],
            "existing_modules": deep["existing_modules"]}


_STOP = {"the", "a", "an", "to", "of", "and", "or", "for", "in", "on", "with", "add", "new",
         "api", "is", "it", "be", "we", "should", "must", "fix", "bug", "feature"}


def _keywords(item: dict) -> list[str]:
    import re as _re
    text = f"{item.get('title','')} {item.get('body','')}".lower()
    words = _re.findall(r"[a-z][a-z0-9_\-]{2,}", text)
    out = []
    for w in words:
        if w in _STOP or w in out:
            continue
        out.append(w)
    return out[:12]


def _search_codebase(scope: str, project: str | None, item: dict) -> dict[str, Any]:
    """Deep scan: find existing components/APIs/modules the item touches (reuse-first evidence).

    Deterministic; reads the real repo. Returns matches + evidence + an architecture-fit hint.
    """
    kws = _keywords(item)
    repo = str(ROOT)
    comps: list[str] = []       # core modules / components
    apis: list[str] = []        # api routes
    modules: list[str] = []     # other relevant files (scripts/docs/config)
    hits = 0
    # 1) core modules: match keyword in filename
    core_dir = os.path.join(repo, "core")
    if os.path.isdir(core_dir) and kws:
        for f in os.listdir(core_dir):
            if not f.endswith(".py"):
                continue
            stem = f[:-3].lower()
            if any(k in stem for k in kws):
                comps.append(f"core/{f}")
                hits += 1
            if len(comps) >= 8:
                break
    # 2) API routes: grep the OpenAPI path list for keyword matches
    try:
        import json as _json
        with open(os.path.join(repo, "api", "openapi.json"), encoding="utf-8-sig") as fh:
            paths = list((_json.load(fh) or {}).get("paths", {}).keys())
        for p in paths:
            if any(k in p.lower() for k in kws):
                apis.append(p)
            if len(apis) >= 8:
                break
    except Exception:
        pass
    # 3) config/other modules by name
    cfg_dir = os.path.join(repo, "config")
    if os.path.isdir(cfg_dir) and kws:
        for f in os.listdir(cfg_dir):
            if f.endswith(".json") and any(k in f[:-5].lower() for k in kws):
                modules.append(f"config/{f}")
            if len(modules) >= 6:
                break
    if hits or apis:
        fit_hint = "EXTEND" if (comps or apis) else "NEW_CAPABILITY"
    else:
        fit_hint = "NEW_CAPABILITY"
    return {"existing_components": comps, "existing_apis": apis, "existing_modules": modules,
            "fit_hint": fit_hint, "keyword_hits": hits + len(apis)}


def deterministic(scope: str, project: str | None, item: dict, *, depth: str = "deep") -> dict[str, Any]:
    """Signals-only proposal: no AI. ``depth='deep'`` also grounds findings in the real codebase."""
    ctx = _gather_context(scope, project, item)
    dup = [s for s in ctx["similar"] if float(s.get("score") or 0) >= 0.6]
    deep = _search_codebase(scope, project, item) if depth == "deep" else \
        {"existing_components": [], "existing_apis": [], "existing_modules": [],
         "fit_hint": "", "keyword_hits": 0}
    if dup:
        fit = "REUSE"
    elif deep["fit_hint"]:
        fit = deep["fit_hint"]
    elif item.get("links") or item.get("deps"):
        fit = "EXTEND"
    else:
        fit = "NEW_CAPABILITY"
    if deep["existing_components"] or deep["existing_apis"]:
        strategy = ("Extend existing components/APIs: " +
                    ", ".join((deep["existing_components"] + deep["existing_apis"])[:4]))
    elif item.get("deps") or item.get("links"):
        strategy = "Extend an existing module/API"
    else:
        strategy = "New capability; design before building (reuse-first)"
    evidence = [f"similar={len(ctx['similar'])}", f"score={ctx['score']}",
                f"components={len(deep['existing_components'])}", f"apis={len(deep['existing_apis'])}"]
    return {
        "analyzed_by": "deterministic",
        "architecture_fit": fit,
        "implementation_strategy": strategy,
        "existing_components": deep["existing_components"],
        "existing_apis": deep["existing_apis"],
        "existing_modules": deep["existing_modules"],
        "duplication_findings": [f"{s['ref']} (score {s['score']:.2f})" for s in dup],
        "dependency_findings": [f"depends on {d}" for d in ctx["deps"]],
        "conflict_findings": [],
        "drift": "NONE",
        "rewrite_required": False,
        "new_component_required": fit in ("NEW_COMPONENT", "NEW_CAPABILITY"),
        "risks": (["possible duplicate"] if dup else []),
        "assumptions": [],
        "evidence": evidence,
        "confidence": ("high" if deep["keyword_hits"] else ("medium" if item.get("deps") else "low")),
        "missing_info": ([] if item.get("title") and item.get("body") else ["body/acceptance criteria thin"]),
        "rationale": f"deterministic {depth} grooming (codebase-grounded)" if depth == "deep"
        else "deterministic grooming from backlog signals",
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
        f"RELATED/SIMILAR backlog items: {ctx.get('similar')}\n"
        f"CANDIDATE EXISTING CODE (reuse-first): components={ctx.get('existing_components')} "
        f"apis={ctx.get('existing_apis')} modules={ctx.get('existing_modules')}\n\n"
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
    v = str(v).strip() if v is not None else ""
    if v:  # an explicit non-empty value wins
        return v.lower() not in ("0", "false", "no", "off")
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
def _dup_threshold() -> float:
    """Jaccard threshold for near-duplicate marking (BI-PF-0432); env PF_DEDUP_THRESHOLD (default 0.6)."""
    import os as _os
    try:
        return float(_os.environ.get("PF_DEDUP_THRESHOLD", "0.6") or 0.6)
    except Exception:
        return 0.6


def _mark_duplicates(scope: str, project: str | None, item: dict, ctx: dict) -> list[str]:
    """BI-PF-0432 (Option B): mark THIS item as a possible duplicate, advisory only.

    Uses the candidates grooming already gathered (``find_similar`` -> ``ctx["similar"]``), restricted to the
    SAME project so we never write across scopes/projects. Only the groomed item is marked (and only when it is
    NOT the highest ``order_by_priority``/canonical of the group): ``links.possible_duplicate_of = [<canonical
    ref>]``, no status change. Never raises (callers suppress).
    """
    from core import backlog
    iid = str(item.get("id"))
    me = backlog.get_epic(scope, project, iid)
    if not me:
        return []
    th = _dup_threshold()
    group = [me]
    for s in (ctx.get("similar") or []):
        if str(s.get("id") or "") in ("", iid):
            continue
        if str(s.get("project") or "") != str(project or ""):
            continue  # same-project only - never mark another project's backlog
        if float(s.get("score") or 0) < th:
            continue
        c = backlog.get_epic(scope, project, str(s.get("id")))
        if c:
            group.append(c)
    if len(group) < 2:
        return []
    canon = backlog.order_by_priority(group)[0]
    if canon is me:
        return []  # I am the canonical -> nothing to mark
    canon_ref = backlog.qualify(str(canon.get("scope") or scope), canon.get("project"), str(canon.get("id")))
    backlog.link(scope, project, iid, possible_duplicate_of=[canon_ref])
    return [iid]


def groom(scope: str, project: str | None, item_id: str, mode: str = "", *,
          product: str = "", depth: str = "deep") -> dict[str, Any]:
    """Groom one item (deep by default). ``mode`` = ai (default) | deterministic.

    Deep analysis (existing components/APIs/modules, duplication/drift, strategy) is grounded in the real
    codebase and stored on the item's ``analysis`` block - so pickup is execution, not re-analysis.
    AI is the default; if the AI path yields nothing, falls back to deterministic (never blocks).
    Returns ``{item_id, mode, depth, proposal, applied, error}``.
    """
    from core import backlog
    it = backlog.get_epic(scope, project, item_id)
    if not it:
        return {"item_id": item_id, "error": "not found", "applied": False}
    m = str(mode or default_mode()).lower()
    if m not in MODES:
        m = "ai"
    d = str(depth or "deep").lower()
    if d not in ("deep", "standard"):
        d = "deep"
    ctx = _gather_context(scope, project, it)
    proposal = None
    used = m
    if m == "ai":
        proposal = _run_ai(it, ctx, project, product or (project or "default"))
        if proposal is None:
            used, proposal = "deterministic", deterministic(scope, project, it, depth=d)
    else:
        proposal = deterministic(scope, project, it, depth=d)

    # persist the proposal onto analysis{} (single writer: backlog)
    analysis = {k: v for k, v in proposal.items() if k in (
        "architecture_fit", "implementation_strategy", "existing_components", "existing_apis",
        "existing_modules", "duplication_findings", "dependency_findings",
        "conflict_findings", "drift", "rewrite_required", "new_component_required", "risks",
        "assumptions", "evidence", "confidence", "missing_info", "rationale")}
    analysis["depth"] = d
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
    # BI-PF-0432: mark near-duplicates (advisory link; never blocks grooming)
    marked: list[str] = []
    with contextlib.suppress(Exception):
        marked = _mark_duplicates(scope, project, it, ctx)
    return {"item_id": item_id, "mode": used, "depth": d, "proposal": proposal,
            "applied": True, "error": "", "marked_duplicates": marked}


def refresh_stale(scope: str, project: str | None = None, *, limit: int = 10,
                  mode: str = "deterministic") -> dict[str, Any]:
    """Re-analyze items whose COMPLETE analysis is stale vs the current architecture (BI-PF-0389).

    Re-grounds the design in the current codebase and updates the stored analysis with the new
    architecture fingerprint, so pickup never executes a stale design. **Deterministic/offline-safe by
    default** (no per-assignment AI grooming); pass ``mode="ai"`` for explicit deep refresh.
    Returns ``{refreshed:[ids], count}``.
    """
    from core import backlog
    refreshed: list[str] = []
    for it in backlog.list_open(scope, project, order=False):
        if len(refreshed) >= int(limit or 10):
            break
        a = it.get("analysis") or {}
        if str(a.get("status")) not in ("COMPLETE", "STALE"):
            continue
        if not backlog.analysis_is_stale(it):
            continue
        m = str(mode or "deterministic").lower()
        proposal = None
        used = m
        if m == "ai":
            ctx = _gather_context(scope, project, it)
            proposal = _run_ai(it, ctx, project, project or "default")
            if proposal is None:
                used, proposal = "deterministic", deterministic(scope, project, it)
        else:
            proposal = deterministic(scope, project, it)
        analysis = {k: v for k, v in proposal.items() if k in (
            "architecture_fit", "implementation_strategy", "existing_components", "existing_apis",
            "existing_modules", "duplication_findings", "dependency_findings",
            "conflict_findings", "drift", "rewrite_required", "new_component_required", "risks",
            "assumptions", "evidence", "confidence", "missing_info", "rationale")}
        analysis["depth"] = "deep"
        analysis["mode"] = used
        analysis["refreshed_at"] = datetime.now().isoformat()
        with contextlib.suppress(Exception):
            backlog.set_analysis(scope, project, it.get("id"), status="COMPLETE", analysis=analysis,
                                 analyzed_by=used)
            refreshed.append(str(it.get("id")))
    return {"refreshed": refreshed, "count": len(refreshed)}


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
