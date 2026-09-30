"""Capability-gated pipeline composition (BI-0213).

Given the ENABLED capability packs, produce the run's EFFECTIVE stage order + agent roster by
INSERTING optional stages (anchor-based, e.g. ``0f`` after ``0a``; ``4m`` after ``4-0``) and appending
pack agents/validators to existing stages (media-QA into ``5``/``6``).

Pure + in-memory: no store, no I/O, no side effects. A run with no (or only the ``none``) pack returns
the base definition UNCHANGED (byte-identical regression guard).

Reuses the existing skip mechanism (run_plan/plan_evaluator/pipeline_tailoring) — this module only ADDS;
it never removes required stages and never becomes a 4th enable path. See docs/PIPELINE-COMPOSITION-DESIGN.md.
"""

import copy
from typing import Dict, List, Optional

# the no-op pack keys: an enabled set that is empty or only these = identity
_NOOP_PACKS = {"", "none", "text"}


def _enabled_keys(project_dir: Optional[str] = None, packs: Optional[List[Dict]] = None) -> List[str]:
    if packs is not None:
        return [str(p if isinstance(p, str) else (p or {}).get("key") or (p or {}).get("modality") or "")
                for p in packs]
    if not project_dir:
        return []
    try:
        from core import capability_packs as _cp
        prof = _cp.load_profile(project_dir)
        return list(prof.get("enabled_packs") or [])
    except Exception:
        return []


def enabled_packs(project_dir: Optional[str] = None, packs: Optional[List[Dict]] = None) -> List[Dict]:
    """Enabled packs. When ``packs`` is given, use them verbatim (caller/test composed); else resolve
    the project's enabled_packs through the catalog."""
    if packs is not None:
        return [p for p in packs
                if isinstance(p, dict) and str(p.get("key") or p.get("modality") or "").lower() not in _NOOP_PACKS]
    keys = [k for k in _enabled_keys(project_dir) if k and k.lower() not in _NOOP_PACKS]
    out = []
    try:
        from core import capability_packs as _cp
        for k in keys:
            p = _cp.view(k)
            if p:
                out.append(p)
    except Exception:
        pass
    return out


def _insert_after(stages: Dict, new_id: str, anchor: str, spec: Dict) -> bool:
    """Insert ``new_id`` immediately after ``anchor`` (dict-order preserving). Returns ok."""
    if anchor not in stages or new_id in stages:
        return False
    keys = list(stages.keys())
    idx = keys.index(anchor)
    new_stage = {k: v for k, v in spec.items() if k not in ("id", "after")}
    new_stage.setdefault("ideal_flow", [])
    new_stage.setdefault("depends_on", [anchor])
    # rebuild dict with insertion at idx+1
    rebuilt = {}
    for i, k in enumerate(keys):
        rebuilt[k] = stages[k]
        if i == idx:
            rebuilt[new_id] = new_stage
    stages.clear()
    stages.update(rebuilt)
    return True


def _rewire_dependents(stages: Dict, anchor: str, new_id: str) -> None:
    """Stages that depended on the anchor should now depend on the inserted stage."""
    for sid, st in stages.items():
        if sid == new_id:
            continue
        deps = list(st.get("depends_on") or [])
        # only redirect if the anchor is a direct hard dep and the inserted stage sits right after it
        if anchor in deps:
            st["depends_on"] = [new_id if d == anchor else d for d in deps]


def effective_stages(base_def: Dict, pack_list: List[Dict], warnings: Optional[List[str]] = None) -> Dict:
    """Return a composed ``stages`` dict given enabled packs (anchor-insert). Pure."""
    stages = copy.deepcopy((base_def.get("stages") or {}))
    for p in pack_list:
        for spec in (p.get("stages") or []):
            sid = str(spec.get("id") or "")
            anchor = str(spec.get("after") or (spec.get("depends_on") or [""])[0] or "")
            if not sid or sid in stages:
                continue
            if anchor not in stages:
                if warnings is not None:
                    warnings.append(f"unknown anchor '{anchor}' for stage '{sid}' (skipped)")
                continue
            if not _insert_after(stages, sid, anchor, spec):
                if warnings is not None:
                    warnings.append(f"could not insert stage '{sid}' after '{anchor}'")
                continue
            _rewire_dependents(stages, anchor, sid)
    return stages


def effective_agents(base_roster: Dict, pack_list: List[Dict]) -> Dict:
    """Append pack agents/validators to their target stages' ideal_flow. base_roster: {stage_id: [agents]}."""
    roster = {k: list(v or []) for k, v in (base_roster or {}).items()}
    for p in pack_list:
        # pack.agents may be a flat list (applied to all media stages) or {stage_id: [agents]}
        agents = p.get("agents") or []
        targets = p.get("agent_stages") or p.get("stages_apply") or []
        if isinstance(agents, dict):
            for sid, ags in agents.items():
                roster.setdefault(sid, [])
                for a in ags:
                    if a not in roster[sid]:
                        roster[sid].append(a)
        elif agents and targets:
            for sid in targets:
                roster.setdefault(sid, [])
                for a in agents:
                    if a not in roster[sid]:
                        roster[sid].append(a)
        # validators -> media-QA hook stages (default 5,6)
        vals = p.get("validators") or []
        for sid in (p.get("validator_stages") or ["5", "6"]):
            if vals:
                roster.setdefault(sid, [])
                for v in vals:
                    if v not in roster[sid]:
                        roster[sid].append(v)
    return roster


def enabled_tools(pack_list: List[Dict]) -> List[str]:
    out: List[str] = []
    for p in pack_list:
        for t in (p.get("tools") or []):
            if t not in out:
                out.append(t)
    return out


def enabled_models(pack_list: List[Dict]) -> List[str]:
    out: List[str] = []
    for p in pack_list:
        for m in (p.get("models") or []):
            if m not in out:
                out.append(m)
    return out


def effective_definition(base_def: Dict, project_dir: Optional[str] = None,
                         packs: Optional[List[Dict]] = None) -> Dict:
    """Compose the effective pipeline definition. IDENTITY when no real pack is enabled."""
    pack_list = enabled_packs(project_dir, packs)
    if not pack_list:
        return base_def  # byte-identical regression guard: same object, no marker key
    warnings: List[str] = []
    composed = copy.deepcopy(base_def)
    composed["stages"] = effective_stages(base_def, pack_list, warnings)
    # roster append for stages that already exist
    roster = {sid: list((st or {}).get("ideal_flow") or [])
              for sid, st in (composed.get("stages") or {}).items()}
    merged = effective_agents(roster, pack_list)
    for sid, ags in merged.items():
        if sid in composed["stages"]:
            composed["stages"][sid]["ideal_flow"] = ags
    if warnings:
        composed.setdefault("_composition", {})["warnings"] = warnings
    composed.setdefault("_composition", {})["packs"] = [p.get("key") or p.get("modality") for p in pack_list]
    return composed
