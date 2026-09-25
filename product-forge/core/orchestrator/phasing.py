"""
Phasing Manager (extracted from pipeline_executor - 1A.11).

Extracts the feature list from the product plan and plans dynamic
implementation iterations (feature subsets) for stages 4a..4f.
"""
import os
from typing import Dict, List, Optional

from core.iteration_planner import (
    plan_iterations,
    iteration_feature_map,
    extract_features as _parse_features,
    ITERATION_STAGES,
)

PHASE_STAGES = ITERATION_STAGES


class PhasingManager:
    def __init__(self, project_dir: str, phases_override: Optional[int] = None):
        self.project_dir = project_dir
        self.phases_override = phases_override
        self.phase_plan: List = []
        self.phase_feature_map: Dict[str, List[str]] = {}
        self.phases_planned = False
        self.planning_mode = "epic"  # "epic" (Scrum-style) or "feature"

    def extract_features(self) -> List[Dict]:
        """Extract feature list (id + title + priority) from the product plan."""
        from core import stage_paths as _sp
        candidates = [
            os.path.join(self.project_dir, "docs", "product-plan.md"),
            os.path.join(_sp.find_stage_dir(self.project_dir, "0"), "ideation-output.md"),
        ]
        for p in candidates:
            if not os.path.exists(p):
                continue
            try:
                with open(p, "r", encoding="utf-8") as f:
                    txt = f.read()
            except Exception:
                continue
            feats = _parse_features(txt)
            if feats:
                return feats
        return []

    def plan(self) -> List:
        """Compute a dynamic implementation phase plan from the feature list."""
        feats = self.extract_features()
        iterations = plan_iterations(feats, override=self.phases_override,
                                     group_by_epic=(self.planning_mode != "feature"))
        self.phase_plan = iterations
        self.phase_feature_map = iteration_feature_map(iterations)
        self.phases_planned = True
        if iterations:
            print(f"  [ITERATIONS] {len(iterations)} implementation iteration(s): "
                  + ", ".join(f"{it.stage_id}({len(it.feature_subset)}f,~{it.est_output_tokens}tok)"
                              for it in iterations))
        else:
            print("  [ITERATIONS] no features found; implementation iterations will be skipped")
        return iterations

    def features_for_stage(self, stage_id: str) -> List[str]:
        if not self.phases_planned:
            self.plan()
        return self.phase_feature_map.get(stage_id, [])

    def is_inactive_stage(self, stage_id: str) -> bool:
        if not self.phases_planned:
            return False
        active = {p.stage_id for p in self.phase_plan}
        if stage_id in PHASE_STAGES:
            return stage_id not in active
        for s in PHASE_STAGES:
            if stage_id == s + "-vqa":
                return s not in active
        return False
