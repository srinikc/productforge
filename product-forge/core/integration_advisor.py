"""
Integration advisor (pipeline intelligence).

Reads the project's context (product kind, domain, stack, requirements) and
RECOMMENDS which optional integrations to enable — with a plain-language reason
and clear options — so HIL only confirms, never has to understand flags.

Outputs:
  products/<project>/recommendations.json     (machine; read by feature_flags)
  products/<project>/docs/qa/integration-recommendations.md  (human)
"""
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_DOMAINS = {
    "fintech": ("fintech", "payment", "pci", "bank", "wallet", "trading", "lending"),
    "healthcare": ("healthcare", "hipaa", "patient", "medical", "clinic", "ehr"),
    "ecommerce": ("ecommerce", "e-commerce", "cart", "checkout", "marketplace", "storefront"),
    "social": ("social network", "community", "followers", "timeline", "newsfeed", "social feed"),
    "media": ("image", "video", "audio", "stream", "media", "photo"),
    "gov": ("government", "gov", "public sector", "citizen"),
    "data": ("analytics", "etl", "warehouse", "pipeline", "dataset", "bi"),
}


def _read(project_dir: str, *rels) -> str:
    out = ""
    for r in rels:
        p = os.path.join(project_dir, r)
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    out += f.read() + "\n"
            except Exception:
                pass
    return out


def _detect_domain(project_dir: str, project_cfg: Dict, tech: Dict, text: str) -> str:
    blob = " ".join([
        str(project_cfg.get("product_domain") or ""),
        str(project_cfg.get("business_model") or ""),
        str((tech.get("chosen") or {}).get("domain") or ""),
        text.lower(),
    ]).lower()
    for domain, keys in _DOMAINS.items():
        if any(k in blob for k in keys):
            return domain
    return ""


def _open_defects(project: str) -> int:
    try:
        from core.defect_loop import open_defects
        return len(open_defects(project))
    except Exception:
        return 0


def recommend(project_dir: str, project: Optional[str] = None) -> Dict[str, Any]:
    project = project or os.path.basename(os.path.normpath(project_dir))
    project_cfg = {}
    try:
        with open(os.path.join(project_dir, "project.json"), "r", encoding="utf-8") as f:
            project_cfg = json.load(f) or {}
    except Exception:
        pass
    tech = {}
    try:
        with open(os.path.join(project_dir, "docs", "tech-stack.json"), "r", encoding="utf-8") as f:
            tech = json.load(f) or {}
    except Exception:
        pass
    req_text = _read(project_dir, "docs/requirements.md", "docs/design.md",
                     "docs/architecture.md", "docs/product-plan.md")
    chosen = tech.get("chosen") or {}
    frameworks = [str(x) for x in (chosen.get("frameworks") or []) + (chosen.get("languages") or [])]
    domain = _detect_domain(project_dir, project_cfg, tech, req_text)
    fr = len(re.findall(r"\bFR[-_]?\d+\b", req_text, re.I))
    nfr = len(re.findall(r"\bNFR[-_]?\d+\b", req_text, re.I))
    open_def = _open_defects(project)
    needs_persistence = bool(re.search(r"\b(database|postgres|mysql|sqlite|redis|cache|queue|kafka|auth)\b",
                                       req_text + " " + json.dumps(chosen).lower(), re.I))

    flags: Dict[str, Dict[str, Any]] = {}

    def add(name, on, reason, options):
        flags[name] = {"enabled": bool(on), "reason": reason, "options": options,
                       "label": _LABEL.get(name, name)}

    add("techstack_guidelines", bool(frameworks),
        f"Your stack uses {', '.join(frameworks[:4])}." if frameworks else "No stack detected yet.",
        ["Enable (recommended)", "Skip"])
    add("business_skills",
        domain in ("fintech", "healthcare", "ecommerce", "social", "media", "gov"),
        (f"Domain '{domain}' implies specialised practices (security/compliance/UX)."
         if domain else "No regulated/specialised domain detected."),
        ["Enable", "Skip"])
    add("service_catalog", needs_persistence,
        ("Your requirements mention data storage/auth/queues, so infra choices matter."
         if needs_persistence else "No infrastructure services detected."),
        ["Enable", "Skip"])
    add("spec_llm",
        (len(req_text) > 4000 or (fr + nfr) >= 15),
        (f"Specs are large ({fr} FR / {nfr} NFR), so an AI spec review adds value."
         if (fr + nfr) >= 15 else "Specs are small/simple."),
        ["Enable", "Skip"])
    add("code_analyzer", open_def > 0,
        (f"{open_def} open defect(s) — a change-plan helper can speed fixes."
         if open_def else "No open defects; not needed unless fixes accumulate."),
        ["Enable", "Skip"])

    rec = {"project": project, "domain": domain, "frameworks": frameworks,
           "generated_at": datetime.now().isoformat(), "flags": flags}
    _persist(project_dir, rec)
    return rec


_LABEL = {
    "techstack_guidelines": "Stack-specific coding guidance",
    "business_skills": "Domain/business skill packs",
    "service_catalog": "Infrastructure service catalog",
    "spec_llm": "AI spec review",
    "code_analyzer": "Change-plan helper for fixes",
    "per_category": "Per-category test execution",
}

# One-line "what does this pack do" — shown as a legend so options aren't cryptic.
_DESC = {
    "techstack_guidelines": "adds stack-specific coding guidance to agent prompts (internal quality).",
    "business_skills": "adds domain/business skill packs (regulated-industry practices) — can shape the product/UX.",
    "service_catalog": "adds an infrastructure service catalog (DB/auth/queue choices) — can shape the product/UX.",
    "spec_llm": "adds an AI review of the specs before build (internal quality).",
    "code_analyzer": "adds a change-plan helper that speeds up fixes (internal quality).",
    "per_category": "runs tests per category (internal quality).",
}


def _enabled_names(choices: Dict[str, bool]) -> List[str]:
    return [_LABEL.get(n, n) for n, v in (choices or {}).items() if v]


def legend() -> List[str]:
    """Human-readable legend: each pack + what it does + whether it can change the product."""
    out = []
    for n, lbl in _LABEL.items():
        kind = RISK.get(n, "internal")
        tag = "can change product/UX" if kind != "internal" else "internal quality only"
        out.append(f"{lbl} — {_DESC.get(n, '')} ({tag})")
    return out


def _persist(project_dir: str, rec: Dict):
    try:
        with open(os.path.join(project_dir, "recommendations.json"), "w", encoding="utf-8") as f:
            json.dump(rec, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
    qa = os.path.join(project_dir, "docs", "qa")
    try:
        os.makedirs(qa, exist_ok=True)
        lines = [f"# Recommended integrations — {rec['project']}", "",
                 "The pipeline recommends these based on your product. Just confirm;",
                 "no technical detail needed.", ""]
        if rec.get("domain"):
            lines.append(f"- Detected domain: **{rec['domain']}**")
        lines.append("")
        lines.append("| Integration | Recommendation | Why | Options |")
        lines.append("|---|---|---|---|")
        for name, f_ in rec["flags"].items():
            lines.append(f"| {f_['label']} | {'ON' if f_['enabled'] else 'off'} | "
                         f"{f_['reason']} | {' / '.join(f_['options'])} |")
        with open(os.path.join(qa, "integration-recommendations.md"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except Exception:
        pass


def plain_summary(rec: Dict) -> str:
    lines = ["", "RECOMMENDED INTEGRATIONS (based on your project):"]
    for name, f_ in rec.get("flags", {}).items():
        mark = "ON " if f_["enabled"] else "off"
        kind = RISK.get(name, "internal")
        lines.append(f"  [{mark}] {f_['label']} ({kind}) — {f_['reason']}")
    return "\n".join(lines)


# Impact: `internal` = no effect on the shipped product/UX; `user_facing` = can.
RISK = {
    "techstack_guidelines": "internal",
    "spec_llm": "internal",
    "code_analyzer": "internal",
    "per_category": "internal",
    "business_skills": "user_facing",
    "service_catalog": "user_facing",
}


def choices_recommended(rec: Dict) -> Dict[str, bool]:
    return {n: bool(f["enabled"]) for n, f in rec.get("flags", {}).items()}


def choices_internal_only(rec: Dict) -> Dict[str, bool]:
    """Apply only internal (quality) items; skip anything user-facing."""
    return {n: (bool(f["enabled"]) if RISK.get(n, "internal") == "internal" else False)
            for n, f in rec.get("flags", {}).items()}


def needs_hil(rec: Dict) -> bool:
    """True when any *enabled* recommendation is user-facing (affects the product)."""
    for n, f in rec.get("flags", {}).items():
        if f.get("enabled") and RISK.get(n, "internal") != "internal":
            return True
    return False


def choices_all(rec: Dict) -> Dict[str, bool]:
    return {n: True for n in rec.get("flags", {})}


def choices_none(rec: Dict) -> Dict[str, bool]:
    return {n: False for n in rec.get("flags", {})}


def user_facing_flags(rec: Dict) -> Dict[str, Any]:
    """Only the flags that can change the shipped product (need the owner's consent)."""
    return {n: f for n, f in rec.get("flags", {}).items() if RISK.get(n, "internal") != "internal"}


def _internal_defaults(rec: Dict) -> Dict[str, bool]:
    """Internal (quality-only) flags — always applied at their recommended value."""
    return {n: bool(f.get("enabled")) for n, f in rec.get("flags", {}).items()
            if RISK.get(n, "internal") == "internal"}


def with_internal(rec: Dict, uf_choices: Dict[str, bool]) -> Dict[str, bool]:
    d = _internal_defaults(rec)
    d.update(uf_choices or {})
    return d


def hil_options(rec: Dict) -> List[Dict[str, Any]]:
    """Ask ONLY about product-shaping packs; internal packs are applied automatically."""
    uf = user_facing_flags(rec)
    on = [_LABEL.get(n, n) for n, f in uf.items() if f.get("enabled")]
    enable = with_internal(rec, {n: bool(f.get("enabled")) for n, f in uf.items()})
    skip = with_internal(rec, {n: False for n in uf})
    return [
        {"label": "Enable the product-shaping packs (recommended): "
                  + ("; ".join(on) if on else "none") +
                  "  [internal quality packs are applied automatically]", "choices": enable},
        {"label": "Skip the product-shaping packs (internal quality packs are still applied automatically)",
         "choices": skip},
    ]


def apply_choices(project_dir: str, rec: Dict, choices: Dict[str, bool]) -> Dict[str, Any]:
    """Persist HIL/auto decisions (integration_choices.json); overrides recommendation."""
    try:
        with open(os.path.join(project_dir, "integration_choices.json"), "w", encoding="utf-8") as f:
            json.dump({"project": rec.get("project"), "choices": choices,
                       "decided_at": datetime.now().isoformat()}, f, indent=2)
    except Exception:
        pass
    return choices


def apply_recommendation(project_dir: str, rec: Optional[Dict] = None) -> Dict[str, Any]:
    """Adopt the recommendation as the committed choices (auto mode)."""
    rec = rec or recommend(project_dir)
    return apply_choices(project_dir, rec, choices_recommended(rec))
