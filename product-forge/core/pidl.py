"""PIDL-1 (BI-PF-0376): Personal Intelligence Decision Layer - context resolver.

PIDL is a centralized **decision/perspective** capability invoked by the orchestration/scheduler path at
decision boundaries (never by workers). This module is the read-only **context resolver**: it assembles
only the *relevant subset* of the user's established rules/principles/preferences/prior decisions for a
given task/result/action - it never injects the whole personality.

Reuse, not rewrite (doc appendix): rules/principles come from ``core.forge_constitution`` + ``core.learnings``;
preferences from ``core.persona``; prior decisions/context from ``core.memory_api``. PIDL owns only the thin
profile index (``config/pidl-profile.json``). No new memory/identity store, no worker coupling.

The resolver is PURE and fail-open-to-empty: any unavailable source degrades to an empty list, never raises.
"""
import contextlib
import json
import os
from datetime import datetime
from typing import Any

from core.paths import ROOT

PROFILE_FILE = "pidl-profile.json"
_PROFILE_PATH = os.path.join(ROOT, "config", PROFILE_FILE)
_APPROVAL_PATH = os.path.join(ROOT, "config", "approval-policy.json")
_TRACE_DEFAULT = os.path.join(ROOT, "data", "pidl", "decisions.jsonl")


def load_profile() -> dict[str, Any]:
    """The PIDL profile index (categories -> canonical sources, lenses, approval defaults)."""
    try:
        with open(_PROFILE_PATH, encoding="utf-8-sig") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _text(*parts: Any) -> str:
    return " ".join(str(p or "") for p in parts).lower()


def _lenses(profile: dict[str, Any], area: str, components: list[str], action: str) -> list[str]:
    """Deterministic review lenses from the touched area/components/action (profile-mapped)."""
    mapping = profile.get("area_lenses") or {}
    lens_set: list[str] = []
    hay = _text(area, action, *components)
    for key, lenses in mapping.items():
        if key and key.lower() in hay:
            for lens in lenses:
                if lens not in lens_set:
                    lens_set.append(lens)
    if not lens_set:
        lens_set = list(profile.get("review_lenses") or [])
    return lens_set


def _consequential(profile: dict[str, Any], area: str, components: list[str], action: str) -> bool:
    hay = _text(area, action, *components)
    return any(str(k).lower() in hay for k in (profile.get("consequential_keywords") or []))


def _strict_rules() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        from core import forge_constitution as fc
        c = fc.get_default_constitution()
        strict = set((load_profile().get("categories", {}).get("rules", {}) or {}).get("strict_severities")
                     or ["mandatory"])
        for r in c.rules:
            if getattr(r, "enabled", True) and str(getattr(r, "severity", "")) in strict:
                out.append({"ref": f"CONST-{r.rule_id}", "name": r.name, "category": r.category,
                            "severity": r.severity})
    except Exception:
        pass
    return out


def _principles() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        from core import forge_constitution as fc
        c = fc.get_default_constitution()
        for r in c.rules:
            if getattr(r, "enabled", True) and str(getattr(r, "severity", "")) != "mandatory":
                out.append({"ref": f"CONST-{r.rule_id}", "name": r.name, "category": r.category})
    except Exception:
        pass
    try:
        from core import learnings
        for ln in (learnings.all_learnings() or [])[:20]:
            out.append({"ref": str(ln.get("id")), "name": ln.get("rule"), "area": ln.get("area")})
    except Exception:
        pass
    return out


def _preferences() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        from core import persona
        p = persona.load() or {}
        for key in ("must", "must_not", "knobs", "traits"):
            for v in (p.get(key) or []):
                out.append({"key": key, "value": v})
    except Exception:
        pass
    return out


def _prior_decisions(scope: str, project: str | None, components: list[str], area: str) -> list[dict[str, Any]]:
    """Relevant prior decisions from the existing memory/RAG store (read-only)."""
    out: list[dict[str, Any]] = []
    queries = [q for q in ([area] + list(components)) if q]
    if not queries:
        return out
    try:
        from core.memory_api import MemoryAPI
        api = MemoryAPI(project=str(project or scope or "default"))
        got = api.retrieve_batch(queries, min_confidence=0.5, max_per_query=5) or {}
        for q, entries in got.items():
            for e in (entries or [])[:5]:
                out.append({"query": q, "ref": getattr(e, "source", "") or getattr(e, "id", ""),
                            "text": (getattr(e, "content", "") or "")[:200]})
    except Exception:
        pass
    return out


def resolve_context(scope: str = "product_forge", project: str | None = None, *,
                    task: dict[str, Any] | None = None, result: dict[str, Any] | None = None,
                    action: str = "", components: list[str] | None = None,
                    area: str = "", max_rules: int = 20) -> dict[str, Any]:
    """Assemble the relevant PIDL context subset for a decision point (read-only, deterministic)."""
    profile = load_profile()
    comps = [str(c) for c in (components or [])]
    if task and not comps:
        comps = [str(c) for c in (task.get("affected_components") or [])]
    area_eff = area or (comps[0] if comps else "")

    rules = _strict_rules()[:max_rules]
    principles = _principles()[:max_rules]
    preferences = _preferences()
    lenses = _lenses(profile, area_eff, comps, action)
    consequential = _consequential(profile, area_eff, comps, action)
    prior = _prior_decisions(scope, project, comps, area_eff)

    approval = dict(profile.get("approval_defaults") or {})
    if consequential:
        approval["autonomy"] = "restricted"
        approval["approval_required"] = True
    policy = {"autonomy": approval.get("autonomy", "allowed"),
              "approval_required": bool(approval.get("approval_required", False)),
              "escalation_allowed": bool(approval.get("escalation_allowed", True))}

    evidence = ([r["ref"] for r in rules] + [p["ref"] for p in principles if p.get("ref")])[:max_rules]
    return {
        "scope": scope, "project": project or "",
        "profile_version": int(profile.get("version") or 0),
        "applicable_rules": rules,
        "applicable_principles": principles,
        "applicable_preferences": preferences,
        "prior_decisions": prior,
        "review_lenses": lenses,
        "execution_policy": policy,
        "consequential": consequential,
        "evidence": evidence,
        "context_size": {"rules": len(rules), "principles": len(principles),
                         "preferences": len(preferences), "prior_decisions": len(prior)},
    }


# ── PIDL-2 (BI-PF-0377): decision engine + structured contract ─────────────────────────────
ACTIONS = ("AUTO_PROCEED", "REVIEW", "CORRECT", "APPROVAL_REQUIRED", "ESCALATE")
_NEXT_ACTION = {
    "AUTO_PROCEED": "continue; no intervention required",
    "REVIEW": "route the result to AI/human review before proceeding",
    "CORRECT": "re-dispatch a correction with the conflicts resolved",
    "APPROVAL_REQUIRED": "request authenticated human approval before proceeding",
    "ESCALATE": "escalate to a human operator",
}


def _confidence(result: dict[str, Any] | None, ctx: dict[str, Any], conflicts: list[Any]) -> dict[str, float]:
    """Deterministic, explainable confidence signals (bounded 0..1). No LLM required."""
    has_result = result is not None
    ok = bool(result.get("ok", True)) if has_result else True
    factual = 0.95 if (has_result and ok) else (0.6 if has_result else 0.8)
    architectural = max(0.3, 0.9 - 0.3 * len(conflicts))
    requirement = 0.9 if ctx.get("applicable_principles") else 0.75
    preference = 0.9 if ctx.get("applicable_preferences") else 0.7
    implementation = 0.95 if ok else 0.5
    return {"factual": round(factual, 2), "architectural": round(architectural, 2),
            "requirement_interpretation": round(requirement, 2),
            "user_preference": round(preference, 2), "implementation": round(implementation, 2)}


def decide(scope: str = "product_forge", project: str | None = None, *,
           task: dict[str, Any] | None = None, result: dict[str, Any] | None = None,
           action: str = "", components: list[str] | None = None, area: str = "",
           conflicts: list[Any] | None = None, failures: int = 0, escalated: bool = False) -> dict[str, Any]:
    """Evaluate a decision point and return the structured PIDL decision contract (read-only, pure).

    Precedence: ESCALATE -> APPROVAL_REQUIRED (consequential) -> CORRECT (conflicts) -> REVIEW
    (failed/low-confidence) -> AUTO_PROCEED.
    """
    profile = load_profile()
    conf = list(conflicts or [])
    ctx = resolve_context(scope, project, task=task, result=result, action=action,
                          components=components, area=area)
    decision_cfg = profile.get("decision") or {}
    weights = decision_cfg.get("weights") or {}
    review_below = float(decision_cfg.get("review_below", 0.6))
    escalate_failures = int(decision_cfg.get("escalate_failures", 3))

    sig = _confidence(result, ctx, conf)
    wsum = sum(float(weights.get(k, 0.0)) for k in sig) or 1.0
    overall = round(sum(float(weights.get(k, 0.0)) * v for k, v in sig.items()) / wsum, 2)
    sig["overall"] = overall

    status = str((result or {}).get("status") or "").lower()
    ok = bool((result or {}).get("ok", True))
    # PIDL-5: approval policy (config/approval-policy.json) augments the consequential signal
    pol = approval_policy(action=action, area=area, components=components)
    approval_required = bool(ctx["execution_policy"].get("approval_required")) or bool(pol.get("required"))

    if escalated or int(failures) >= escalate_failures:
        act, reason = "ESCALATE", f"repeated failures ({failures}) or explicit escalation"
    elif approval_required:
        act, reason = "APPROVAL_REQUIRED", "consequential action under the approval policy"
    elif conf:
        act, reason = "CORRECT", f"{len(conf)} conflict(s) to resolve"
    elif not ok or status in ("failed", "blocked", "needs_review", "review") or overall < review_below:
        act, reason = "REVIEW", f"result not clean (status={status or 'n/a'}, confidence={overall})"
    else:
        act, reason = "AUTO_PROCEED", "consistent with policy; no conflicts; confidence sufficient"

    risk = "HIGH" if (ctx.get("consequential") or conf) else ("MEDIUM" if act in ("REVIEW", "APPROVAL_REQUIRED") else "LOW")
    return {
        "scope": scope, "project": project or "",
        "decision": {"action": act, "reason": reason},
        "confidence": sig,
        "risk": risk,
        "recommendation": _NEXT_ACTION[act],
        "evidence": ctx.get("evidence", []),
        "conflicts": conf,
        "approval": {"required": approval_required, "policy": ctx["execution_policy"],
                     "approval_policy": pol.get("policy"), "approver": pol.get("approver")},
        "next_action": _NEXT_ACTION[act],
        "pidl_profile_version": ctx.get("profile_version"),
    }


# ── PIDL-3 (BI-PF-0378): worker-result decision gate (primary trigger) ─────────────────────
def gate_mode() -> str:
    """The gate mode: ``advisory`` (record only) or ``enforce`` (hold non-AUTO closes)."""
    try:
        from core import env_flags
        m = str(env_flags.get("PIDL_GATE_MODE", "advisory") or "advisory").strip().lower()
        return m if m in ("advisory", "enforce") else "advisory"
    except Exception:
        return "advisory"


def gate(scope: str = "product_forge", project: str | None = None, *, item_id: str = "",
         result: dict[str, Any] | None = None, action: str = "", components: list[str] | None = None,
         area: str = "", conflicts: list[Any] | None = None, failures: int = 0,
         escalated: bool = False, run_id: str = "") -> dict[str, Any]:
    """The worker-result decision gate: evaluate a finished result and return the decision + provenance.

    Invoked by the ORCHESTRATION path (never the worker). Pure/read-only; the caller acts on the result.
    """
    d = decide(scope, project, result=result, action=action, components=components, area=area,
               conflicts=conflicts, failures=failures, escalated=escalated)
    d["item_id"] = str(item_id or "")
    d["run_id"] = str(run_id or "")
    d["worker_id"] = str((result or {}).get("worker_id") or "")
    d["runtime"] = str((result or {}).get("provider") or (result or {}).get("runtime") or "")
    d["gate_mode"] = gate_mode()
    return d


# ── PIDL-4 (BI-PF-0379): pre-dispatch evaluation + cross-worker synthesis + consequential gate ──
def pre_dispatch(scope: str = "product_forge", project: str | None = None, *, item: dict[str, Any] | None = None,
                 action: str = "", components: list[str] | None = None, area: str = "") -> dict[str, Any]:
    """Pre-dispatch evaluation (doc trigger #1, optional): the relevant context + execution constraints.

    Returns the exact ``pidl_context`` + ``execution_policy`` a worker's execution contract carries. Read-only;
    the scheduler still decides whether/when the work runs.
    """
    comps = [str(c) for c in (components or [])]
    if item and not comps:
        comps = [str(c) for c in (item.get("affected_components") or [])]
    act = action or str((item or {}).get("title") or (item or {}).get("body") or "")
    ctx = resolve_context(scope, project, task=item, action=act, components=comps, area=area)
    d = decide(scope, project, task=item, action=act, components=comps, area=area)
    return {
        "scope": scope, "project": project or "", "item_id": str((item or {}).get("id") or ""),
        "pidl_context": {"profile_version": ctx["profile_version"],
                         "applicable_rules": ctx["applicable_rules"],
                         "applicable_principles": ctx["applicable_principles"],
                         "applicable_preferences": ctx["applicable_preferences"],
                         "review_lenses": ctx["review_lenses"]},
        "execution_policy": ctx["execution_policy"],
        "decision": d["decision"], "consequential": ctx["consequential"],
        "recommendation": d["recommendation"],
    }


def synthesize(scope: str = "product_forge", project: str | None = None, *, results: list[dict[str, Any]] | None = None,
               item_id: str = "", action: str = "", area: str = "") -> dict[str, Any]:
    """Cross-worker synthesis gate (doc trigger #3): evaluate combined parallel results for consistency.

    Detects status disagreement and path overlap (reusing ``scheduler.path_overlap``); returns the decision
    contract plus a synthesis summary. ``CORRECT`` when conflicting, ``REVIEW`` when incomplete, else
    ``AUTO_PROCEED``. Read-only.
    """
    res = list(results or [])
    conflicts: list[dict[str, Any]] = []
    paths_by: list[tuple[str, list[str]]] = []
    for r in res:
        ps = [str(p) for p in (r.get("paths") or r.get("affected_components") or [])]
        paths_by.append((str(r.get("item_id") or r.get("id") or ""), ps))
    try:
        from core import scheduler
        for i in range(len(paths_by)):
            for j in range(i + 1, len(paths_by)):
                if paths_by[i][1] and scheduler.path_overlap(paths_by[i][1], paths_by[j][1]):
                    conflicts.append({"kind": "path_overlap", "a": paths_by[i][0], "b": paths_by[j][0]})
    except Exception:
        pass
    oks = [bool(r.get("ok", True)) for r in res]
    if res and len(set(oks)) > 1:
        conflicts.append({"kind": "status_disagreement"})
    agg_ok = all(oks) if oks else True
    agg = {"ok": agg_ok, "status": "pr_ready" if agg_ok else "mixed", "synthesis": True}
    d = decide(scope, project, result=agg, conflicts=conflicts, action=action or "synthesis", area=area)
    d["item_id"] = str(item_id or "")
    d["synthesis"] = {
        "results": [{"item_id": str(r.get("item_id") or r.get("id") or ""),
                     "ok": bool(r.get("ok", True)), "status": str(r.get("status") or "")} for r in res],
        "consistent": not conflicts, "conflicts": conflicts,
    }
    return d


def consequential_gate(scope: str = "product_forge", project: str | None = None, *, action: str = "",
                       components: list[str] | None = None, area: str = "",
                       item_id: str = "") -> dict[str, Any]:
    """Before-consequential-action gate (doc trigger #4): APPROVAL_REQUIRED when consequential, else AUTO."""
    ctx = resolve_context(scope, project, action=action, components=components, area=area)
    d = decide(scope, project, action=action, components=components, area=area)
    d["item_id"] = str(item_id or "")
    d["consequential"] = ctx["consequential"]
    return d


# ── PIDL-5 (BI-PF-0380): approval policy + versioned trace + outcome/correction feedback ──
def approval_policy(action: str = "", area: str = "", components: list[str] | None = None) -> dict[str, Any]:
    """Centralized approval policy (config/approval-policy.json): does this action require approval?"""
    try:
        with open(_APPROVAL_PATH, encoding="utf-8-sig") as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}
    default = cfg.get("default") or {"requires_approval": False, "approver": "operator",
                                     "escalation_allowed": True}
    hay = _text(action, area, *(components or []))
    for r in (cfg.get("rules") or []):
        m = r.get("match") or {}
        kws = [str(k).lower() for k in (m.get("keywords") or [])]
        ars = [str(a).lower() for a in (m.get("areas") or [])]
        if (kws and any(k in hay for k in kws)) or (ars and any(a in hay for a in ars)):
            return {"required": bool(r.get("requires_approval", True)),
                    "policy": {"version": cfg.get("version"), "rule": r.get("id")},
                    "approver": r.get("approver") or default.get("approver"),
                    "escalation_allowed": bool(default.get("escalation_allowed", True))}
    return {"required": bool(default.get("requires_approval", False)),
            "policy": {"version": cfg.get("version"), "rule": ""},
            "approver": default.get("approver"),
            "escalation_allowed": bool(default.get("escalation_allowed", True))}


def _trace_path(path: str | None = None) -> str:
    return path or _TRACE_DEFAULT


def _read_trace(path: str | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with open(_trace_path(path), encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if ln:
                    with contextlib.suppress(Exception):
                        out.append(json.loads(ln))
    except Exception:
        pass
    return out


def _append_trace(rec: dict[str, Any], path: str | None = None) -> None:
    p = _trace_path(path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def record_decision(decision: dict[str, Any], *, scope: str = "product_forge", project: str | None = None,
                    item_id: str = "", task_revision: int = 0, outcome: str = "",
                    path: str | None = None) -> dict[str, Any]:
    """Append a versioned decision to the trace (single writer). Returns the recorded row."""
    d = dict(decision or {})
    iid = str(item_id or d.get("item_id") or "")
    version = 1 + sum(1 for r in _read_trace(path) if str(r.get("item_id") or "") == iid) if iid else 1
    rec = {
        "decision_id": f"PIDL-{iid or 'G'}-{version:04d}",
        "at": datetime.now().isoformat(),
        "scope": scope, "project": project or "", "item_id": iid, "task_revision": int(task_revision or 0),
        "worker_id": str(d.get("worker_id") or ""), "runtime": str(d.get("runtime") or ""),
        "pidl_profile_version": d.get("pidl_profile_version"),
        "decision": d.get("decision") or {}, "confidence": d.get("confidence") or {},
        "risk": d.get("risk"), "evidence": d.get("evidence") or [],
        "conflicts": d.get("conflicts") or [], "approval": d.get("approval") or {},
        "next_action": d.get("next_action"), "run_id": str(d.get("run_id") or ""),
        "decision_version": version, "outcome": outcome or "",
    }
    _append_trace(rec, path)
    return rec


def history(scope: str = "", project: str = "", item_id: str = "", limit: int = 50,
            path: str | None = None) -> list[dict[str, Any]]:
    """Read the decision trace (filtered). Newest last, capped at ``limit``."""
    rows = [r for r in _read_trace(path)
            if (not scope or r.get("scope") == scope)
            and (not project or r.get("project") == project)
            and (not item_id or r.get("item_id") == item_id)]
    return rows[-int(limit or 50):]


def get(decision_id: str, path: str | None = None) -> dict[str, Any] | None:
    for r in _read_trace(path):
        if r.get("decision_id") == decision_id:
            return r
    return None


def latest(item_id: str, path: str | None = None) -> dict[str, Any] | None:
    rows = [r for r in _read_trace(path) if r.get("item_id") == item_id and r.get("kind") != "outcome"]
    return rows[-1] if rows else None


def record_outcome(decision_id: str, outcome: str = "", corrections: list[str] | None = None,
                   by: str = "", path: str | None = None) -> dict[str, Any]:
    """Record an outcome/correction. Corrections become evidence-gated CANDIDATES (never rules)."""
    corr = [str(c) for c in (corrections or []) if str(c).strip()]
    proposed: list[str] = []
    for c in corr:
        try:
            from core import learning_synth
            r = learning_synth.add_candidate(c, source_ref=str(decision_id), rationale="PIDL correction feedback")
            if r.get("ok"):
                proposed.append(str((r.get("candidate") or {}).get("id") or ""))
        except Exception:
            pass
    rec = {"decision_id": str(decision_id), "at": datetime.now().isoformat(), "kind": "outcome",
           "outcome": str(outcome or ""), "corrections": corr, "by": str(by or ""),
           "proposed_candidates": proposed}
    _append_trace(rec, path)
    return rec


def record_approval(decision_id: str, approved: bool, by: str = "operator", reason: str = "",
                    path: str | None = None) -> dict[str, Any]:
    """Record an authenticated approve/reject against a decision (append-only)."""
    rec = {"decision_id": str(decision_id), "at": datetime.now().isoformat(), "kind": "approval",
           "approved": bool(approved), "by": str(by or ""), "reason": str(reason or "")}
    _append_trace(rec, path)
    return rec


def feedback_candidates(status: str = "proposed") -> list[dict[str, Any]]:
    """Learning candidates proposed from PIDL corrections (evidence-gated; promote via learning_synth)."""
    try:
        from core import learning_synth
        return learning_synth.list_candidates(status=status)
    except Exception:
        return []


def render_context(ctx: dict[str, Any], max_chars: int = 1200) -> str:
    """A compact, bounded text block for prompt/contract injection (only the relevant subset)."""
    lines = [f"pidl profile_version={ctx.get('profile_version')}"]
    if ctx.get("applicable_rules"):
        lines.append("rules: " + "; ".join(str(r.get("name")) for r in ctx["applicable_rules"]))
    if ctx.get("applicable_principles"):
        lines.append("principles: " + "; ".join(str(p.get("name")) for p in ctx["applicable_principles"][:8]))
    if ctx.get("applicable_preferences"):
        lines.append("preferences: " + "; ".join(str(p.get("value")) for p in ctx["applicable_preferences"][:8]))
    if ctx.get("review_lenses"):
        lines.append("review_lenses: " + ", ".join(ctx["review_lenses"]))
    pol = ctx.get("execution_policy") or {}
    lines.append(f"execution_policy: autonomy={pol.get('autonomy')} approval_required={pol.get('approval_required')}")
    return "\n".join(lines)[:max_chars]
