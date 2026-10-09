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
import re
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


def default_batch() -> int:
    """Items per LLM call for bulk grooming (BI-PF-1194). Config ``batch_size``, default 3, min 1."""
    try:
        return max(1, int(guidelines().get("batch_size") or 3))
    except Exception:
        return 3


def default_parallel() -> int:
    """Concurrent batch calls for bulk grooming (BI-PF-1197). Config ``parallel``, default 4, min 1."""
    try:
        return max(1, int(guidelines().get("parallel") or 4))
    except Exception:
        return 4


def _context_review_cfg() -> dict[str, Any]:
    """BI-PF-0665: config for the advisory LLM context review run during grooming."""
    return dict(guidelines().get("context_review") or {})


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
    # BI-PF-1195: derive the full authored context from the item's own body (real content, no placeholders)
    # and map explicit deps to structured dependencies. _apply_proposal gap-fills these onto the item.
    from core import backlog
    draft = backlog._draft_context(
        str(item.get("title") or ""), str(item.get("body") or ""), str(item.get("origin") or ""),
        str(item.get("source") or ""), str(item.get("type") or item.get("type_") or "feature"),
        links=item.get("links"))
    ext_deps = [str(d) for d in (item.get("deps") or [])] + [str(d) for d in (item.get("blocked_by") or [])]
    dependencies = [{"task_id": d, "type": "REQUIRES", "required_state": "COMPLETE"}
                    for d in sorted({x for x in ext_deps if x})]
    return {
        "analyzed_by": "deterministic",
        "architecture_fit": fit,
        "priority_class": "P2", "priority_rank": 2, "moscow": "Should",
        "dependencies": dependencies,
        "context": {
            "objective": draft["objective"],
            "acceptance_criteria": draft["acceptance_criteria"],
            "in_scope": draft["in_scope"],
            "out_of_scope": draft["out_of_scope"],
            "affected_components": draft["affected_components"],
            "affected_files": draft["affected_files"],
            "approach": draft["approach"],
            "verification": draft["verification"],
            "risks": draft["risks"],
            "rollback": draft["rollback"],
            "evidence": draft["evidence"],
            "owner": draft["owner"],
            "requester": draft["requester"],
            "brief": draft["brief"],
        },
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
        "dependencies (list of {task_id,type(BLOCKS|REQUIRES|RELATED),required_state}), "
        "objective (string), acceptance_criteria (list), in_scope (list), out_of_scope (list), "
        "affected_components (list), affected_files (list), approach (string), verification (list), "
        "rollback (string), evidence (list), owner (string), requester (string), "
        "brief ({problem, what_adds, why, who_feels, source='authored'}). "
        "Keep it concise: each list <= 5 short items, each string <= 240 chars."
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


def _llm_text(prompt: str, product: str) -> str:
    """One-shot LLM call via the single LLM owner (BI-PF-1196) - no agent runtime overhead.

    Uses ``core.context_review.default_llm`` (the sanctioned one-shot path over ``LLMClient`` - no new
    client), so grooming is one bounded model call with the cache/ledger/replay machinery, instead of the
    full pipeline agent flow (context package, compliance, design-critic, artifacts, memory).
    """
    from core.context_review import default_llm
    llm = default_llm(str(product or "default"))
    return llm(prompt) or ""


def _extract_json(text: str):
    """Best-effort parse of the first JSON object embedded in model text (fenced ```json or bare)."""
    if not text:
        return None
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        with contextlib.suppress(Exception):
            return json.loads(m.group(1).strip())
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        with contextlib.suppress(Exception):
            return json.loads(text[start:end + 1])
    return None


def _run_ai(item: dict, ctx: dict, project: str | None, product: str) -> dict | None:
    """One-shot LLM groom; return the parsed proposal or None on failure (BI-PF-1196).

    Uses the single LLM owner directly (``_llm_text``) - one bounded call, no agent runtime. A missing or
    garbled response returns None so the caller falls back per item. Skipped when AI is disabled.
    """
    if not _ai_enabled():
        return None
    try:
        text = _llm_text(_ai_prompt(item, ctx) + "\n\nReturn ONLY a single JSON object (no prose, no files).",
                         str(product or (project or "default")))
        proposal = _extract_json(text)
        return proposal if isinstance(proposal, dict) else None
    except Exception:
        return None


def _ai_prompt_batch(items_ctx: list[tuple[dict, dict]]) -> str:
    """Prompt for a batched AI groom: N items in one agent run, one JSON file per item (BI-PF-1194)."""
    gl = guidelines()
    checks = "\n".join(f"- {c.get('id')}: {c.get('ask')}" for c in gl.get("checklist", []))
    parts = []
    for item, ctx in items_ctx:
        parts.append(
            f"=== ITEM {item.get('id')} ===\n"
            f"TITLE: {item.get('title')}\nBODY: {item.get('body','')}\n"
            f"EXISTING deps: {ctx.get('deps')}\nRELATED/SIMILAR backlog items: {ctx.get('similar')}\n"
            f"CANDIDATE EXISTING CODE (reuse-first): components={ctx.get('existing_components')} "
            f"apis={ctx.get('existing_apis')} modules={ctx.get('existing_modules')}")
    ids = ", ".join(str(i.get("id")) for i, _ in items_ctx)
    return (
        f"You are grooming {len(items_ctx)} Product Forge backlog items into execution-ready specs "
        "(reuse-first). Groom EACH item INDEPENDENTLY; never mix findings between items.\n\n"
        + "\n\n".join(parts)
        + "\n\nApply this checklist to EACH item:\n" + checks
        + "\n\nReturn ONLY one JSON object (no prose, no files, no markdown fences) mapping each item id to "
        "its proposal: {\"<ITEM_ID>\": {...}, ...}. Each proposal object uses these keys:\n"
        "architecture_fit (REUSE|EXTEND|MODIFY|NEW_COMPONENT|NEW_CAPABILITY|REFACTOR|OTHER), "
        "implementation_strategy (string), duplication_findings (list), dependency_findings (list), "
        "conflict_findings (list), drift (NONE|LOW|MEDIUM|HIGH), rewrite_required (bool), "
        "new_component_required (bool), risks (list), assumptions (list), evidence (list), "
        "confidence (low|medium|high), missing_info (list), rationale (string), "
        "priority_class (P0|P1|P2|P3), priority_rank (int, lower=higher), moscow (Must|Should|Could|Wont), "
        "dependencies (list of {task_id,type(BLOCKS|REQUIRES|RELATED),required_state}), "
        "objective (string), acceptance_criteria (list), in_scope (list), out_of_scope (list), "
        "affected_components (list), affected_files (list), approach (string), verification (list), "
        "rollback (string), evidence (list), owner (string), requester (string), "
        "brief ({problem, what_adds, why, who_feels, source='authored'}), and "
        "context_review ({implementable (bool), missing (list), reason (string)}). "
        f"Cover exactly these ids: {ids}. "
        "Keep each proposal concise: each list <= 5 short items, each string <= 240 chars."
    )


def _run_ai_batch(items_ctx: list[tuple[dict, dict]], project: str | None,
                  product: str) -> dict[str, dict]:
    """One LLM call grooms N items; returns {item_id: proposal} parsed from the JSON response (BI-PF-1196).

    The prompt requests one JSON object keyed by item id; missing/garbled items are simply absent from the
    result -> the caller falls back per item. Skipped when AI is disabled (automation).
    """
    if not _ai_enabled() or not items_ctx:
        return {}
    try:
        text = _llm_text(_ai_prompt_batch(items_ctx) + "\n\nReturn ONLY the JSON object and nothing else.",
                         str(product or (project or "default")))
        data = _extract_json(text)
    except Exception:
        return {}
    out: dict[str, dict] = {}
    if isinstance(data, dict):
        for item, _ctx in items_ctx:
            v = data.get(str(item.get("id")))
            if isinstance(v, dict):
                out[str(item.get("id"))] = v
    return out


# ── public API ──────────────────────────────────────────────────────────────
def _dup_threshold() -> float:
    """Jaccard threshold for near-duplicate marking (BI-PF-0432); env PF_DEDUP_THRESHOLD (default 0.6)."""
    import os as _os
    try:
        return float(_os.environ.get("PF_DEDUP_THRESHOLD", "0.6") or 0.6)
    except Exception:
        return 0.6


_MOSCOW_RANK = {"must": 0, "should": 1, "could": 2, "wont": 3}


def _mosrank(moscow: Any) -> int:
    return _MOSCOW_RANK.get(str(moscow or "").strip().lower(), 9)


def _same_project_dups(scope: str, project: str | None, item: dict, ctx: dict) -> list[dict]:
    """Same-(scope,project) near-duplicate candidates from grooming's ``ctx["similar"]`` (BI-PF-0432/0435)."""
    from core import backlog
    iid = str(item.get("id"))
    th = _dup_threshold()
    out: list[dict] = []
    for s in (ctx.get("similar") or []):
        if str(s.get("id") or "") in ("", iid):
            continue
        if str(s.get("project") or "") != str(project or ""):
            continue  # same-project only - never touch another project's backlog
        if float(s.get("score") or 0) < th:
            continue
        c = backlog.get_epic(scope, project, str(s.get("id")))
        if c:
            out.append(c)
    return out


def _build_proposal(item: dict, dups: list[dict]) -> dict:
    """A deterministic consolidation draft (BI-PF-0435): fold the duplicates' UNIQUE content into this item."""
    body = str(item.get("body") or "")
    acc = [str(a) for a in (item.get("acceptance_criteria") or [])]
    moscow = str(item.get("moscow") or "")
    sources: list[str] = []
    for d in dups:
        did = str(d.get("id"))
        sources.append(did)
        b = str(d.get("body") or "").strip()
        if b and b not in body:
            body = (body + f"\n\n[consolidated from {did}]: {b}").strip()
        for a in (d.get("acceptance_criteria") or []):
            if str(a) not in acc:
                acc.append(str(a))
        if _mosrank(d.get("moscow")) < _mosrank(moscow):
            moscow = str(d.get("moscow") or moscow)
    return {"sources": sources, "title": item.get("title"), "body": body,
            "acceptance_criteria": acc, "moscow": moscow}


def _mark_duplicates(scope: str, project: str | None, item: dict, ctx: dict) -> list[str]:
    """BI-PF-0432 (Option B): mark THIS item as a possible duplicate, advisory only.

    Restricts candidates to the SAME project (never writes across scopes/projects) and marks ONLY the groomed
    item (and only when it is NOT the highest ``order_by_priority``/canonical of the group):
    ``links.possible_duplicate_of = [<canonical ref>]``, no status change. Never raises (callers suppress).
    """
    from core import backlog
    iid = str(item.get("id"))
    me = backlog.get_epic(scope, project, iid)
    if not me:
        return []
    dups = _same_project_dups(scope, project, item, ctx)
    if not dups:
        return []
    group = [me] + dups
    canon = backlog.order_by_priority(group)[0]
    if canon is me:
        return []  # I am the canonical -> nothing to mark
    canon_ref = backlog.qualify(str(canon.get("scope") or scope), canon.get("project"), str(canon.get("id")))
    backlog.link(scope, project, iid, possible_duplicate_of=[canon_ref])
    return [iid]


_ANALYSIS_KEYS = (
    "architecture_fit", "implementation_strategy", "existing_components", "existing_apis",
    "existing_modules", "duplication_findings", "dependency_findings",
    "conflict_findings", "drift", "rewrite_required", "new_component_required", "risks",
    "assumptions", "evidence", "confidence", "missing_info", "rationale")

# BI-PF-1195: full item context populated by grooming (gap-fill unless force); these are TOP-LEVEL item
# fields (not the analysis block). `brief` is only written when its source is authored/extracted.
_CONTEXT_FIELDS = ("objective", "acceptance_criteria", "in_scope", "out_of_scope",
                   "affected_components", "affected_files", "approach", "verification",
                   "risks", "rollback", "evidence", "owner", "requester", "brief")


def _empty(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, (list, dict, str)):
        return len(v) == 0
    return False


def _apply_proposal(scope: str, project: str | None, item_id: str, it: dict, ctx: dict,
                    proposal: dict, used: str, depth: str, *,
                    context_review: dict | None = None,
                    run_context_review: bool = True, force: bool = False) -> dict[str, Any]:
    """Persist a computed grooming proposal onto the item's ``analysis`` (single writer: backlog).

    Shared by single ``groom`` and batch ``groom_all`` so both behave identically. When ``context_review``
    is passed (batched AI pass), it is stored as-is; otherwise the advisory review is computed per item
    (BI-PF-0665) only when ``run_context_review`` and the config allows it.
    """
    from core import backlog
    analysis = {k: v for k, v in proposal.items() if k in _ANALYSIS_KEYS}
    analysis["depth"] = depth
    analysis["status"] = "IN_PROGRESS"          # awaits user decision -> COMPLETE
    backlog.set_analysis(scope, project, item_id, status="IN_PROGRESS", analysis=analysis,
                         analyzed_by=used)
    # record groomer provenance on the analysis block (survives later status-only updates)
    try:
        _it = backlog.get_epic(scope, project, item_id) or {}
        _a = dict(_it.get("analysis") or {})
        _a["analyzed_by"] = used
        _a["mode"] = used
        backlog.update(scope, project, item_id, analysis=_a)
    except Exception:
        pass
    # BI-PF-0665: advisory AI context review (is the item implementable: what/why/how/where?).
    try:
        rv = context_review
        if rv is None and run_context_review:
            _cr = _context_review_cfg()
            if _cr.get("enabled") and (used == "ai" or _cr.get("on_deterministic")):
                from core import context_review as _crv
                rv = _crv.review(backlog.get_epic(scope, project, item_id) or it)
        if rv is not None:
            _a2 = dict((backlog.get_epic(scope, project, item_id) or {}).get("analysis") or {})
            _a2["context_review"] = rv
            backlog.update(scope, project, item_id, analysis=_a2)
    except Exception:
        pass
    # BI-PF-1195: populate priority + structured deps + full context; gap-fill by default, --force overwrites.
    has_prio = bool(str(it.get("priority") or "").strip())
    pclass = str(proposal.get("priority_class") or "")
    if (force or not has_prio) and (proposal.get("priority_rank") is not None or pclass or proposal.get("moscow")):
        with contextlib.suppress(Exception):
            backlog.set_priority(scope, project, item_id,
                                 priority=(str(proposal.get("priority") or pclass) or None),
                                 priority_rank=proposal.get("priority_rank"),
                                 priority_class=pclass, moscow=str(proposal.get("moscow") or ""))
    if (force or _empty(it.get("dependencies"))) and proposal.get("dependencies"):
        with contextlib.suppress(Exception):
            backlog.set_dependencies(scope, project, item_id, dependencies=proposal["dependencies"])
    # context fields: deterministic supplies proposal["context"]; AI supplies them top-level.
    ctx_src = proposal.get("context") if isinstance(proposal.get("context"), dict) else proposal
    ctx_updates: dict[str, Any] = {}
    for f in _CONTEXT_FIELDS:
        val = ctx_src.get(f, proposal.get(f))
        if _empty(val):
            continue
        if f == "brief" and isinstance(val, dict) and str(val.get("source")) not in ("authored", "extracted"):
            continue
        if force or _empty(it.get(f)):
            ctx_updates[f] = val
    if ctx_updates:
        with contextlib.suppress(Exception):
            backlog.update(scope, project, item_id, **ctx_updates)
    # BI-PF-0432: mark near-duplicates (advisory link; never blocks grooming)
    marked: list[str] = []
    with contextlib.suppress(Exception):
        marked = _mark_duplicates(scope, project, it, ctx)
    # BI-PF-0435: if same-project near-duplicates exist, store a consolidation proposal (human-approved apply)
    with contextlib.suppress(Exception):
        dups = _same_project_dups(scope, project, it, ctx)
        if dups:
            _a = dict((backlog.get_epic(scope, project, item_id) or {}).get("analysis") or {})
            _a["consolidation_proposal"] = _build_proposal(it, dups)
            backlog.update(scope, project, item_id, analysis=_a)
    return {"item_id": item_id, "mode": used, "depth": depth, "proposal": proposal,
            "applied": True, "error": "", "marked_duplicates": marked}


def groom(scope: str, project: str | None, item_id: str, mode: str = "", *,
          product: str = "", depth: str = "deep", force: bool = False) -> dict[str, Any]:
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

    res = _apply_proposal(scope, project, item_id, it, ctx, proposal, used, d, force=force)
    if m == "ai" and used != "ai":
        res["ai_failed"] = True   # asked for AI, fell back -> surface it (BI-PF-1196), never silent
    return res


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


def groom_all(scope: str, project: str | None, mode: str = "", *, batch: int = 0, limit: int = 0,
              force: bool = False, dry: bool = False, depth: str = "deep",
              jobs: int = 0) -> dict[str, Any]:
    """Groom every open backlog item (incl. EPICs) in batched, concurrent AI passes (BI-PF-1194/1197).

    AI is the default; up to ``batch`` items share one LLM call (returning the analysis + advisory
    context_review per item) and up to ``jobs`` batches run concurrently (bounded threads; the LLM client
    rate budget still paces globally). Items a batch misses fall back to per-item deterministic analysis
    (never blocks). Items already IN_PROGRESS/COMPLETE are skipped unless ``force``. ``dry`` returns the
    planned ids without writing. Single writer: backlog (writes are applied sequentially in this thread).
    """
    from core import backlog
    m = str(mode or default_mode()).lower()
    if m not in MODES:
        m = "ai"
    d = str(depth or "deep").lower()
    if d not in ("deep", "standard"):
        d = "deep"
    n = max(1, int(batch or 0) or default_batch())
    workers = max(1, int(jobs or 0) or default_parallel())
    queue: list[dict] = []
    for it in backlog.list_open(scope, project):
        st = str((it.get("analysis") or {}).get("status") or "NOT_ANALYZED")
        # BI-PF-1195: (re)groom NOT_ANALYZED + IN_PROGRESS; COMPLETE (approved) only with --force.
        if not force and st == "COMPLETE":
            continue
        queue.append(it)
    if int(limit or 0) > 0:
        queue = queue[:int(limit)]
    if dry:
        return {"mode": m, "batch": n, "jobs": workers, "count": len(queue), "dry": True,
                "items": [{"id": i.get("id"), "title": i.get("title")} for i in queue]}
    chunks = [queue[i:i + n] for i in range(0, len(queue), n)]
    groomed: list[str] = []
    results: list[dict] = []

    def _run_chunk(chunk: list[dict]):
        ctxs = [(it, _gather_context(scope, project, it)) for it in chunk]
        props = _run_ai_batch(ctxs, project, project or "default") if m == "ai" else {}
        return ctxs, props

    def _apply_chunk(ctxs, proposals):
        for it, ctx in ctxs:
            iid = str(it.get("id"))
            prop = proposals.get(iid)
            used = m
            ai_failed = False
            if not isinstance(prop, dict):
                used, prop = "deterministic", deterministic(scope, project, it, depth=d)
                ai_failed = (m == "ai")   # BI-PF-1196: surface the fallback, never silent
            cr = prop.pop("context_review", None) if isinstance(prop, dict) else None
            try:
                _apply_proposal(scope, project, iid, it, ctx, prop, used, d, context_review=cr,
                                force=force)
                groomed.append(iid)
                results.append({"item_id": iid, "mode": used, "applied": True, "ai_failed": ai_failed})
            except Exception as e:  # noqa: BLE001
                results.append({"item_id": iid, "mode": used, "applied": False,
                                "error": f"{type(e).__name__}: {e}"})

    if m == "ai" and workers > 1 and len(chunks) > 1:
        import concurrent.futures as _cf
        with _cf.ThreadPoolExecutor(max_workers=workers) as pool:
            for ctxs, props in pool.map(_run_chunk, chunks):
                _apply_chunk(ctxs, props)
    else:
        for chunk in chunks:
            ctxs, props = _run_chunk(chunk)
            _apply_chunk(ctxs, props)
    return {"mode": m, "batch": n, "jobs": workers, "count": len(groomed),
            "groomed": groomed, "results": results}


def review(scope: str, project: str | None) -> dict[str, Any]:
    """One view of groomed-but-undecided items (BI-PF-1194): status, confidence, dup/consolidation flags,
    context_review verdict - so a human can eyeball before ``decide_all``."""
    from core import backlog
    out = []
    for it in backlog.list_open(scope, project):
        a = it.get("analysis") or {}
        if str(a.get("status") or "NOT_ANALYZED") != "IN_PROGRESS":
            continue
        cr = a.get("context_review") or {}
        flags = []
        if a.get("duplication_findings"):
            flags.append("duplication")
        if a.get("consolidation_proposal"):
            flags.append("consolidation")
        if str(a.get("confidence") or "") == "low":
            flags.append("low-confidence")
        if cr and cr.get("ok") is False:
            flags.append("context-review-failed")
        if a.get("missing_info"):
            flags.append("missing-info")
        out.append({
            "id": it.get("id"), "title": it.get("title"), "status": a.get("status"),
            "confidence": a.get("confidence") or "", "architecture_fit": a.get("architecture_fit") or "",
            "analyzed_by": a.get("analyzed_by") or "", "flags": flags,
            "context_review": cr or None,
        })
    return {"count": len(out), "items": out}


def decide_all(scope: str, project: str | None, decision: str = "APPROVE", *,
               ids: list[str] | None = None, force: bool = False, dry: bool = False,
               by: str = "user") -> dict[str, Any]:
    """Apply a grooming decision to many groomed items at once (BI-PF-1194), default APPROVE.

    Without ``force``, APPROVE only approves CLEAN items (no consolidation proposal, no duplication
    findings, confidence not low, context_review not failed); flagged items are returned for manual
    handling. ``ids`` restricts to a subset; ``dry`` previews. Per-item via ``decide`` (single writer).
    """
    from core import backlog
    d = str(decision or "APPROVE").upper()
    want = {str(x) for x in ids} if ids else None
    approved: list[str] = []
    flagged: list[dict] = []
    skipped: list[str] = []
    for it in backlog.list_open(scope, project):
        iid = str(it.get("id"))
        if want is not None and iid not in want:
            continue
        a = it.get("analysis") or {}
        if str(a.get("status")) != "IN_PROGRESS":
            skipped.append(iid)
            continue
        reasons = []
        if a.get("duplication_findings"):
            reasons.append("duplication")
        if a.get("consolidation_proposal"):
            reasons.append("consolidation")
        if str(a.get("confidence") or "") == "low":
            reasons.append("low-confidence")
        cr = a.get("context_review") or {}
        if cr and cr.get("ok") is False:
            reasons.append("context-review-failed")
        if reasons and d == "APPROVE" and not force:
            flagged.append({"id": iid, "reasons": reasons})
            continue
        if dry:
            approved.append(iid)
            continue
        decide(scope, project, iid, d, by=by)
        approved.append(iid)
    return {"decision": d, "approved": approved, "count": len(approved),
            "flagged": flagged, "skipped": skipped, "dry": bool(dry)}


def _apply_consolidation(scope: str, project: str | None, item_id: str, by: str = "user",
                         note: str = "") -> dict[str, Any]:
    """BI-PF-0435: apply a stored consolidation proposal (human-approved).

    Folds the duplicates' unique content into THIS item (append), records provenance
    (``links.consolidated_from`` + a ``decisions[]`` ledger entry), and closes each duplicate as ``duplicate``
    (``links.duplicate_of`` + note; preserved in closed.json/history - never deleted). Never raises.
    """
    from core import backlog
    it = backlog.get_epic(scope, project, item_id)
    if not it:
        return {"item_id": item_id, "error": "not found", "applied": False}
    prop = (it.get("analysis") or {}).get("consolidation_proposal") or {}
    sources = [str(x) for x in (prop.get("sources") or [])]
    if not sources:
        return {"item_id": item_id, "error": "no consolidation proposal (groom first)", "applied": False}
    canon_ref = backlog.qualify(scope, project, item_id)
    merged: dict[str, Any] = {"_note": "consolidated (BI-PF-0435)"}
    if prop.get("body"):
        merged["body"] = prop["body"]
    if prop.get("acceptance_criteria"):
        merged["acceptance_criteria"] = prop["acceptance_criteria"]
    if prop.get("moscow"):
        merged["moscow"] = prop["moscow"]
    with contextlib.suppress(Exception):
        backlog.update(scope, project, item_id, **merged)
    with contextlib.suppress(Exception):
        backlog.link(scope, project, item_id,
                     consolidated_from=[backlog.qualify(scope, project, s) for s in sources])
    closed = []
    for s in sources:
        with contextlib.suppress(Exception):
            backlog.set_status(scope, project, s, "duplicate",
                               note=f"consolidated into {canon_ref} by {by}")
            backlog.link(scope, project, s, duplicate_of=[canon_ref])
            closed.append(s)
    with contextlib.suppress(Exception):
        it2 = backlog.get_epic(scope, project, item_id) or {}
        backlog.update(scope, project, item_id, decisions=[
            *(it2.get("decisions") or []),
            {"at": datetime.now().isoformat(), "by": by, "decision": "CONSOLIDATE",
             "sources": sources, "note": str(note or "")}])
    return {"item_id": item_id, "decision": "CONSOLIDATE", "applied": True,
            "consolidated": closed, "duplicate_of": canon_ref}


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
    if d == "CONSOLIDATE":
        return _apply_consolidation(scope, project, item_id, by=by, note=note)
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
