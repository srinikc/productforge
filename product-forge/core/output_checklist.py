"""
Generic output checklist (generalizes the architect-only completeness check).

Per agent, define **essential** and **recommended** required sections (fuzzy
heading match). Missing an essential section fails compliance; a missing
recommended section is a warning. Reusable for any agent whose document must
follow a fixed structure.
"""
import os
import re
from typing import Dict, List, Optional

from core import id_index

_HEADING_RE = re.compile(r"^[ \t]{0,3}#{1,6}[ \t]+(.*)$", re.MULTILINE)
# Per-feature sections: "## F-1: <name>" (1-3 leading #). The gate for flat docs.
_PER_FEATURE_RE = re.compile(r"^[ \t]{0,3}#{1,3}[ \t]*F-\d+", re.MULTILINE)
# Keys whose keywords may appear in body text (not only as a heading).
_TEXT_MATCH_KEYS = {"per_feature", "functional"}

# ── FR/NFR/US id integrity (deterministic post-merge gate) ────────────────
# Any occurrence of a requirement id.
_ID_RE = re.compile(r"\b(FR|NFR|US)-(\d+)\b")
# A *definition*: the id leads a heading / bullet / numbered line (after
# optional bold), e.g. "- **FR-1:** ...", "FR-1: ...", "### FR-2 -".
# Mid-line mentions ("Links: FR-1", "traced to FR-1") are references only.
_DEF_RE = re.compile(
    r"^[ \t]{0,6}(?:#{1,6}[ \t]+|[-*+][ \t]+|\d+\.[ \t]+)?\**[ \t]*(FR|NFR|US)-(\d+)\b",
    re.MULTILINE)
# A per-feature heading (group 1 = level, group 2 = fid).
_FEATURE_HEAD_RE = re.compile(r"^[ \t]{0,3}(#{1,6})[ \t]*(F-\d+)\b", re.MULTILINE)
# Any heading + its level (section-boundary detection).
_HEADING_LEVEL_RE = re.compile(r"^[ \t]{0,3}(#{1,6})[ \t]+", re.MULTILINE)

# ── Spec id families: GLOBAL (unique across the spec, windowed per feature)
# vs LOCAL (per-feature scoped; every feature file restarts at -1) ───────────
# Single reader: id_families() -> config/spec-id-families.json (defaults on miss).
_DEFAULT_FAMILIES = {
    "global": ["FR", "NFR", "US"],
    "feature_id": "F",
    "local": ["AC", "BR", "EC", "V", "EH", "E", "API", "VA", "EDS", "OQ"],
    "local_default": True,
}
_FAMILIES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "spec-id-families.json")
_FAMILIES_CACHE = None


def id_families(path: Optional[str] = None) -> Dict:
    """Single reader for config/spec-id-families.json — delegates to core.id_index
    so every consumer shares ONE definition of the id families.

    GLOBAL ids are unique across the WHOLE spec (windowed per feature).
    LOCAL ids are scoped to a single feature file and MAY repeat across
    features. Unknown prefixes are treated as LOCAL when local_default.
    """
    global _FAMILIES_CACHE
    if path is None and _FAMILIES_CACHE is not None:
        return _FAMILIES_CACHE
    cfg = id_index.families(path)
    cfg = {k: (list(v) if isinstance(v, list) else v) for k, v in cfg.items()}
    cfg["global"] = [str(x).upper() for x in (cfg.get("global") or []) if str(x).strip()]
    cfg["local"] = [str(x).upper() for x in (cfg.get("local") or []) if str(x).strip()]
    if cfg.get("feature_id"):
        cfg["feature_id"] = str(cfg["feature_id"]).upper()
    if path is None:
        _FAMILIES_CACHE = cfg
    return cfg


def _prefix_alt(prefixes) -> str:
    """"A|BC|D" longest-first so "EC" wins over "E" (never an empty alt)."""
    vals = sorted({str(p).upper() for p in (prefixes or []) if str(p).strip()},
                  key=len, reverse=True)
    return "|".join(vals)


def _id_re(prefixes):
    alt = _prefix_alt(prefixes)
    if not alt:
        return re.compile(r"$^")
    return re.compile(r"\b(" + alt + r")-(\d+)\b")


def _def_re(prefixes, wide: bool = False):
    """A *definition* line (heading / bullet / numbered / bold). `wide` also
    accepts the leading table cell `| AC-1 |`, used by LOCAL families."""
    alt = _prefix_alt(prefixes)
    if not alt:
        return re.compile(r"$^")
    lead = r"\|?[ \t]*" if wide else ""
    return re.compile(
        r"^[ \t]{0,6}" + lead +
        r"(?:#{1,6}[ \t]+|[-*+][ \t]+|\d+\.[ \t]+)?\**[ \t]*(" +
        alt + r")-(\d+)\b",
        re.MULTILINE)


def _table_def_re(prefixes):
    """A table row whose FIRST cell is EXACTLY the id — a table-style definition
    (``| FR-1 | … |`` or ``| **FR-1** | … |``). A row like ``| FR-1 Activation | … |``
    (id + text in the same cell, e.g. a priority table) is a reference, not a def."""
    alt = _prefix_alt(prefixes)
    if not alt:
        return re.compile(r"$^")
    return re.compile(r"^[ \t]*\|[ \t]*\**[ \t]*(" + alt + r")-(\d+)[ \t]*\**[ \t]*\|",
                      re.MULTILINE)


def _iter_defs(text, prefixes):
    """Yield (prefix, num) for every definition — heading-style AND table-style."""
    for m in _def_re(prefixes).finditer(text or ""):
        yield m.group(1), m.group(2)
    for m in _table_def_re(prefixes).finditer(text or ""):
        yield m.group(1), m.group(2)


def _count_definitions(text, prefixes):
    """{id: count} across heading-style AND table-style definitions.

    An id counts as a duplicate only if it is defined more than once in the SAME
    style (heading twice, or first-cell table row twice); a heading + a summary
    table row for the same id is the normal merged-doc shape, not a duplicate.
    """
    head, tab = {}, {}
    for m in _def_re(prefixes).finditer(text or ""):
        k = f"{m.group(1)}-{m.group(2)}"
        head[k] = head.get(k, 0) + 1
    for m in _table_def_re(prefixes).finditer(text or ""):
        k = f"{m.group(1)}-{m.group(2)}"
        tab[k] = tab.get(k, 0) + 1
    out = {}
    for k in set(head) | set(tab):
        out[k] = max(head.get(k, 0), tab.get(k, 0))
    return out

# agent -> {"essential": {key: [keywords]}, "recommended": {key: [keywords]}}
REQUIRED: Dict[str, Dict[str, Dict[str, List[str]]]] = {
    "architect": {
        "essential": {
            "architecture_style": ["architecture style", "architectural style", "architecture overview"],
            "tech_stack": ["tech stack", "technology stack", "technologies", "stack"],
            "components": ["component", "module", "interface view", "modules"],
            "security": ["security", "threat", "authentication"],
            "adrs": ["adr", "architecture decision"],
        },
        "recommended": {
            "file_structure": ["file structure", "directory structure", "project structure",
                               "folder structure", "repository structure", "layout", "file layout"],
            "data_model": ["data model", "database", "entities", "entity", "schema", "data layer",
                           "data store", "persistence", "data management"],
            "deployment": ["deploy", "infrastructure", "hosting", "operations",
                           "runtime environment", "ci/cd"],
            "integration": ["integration", "external interface", "interfaces", "interoperability",
                            "external systems", "api design"],
        },
    },
    "design": {
        "essential": {
            "per_feature": ["f-1", "f-2", "per-feature", "feature f-"],
            "functional": ["behaviour", "behavior", "business rule", "validation",
                           "edge case", "acceptance criteri"],
            "functional_requirements": ["functional requirement"],
            "non_functional_requirements": ["non-functional", "nonfunctional"],
            "user_stories": ["user stor"],
            "api_contracts": ["api contract", "api design", "api endpoints"],
        },
        "recommended": {
            "design_direction": ["design direction", "design system", "visual design"],
            "components": ["component"],
            "data_models": ["data model", "schema", "entities"],
        },
    },
    "ideation": {
        "essential": {
            "vision": ["vision"],
            "features": ["feature"],
            "success_criteria": ["success criteri"],
        },
        "recommended": {
            "target_users": ["target user", "persona"],
            "workflow": ["workflow", "journey", "user flow"],
            "risks": ["risk"],
        },
    },
    "product-design-spec": {
        "essential": {
            "per_feature": ["f-1", "f-2", "per-feature", "feature f-"],
            "diagrams": ["state diagram", "stateDiagram", "sequence diagram",
                         "erDiagram", "mermaid"],
            "api_contracts": ["api contract", "api endpoints", "endpoint"],
            "test_plan": ["test plan", "tests:"],
            "traceability": ["traceab", "FR-", "NFR-"],
        },
        "recommended": {
            "screens": ["screen", "page"],
            "flows": ["flow", "journey"],
            "components": ["component"],
            "states": ["state"],
            "data": ["data", "model", "schema"],
        },
    },
}


def _read(paths: List[str]) -> str:
    text = ""
    for p in paths or []:
        try:
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                text += f.read() + "\n"
        except Exception:
            pass
    return text


def _match(groups: Dict[str, List[str]], headings: List[str], text: str = ""):
    present, missing = [], []
    low_text = (text or "").lower()
    for key, keywords in groups.items():
        kws = [str(k).lower() for k in keywords]
        # per_feature: a heading like "## F-1: ..." (>=1) OR the keyword list.
        if key == "per_feature":
            hit = bool(_PER_FEATURE_RE.search(text or "")) or \
                any(any(k in h for k in kws) for h in headings) or \
                any(k in low_text for k in kws)
            (present if hit else missing).append(key)
            continue
        hit = any(any(k in h for k in kws) for h in headings)
        if not hit and key in _TEXT_MATCH_KEYS:
            hit = any(k in low_text for k in kws)
        (present if hit else missing).append(key)
    return present, missing


def has_checklist(agent_id: str) -> bool:
    if agent_id in REQUIRED:
        return True
    try:
        from core.agent_requirements import required_sections
        return bool(required_sections(agent_id))
    except Exception:
        return False


def _spec_for(agent_id: str) -> Dict:
    try:
        from core.agent_requirements import required_sections
        cfg = required_sections(agent_id)
        if cfg:
            return cfg
    except Exception:
        pass
    return REQUIRED.get(agent_id, {})



def _feature_sections(text):
    """[(fid, section_text)] — a feature block ends at the next heading of the
    same or higher level (mirrors agent_runner._parse_per_feature_sections)."""
    text = text or ""
    all_heads = [(m.start(), len(m.group(1))) for m in _HEADING_LEVEL_RE.finditer(text)]
    out = []
    for m in _FEATURE_HEAD_RE.finditer(text):
        pos, level, fid = m.start(), len(m.group(1)), m.group(2)
        end = len(text)
        for hpos, hlevel in all_heads:
            if hpos > pos and hlevel <= level:
                end = hpos
                break
        out.append((fid, text[pos:end]))
    return out


def _allocation_from_text(text, prefixes):
    """Per-feature id ranges derived from the ACTUAL ids (running-number scheme).

    Each feature owns the ids it defines, so a range is ``min..max`` of that
    feature's ids per family. With running numbers the ranges are contiguous in
    plan order; ``check_id_integrity`` verifies that invariant separately.
    """
    alloc: Dict[str, Dict[str, tuple]] = {}
    for fid, section in _feature_sections(text):
        entry = {}
        for prefix in prefixes:
            nums = [int(m.group(2)) for m in _table_def_re([prefix]).finditer(section)]
            nums += [int(m.group(2)) for m in _def_re([prefix]).finditer(section)]
            if nums:
                entry[prefix] = (min(nums), max(nums))
        if entry:
            alloc[fid] = entry
    return alloc


def check_id_integrity(text, allocation=None, block_sizes=None, families=None):
    """Deterministic GLOBAL (FR/NFR/US) id gate over MERGED spec content.

    FAILS when:
      * a GLOBAL requirement id is DEFINED more than once (duplicate definition),
      * a defined id falls outside every allocated range, or outside its own
        feature's block (cross-feature collision),
      * a GLOBAL id is referenced somewhere but never defined.
    """
    text = text or ""
    fam = families or id_families()
    _global_prefixes = [str(p).upper() for p in (fam.get("global") or [])
                        if str(p).strip()]
    _global_def_re = _def_re(_global_prefixes)
    _global_id_re = _id_re(_global_prefixes)
    _derived = allocation is None
    if allocation is None:
        # Derive per-feature ranges from the ACTUAL ids (running-number scheme), so
        # the gate never flags the current contiguous numbering as out-of-range.
        allocation = _allocation_from_text(text, _global_prefixes)
    allocation = dict(allocation or {})

    defs = _count_definitions(text, _global_prefixes)
    duplicates = sorted(k for k, c in defs.items() if c > 1)
    defined = set(defs)
    all_ids = {f"{m.group(1)}-{m.group(2)}" for m in _global_id_re.finditer(text)}
    undefined_refs = sorted(all_ids - defined)

    ranges_by_prefix = {}
    for _fid, entry in allocation.items():
        for prefix, rng in (entry or {}).items():
            try:
                ranges_by_prefix.setdefault(prefix, set()).add((int(rng[0]), int(rng[1])))
            except Exception:
                continue

    def _in_ranges(prefix, num):
        try:
            n = int(num)
        except Exception:
            return True
        return any(lo <= n <= hi for (lo, hi) in ranges_by_prefix.get(prefix, ()))

    out_of_range = []
    if ranges_by_prefix:
        for key in sorted(defined):
            prefix, _, num = key.partition("-")
            if not _in_ranges(prefix, num):
                out_of_range.append(key)
    for fid, section in _feature_sections(text):
        entry = allocation.get(fid) or {}
        for prefix, num in _iter_defs(section, _global_prefixes):
            rng = entry.get(prefix)
            try:
                outside = bool(rng) and not (int(rng[0]) <= int(num) <= int(rng[1]))
            except Exception:
                outside = False
            if outside:
                key = f"{prefix}-{num}"
                if key not in out_of_range:
                    out_of_range.append(key)
    out_of_range = sorted(set(out_of_range))

    issues = []
    if duplicates:
        issues.append(f"duplicate requirement ids: {duplicates}")
    if out_of_range:
        issues.append(f"ids outside allocated ranges: {out_of_range}")
    if undefined_refs:
        issues.append(f"referenced but never defined: {undefined_refs}")
    if _derived:
        # Running-number invariant: per-feature ranges must be contiguous in order.
        for _pfx in _global_prefixes:
            _spans = sorted((e[_pfx] for e in allocation.values() if e.get(_pfx)),
                            key=lambda r: r[0])
            for _a, _b in zip(_spans, _spans[1:]):
                if _b[0] != _a[1] + 1:
                    issues.append(f"{_pfx} ranges not contiguous: {tuple(_a)} -> {tuple(_b)}")
                    break
    return {
        "ok": not issues,
        "duplicates": duplicates,
        "out_of_range": out_of_range,
        "undefined_refs": undefined_refs,
        "defined": sorted(defined),
        "allocation": {k: {p: list(v) for p, v in (e or {}).items()}
                       for k, e in allocation.items()},
        "issues": issues,
    }


LOCAL_INAPPLICABLE = {"ok": True, "local_duplicates": [],
                      "local_undefined_refs": [], "issues": []}


def check_local_id_integrity(text, families=None) -> Dict:
    """Per-feature LOCAL id gate (AC/BR/EC/V/EH/E/... ).

    LOCAL ids are scoped to ONE feature section:
      * within a section they must be DEFINED at most once (duplicate in the
        SAME feature => fail, listing prefix+id+feature),
      * every LOCAL id REFERENCED in a section must be DEFINED in that same
        section (undefined local reference => fail).
    The same id MAY repeat in a DIFFERENT feature section.
    """
    text = text or ""
    fam = families or id_families()
    local_prefixes = [str(p).upper() for p in (fam.get("local") or [])
                      if str(p).strip()]
    if not local_prefixes:
        return dict(LOCAL_INAPPLICABLE)
    id_re = _id_re(local_prefixes)
    def_re = _def_re(local_prefixes, wide=True)
    local_duplicates, local_undefined = [], []
    for fid, section in _feature_sections(text):
        defs = {}
        for m in def_re.finditer(section):
            key = f"{m.group(1)}-{m.group(2)}"
            defs[key] = defs.get(key, 0) + 1
        for key, count in sorted(defs.items()):
            if count > 1:
                local_duplicates.append(f"{key} in {fid}")
        defined = set(defs)
        refs = {f"{m.group(1)}-{m.group(2)}" for m in id_re.finditer(section)}
        for key in sorted(refs - defined):
            local_undefined.append(f"{key} in {fid}")
    issues = []
    if local_duplicates:
        issues.append(f"duplicate local ids within a feature: {local_duplicates}")
    if local_undefined:
        issues.append("local ids referenced but not defined in their feature: "
                      f"{local_undefined}")
    return {
        "ok": not issues,
        "local_duplicates": local_duplicates,
        "local_undefined_refs": local_undefined,
        "issues": issues,
    }


def check_id_integrity_all(text, allocation=None, block_sizes=None, families=None) -> Dict:
    """GLOBAL (FR/NFR/US) rules PLUS per-feature LOCAL rules, merged.

    Returns the same shape as check_id_integrity() plus
    `local_duplicates` / `local_undefined_refs`, so a failure follows the
    existing checklist re-run / compliance path.
    """
    fam = families or id_families()
    result = check_id_integrity(text, allocation=allocation,
                                block_sizes=block_sizes, families=fam)
    local = check_local_id_integrity(text, families=fam)
    result["local_duplicates"] = local.get("local_duplicates", [])
    result["local_undefined_refs"] = local.get("local_undefined_refs", [])
    issues = list(result.get("issues") or [])
    issues.extend(local.get("issues") or [])
    result["issues"] = issues
    result["ok"] = not issues
    return result


def check(agent_id: str, paths: List[str], allocation: Optional[Dict] = None) -> Dict:
    """Check an agent's output against its essential/recommended sections.

    For per-feature agents (design / product-design-spec) this also enforces the
    deterministic FR/NFR/US id-integrity gate; a failure is folded into
    `essential_missing` so it follows the existing checklist failure path.
    """
    spec = _spec_for(agent_id)

    if not spec:
        return {"ok": True, "applicable": False, "had_content": False,
                "present": [], "essential_missing": [], "recommended_missing": [],
                "percent": 100.0, "total": 0}
    text = _read(paths)
    headings = [m.group(1).strip().lower() for m in _HEADING_RE.finditer(text)]
    present_e, missing_e = _match(spec.get("essential", {}), headings, text)
    present_r, missing_r = _match(spec.get("recommended", {}), headings, text)

    # Deterministic per-feature gate: PRESENT iff at least one heading is
    # "F-<n> ..." (e.g. "f-1: ...", "f-16: ...") or explicitly says
    # "per-feature". Decisive (fails the artifact) only for the configured
    # per-feature agents; advisory/no-op for every other agent.
    per_feature_present = any(re.match(r"^f-\d+", h) for h in headings) or \
        any("per-feature" in h for h in headings)
    if not per_feature_present:
        try:
            from core.agent_requirements import per_feature_agents
            decisive = agent_id in set(per_feature_agents())
        except Exception:
            decisive = agent_id in {"design", "product-design-spec"}
        if decisive and "per_feature" not in missing_e:
            missing_e = missing_e + ["per_feature"]

    # Deterministic FR/NFR/US id-integrity gate (per-feature agents only).
    id_integrity = None
    try:
        from core.agent_requirements import per_feature_agents as _pfa
        _is_per_feature = agent_id in set(_pfa())
    except Exception:
        _is_per_feature = agent_id in {"design", "product-design-spec"}
    if _is_per_feature and (text or "").strip():
        id_integrity = check_id_integrity_all(text, allocation=allocation)
        if not id_integrity.get("ok", True) and "requirement_ids" not in missing_e:
            missing_e = missing_e + ["requirement_ids"]

    present = present_e + present_r
    total = len(present_e) + len(missing_e) + len(present_r) + len(missing_r)
    return {
        "applicable": True,
        "present": present,
        "essential_missing": missing_e,
        "recommended_missing": missing_r,
        "missing": missing_e + missing_r,
        "percent": (len(present) / total * 100) if total else 0.0,
        "ok": len(missing_e) == 0,
        "had_content": bool(headings),
        "total": total,
        "id_integrity": id_integrity,
    }
