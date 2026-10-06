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
import json
import os
from typing import Any

from core.paths import ROOT

PROFILE_FILE = "pidl-profile.json"
_PROFILE_PATH = os.path.join(ROOT, "config", PROFILE_FILE)


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
    approval_required = bool(ctx["execution_policy"].get("approval_required"))

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
        "approval": {"required": approval_required, "policy": ctx["execution_policy"]},
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
