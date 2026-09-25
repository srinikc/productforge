"""
Tech Stack decision + knowledge mapping (framework-agnostic).

The ARCHITECT decides the stack; this module:
  - detects a requested stack from free text/config,
  - parses the architect's structured ``tech-stack`` JSON block,
  - loads/saves ``docs/tech-stack.json``,
  - maps a chosen stack -> knowledge layers (guideline files),
  - diffs the chosen stack against the user's request.
"""
import json
import os
import re
from typing import Dict, List, Optional


# canonical technology name -> knowledge layers (guideline files live in the
# compliance checker's LAYER_GUIDELINE_MAP)
LANG_LAYER = {
    "python": ["python"], "python3": ["python"],
    "typescript": ["typescript"], "javascript": ["typescript"], "ts": ["typescript"],
    "go": ["go"], "golang": ["go"],
}
FRAMEWORK_LAYER = {
    "fastapi": ["backend", "api"], "flask": ["backend", "api"], "django": ["backend", "api"],
    "express": ["backend", "api"], "nestjs": ["backend", "api"], "spring": ["backend", "api"],
    "react": ["frontend"], "nextjs": ["frontend"], "next.js": ["frontend"],
    "vue": ["frontend"], "angular": ["frontend"], "svelte": ["frontend"],
}
DB_LAYER = {
    "postgresql": ["database"], "postgres": ["database"], "mysql": ["database"],
    "mongodb": ["database"], "sqlite": ["database"], "sqlalchemy": ["database"],
}
CACHE_LAYER = {"redis": ["caching"], "memcached": ["caching"]}
DEPLOY_LAYER = {"docker": ["packaging"], "kubernetes": ["packaging"], "pip": ["packaging"]}

KNOWN_TECHS = sorted(set(list(LANG_LAYER) + list(FRAMEWORK_LAYER) + list(DB_LAYER)
                         + list(CACHE_LAYER) + list(DEPLOY_LAYER)))

WEB_MARKERS = set(FRAMEWORK_LAYER) | {"rest", "graphql", "http", "web", "server"}


# Technologies whose names are also common English words or too short to match
# safely (BI-0078): only count them when they appear in an explicit tech context.
_AMBIGUOUS_TECHS = {"go", "react", "vue", "angular", "spring", "express",
                    "rest", "web", "server"}
# Aliases too short/ambiguous for substring detection - use the full name instead.
_SKIP_ALIASES = {"ts", "js"}
_CTX_BEFORE = (r"(?:\bin\b|\busing\b|\bwith\b|\bvia\b|\bwritten in\b|"
               r"\bbuilt (?:in|with|using)\b|\bcoded in\b|\bstack\b|\blanguage\b|"
               r"\bframework\b|\bruntime\b|\bon\b)\s+")
_CTX_AFTER = (r"\s+(?:language|framework|stack|app|application|server|backend|"
              r"runtime|api|project)\b")


def detect_tech_from_text(text: str) -> List[str]:
    """Find known technologies mentioned in free text (idea/description).

    Conservative: English-word collisions (e.g. "go", "react", "rest") only match
    in explicit technology context, so prose like "go through the feature" does not
    select Go (BI-0078).
    """
    if not text:
        return []
    low = text.lower()
    found = []
    for tech in KNOWN_TECHS:
        if tech in _SKIP_ALIASES:
            continue
        pat = r"\b" + re.escape(tech) + r"\b"
        if tech in _AMBIGUOUS_TECHS:
            if re.search(_CTX_BEFORE + pat, low) or re.search(pat + _CTX_AFTER, low):
                found.append(tech)
        elif re.search(pat, low):
            found.append(tech)
    return sorted(set(found))


def _norm(items) -> List[str]:
    if not items:
        return []
    if isinstance(items, str):
        items = [items]
    return [str(i).strip().lower() for i in items if str(i).strip()]


def stack_to_layers(chosen: Dict) -> List[str]:
    """Map a chosen tech-stack dict to knowledge layers."""
    layers: List[str] = []
    for lang in _norm(chosen.get("languages")):
        layers += LANG_LAYER.get(lang, [])
    for fw in _norm(chosen.get("frameworks")):
        layers += FRAMEWORK_LAYER.get(fw, [])
    layers += DB_LAYER.get((chosen.get("database") or "").strip().lower(), []) if chosen.get("database") else []
    layers += CACHE_LAYER.get((chosen.get("cache") or "").strip().lower(), []) if chosen.get("cache") else []
    layers += DEPLOY_LAYER.get((chosen.get("deploy") or "").strip().lower(), []) if chosen.get("deploy") else []
    seen, out = set(), []
    for l in layers:
        if l not in seen:
            seen.add(l)
            out.append(l)
    return out


def is_web_stack(chosen: Dict) -> bool:
    if not chosen:
        return False
    blob = " ".join(_norm(chosen.get("frameworks")) + [str(chosen.get("kind", "")).lower()])
    return any(m in blob for m in WEB_MARKERS)


def parse_tech_stack_block(text: str) -> Optional[Dict]:
    """Extract the architect's ```json tech-stack block (object with 'kind')."""
    for m in re.finditer(r"```json\s*(\{.*?\})\s*```", text or "", re.DOTALL | re.IGNORECASE):
        try:
            obj = json.loads(m.group(1))
        except Exception:
            continue
        if isinstance(obj, dict) and ("kind" in obj or "languages" in obj or "chosen" in obj):
            return obj
    return None


def build_decision(requested: List[str], chosen: Dict, rationale: str = "") -> Dict:
    """Build/normalize a tech-stack decision record."""
    req = _norm(requested)
    ch = chosen or {}
    chosen_langs = set(_norm(ch.get("languages")))
    chosen_fw = set(_norm(ch.get("frameworks")))
    req_set = set(req)
    req_blob = " ".join(req)
    req_has_web = any(m in req_blob for m in WEB_MARKERS)
    # A change occurs if a requested item is dropped, OR the architect introduces
    # a web stack the user did not ask for.
    changed = bool(req) and (
        not req_set.issubset(chosen_langs | chosen_fw)
        or (not req_has_web and is_web_stack(ch))
    )
    return {
        "requested": req,
        "chosen": ch,
        "source": "user" if (req and not changed) else "architect",
        "changed_from_request": changed,
        "rationale": rationale,
        "approved_by": None,
        "approved_at": None,
    }


def load_tech_stack(project_dir: str) -> Dict:
    path = os.path.join(project_dir, "docs", "tech-stack.json")
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_tech_stack(project_dir: str, data: Dict) -> str:
    path = os.path.join(project_dir, "docs", "tech-stack.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path
