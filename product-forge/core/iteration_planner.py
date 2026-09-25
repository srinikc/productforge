"""
Implementation Iteration Planner

Decides how many implementation iterations a project needs and the **feature
subset** each iteration implements, based on estimated work (priority + rough
output size) and a per-iteration token target. Replaces a fixed 3-way split.

Terminology:
  - Phase   = run lifecycle (init/planning/execution/...)
  - Stage   = DAG node (4a, 4a-vqa, ...)
  - Iteration = one implementation stage + its VQA
  - Feature subset = the features assigned to one iteration

Forward-compatible with an Epic/Scrum layer: if features carry an "epic" field,
the planner groups by epic; otherwise it schedules individual features. The
same capacity logic then becomes sprint planning.
"""
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional


MUST_TOKENS = 3000
NICE_TOKENS = 1200
DEFAULT_TARGET_PER_ITERATION = 10000
MIN_ITERATIONS = 1
MAX_ITERATIONS = 6

# Available implementation stage ids (must exist in pipeline-definition.json).
ITERATION_STAGES = ["4a", "4b", "4c", "4d", "4e", "4f"]


@dataclass
class PlannedIteration:
    iteration_index: int
    stage_id: str
    feature_subset: List[Dict]
    est_output_tokens: int
    epic_ids: List[str] = None
    item_ids: List[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)


def _est_tokens(feature: Dict) -> int:
    priority = (feature.get("priority") or "").lower()
    return NICE_TOKENS if "nice" in priority else MUST_TOKENS


def plan_iterations(features: List[Dict],
                    override: Optional[int] = None,
                    target_per_iteration: int = DEFAULT_TARGET_PER_ITERATION,
                    min_iterations: int = MIN_ITERATIONS,
                    max_iterations: int = MAX_ITERATIONS,
                    group_by_epic: bool = True) -> List[PlannedIteration]:
    """Plan implementation iterations + feature subsets from a feature list.

    When ``group_by_epic`` is True (default) features are ordered/grouped by
    their `epic` field (Scrum-style); set False to ignore epics.
    """
    if not features:
        return []

    # must-have first (stable), then nice-to-have; then by epic if present
    ordered = sorted(features, key=lambda f: (
        0 if "nice" not in (f.get("priority") or "").lower() else 1,
        (f.get("epic") or "") if group_by_epic else "",
    ))

    total = sum(_est_tokens(f) for f in ordered)
    if override:
        n = int(override)
    else:
        n = -(-total // target_per_iteration)  # ceil
    n = max(min_iterations, min(max_iterations, n, len(ordered)))
    n = min(n, len(ITERATION_STAGES))

    per_target = max(1, -(-total // n)) if n else total
    capacity = int(per_target * 1.1)

    # First-fit (best-fit-ish): place each feature in the least-loaded iteration
    # that still has capacity, so phases stay balanced by estimated tokens.
    subsets: List[List[Dict]] = [[] for _ in range(n)]
    loads = [0] * n
    for f in ordered:
        est = _est_tokens(f)
        idx = None
        for j in sorted(range(n), key=lambda k: loads[k]):
            if loads[j] + est <= capacity:
                idx = j
                break
        if idx is None:
            idx = loads.index(min(loads))
        subsets[idx].append(f)
        loads[idx] += est
    subsets = [s for s in subsets if s]

    out = []
    for i, chunk in enumerate(subsets):
        epics = sorted({f.get("epic") for f in chunk if f.get("epic")}) if group_by_epic else []
        out.append(PlannedIteration(
            iteration_index=i,
            stage_id=ITERATION_STAGES[i] if i < len(ITERATION_STAGES) else f"4p{i}",
            feature_subset=chunk,
            est_output_tokens=sum(_est_tokens(f) for f in chunk),
            epic_ids=epics,
            item_ids=sorted({f.get('backlog_id') for f in chunk if f.get('backlog_id')}),
        ))
    return out


def iteration_feature_map(iterations: List[PlannedIteration]) -> Dict[str, List[str]]:
    """Return {stage_id: ["F-1: title", ...]} for executor injection."""
    m: Dict[str, List[str]] = {}
    for it in iterations:
        m[it.stage_id] = [f"{f.get('id')}: {f.get('title')}" for f in it.feature_subset]
    return m


def extract_features(text: str) -> List[Dict]:
    """Extract features (id, title, priority, epic) from a product-plan markdown.

    An `epic` is taken from the nearest preceding heading like "## Epic: X"
    (or "Module: X"), or an inline "[epic: X]" tag. Backward compatible: features
    without an epic get `epic=None`.
    """
    import re
    seen, out = set(), []
    epic = None
    epic_heading_re = re.compile(r"^#{1,6}\s*(?:epic|module)\s*[:\-]?\s*(.+)$", re.I)
    epic_tag_re = re.compile(r"\[epic:\s*([^\]]+)\]", re.I)
    for line in text.splitlines():
        hm = epic_heading_re.match(line.strip())
        if hm:
            epic = hm.group(1).strip(" *:")
            continue
        m = re.search(r"F-(\d+)\s*[:\-]\s*([^:(\n]+)", line)
        if not m:
            continue
        fid = f"F-{m.group(1)}"
        if fid in seen:
            continue
        seen.add(fid)
        prio = "nice-to-have" if re.search(r"nice.to.have", line, re.I) else (
            "must-have" if re.search(r"must.have", line, re.I) else "")
        tag = epic_tag_re.search(line)
        item_epic = tag.group(1).strip() if tag else epic
        out.append({"id": fid, "title": m.group(2).replace("**", "").strip(" :*-"),
                    "priority": prio, "epic": item_epic})
    return out


def plan_for_project(project: str, products_dir: str = "products",
                     override: Optional[int] = None) -> Dict:
    """Plan iterations for a project from its product plan (API-friendly)."""
    import os
    from core import stage_paths as _sp
    candidates = [
        os.path.join(products_dir, project, "docs", "product-plan.md"),
        os.path.join(_sp.find_stage_dir(os.path.join(products_dir, project), "0"),
                     "ideation-output.md"),
    ]
    for p in candidates:
        if not os.path.exists(p):
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                txt = f.read()
        except Exception:
            continue
        feats = extract_features(txt)
        if feats:
            iters = plan_iterations(feats, override=override)
            return {
                "project": project,
                "features": feats,
                "iterations": [it.to_dict() for it in iters],
                "iteration_count": len(iters),
            }
    return {"project": project, "features": [], "iterations": [], "iteration_count": 0}
