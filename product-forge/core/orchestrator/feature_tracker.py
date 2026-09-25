"""
Feature tracker (extracted for 3.2/3.9).

Thin wrapper over core/product_plan.ProductPlan that tracks each feature's
status across the run (planned -> completed -> verified) and persists
product-plan.json + architecture/product-plan.md.
"""
from typing import Dict, List, Optional


class FeatureTracker:
    def __init__(self, project: str, products_dir: str = "products"):
        self.project = project
        self.products_dir = products_dir
        self.plan = None
        self._seeded = False
        try:
            from core.product_plan import ProductPlan
            self.plan = ProductPlan(project, products_dir)
        except Exception:
            self.plan = None

    def seed(self, features: List[Dict]):
        """Create plan features/modules for the extracted feature list."""
        if not self.plan:
            return
        try:
            mods = self.plan.get_modules()
        except Exception:
            mods = []
        if not mods:
            try:
                self.plan.add_module("core", "Core", 1)
            except Exception:
                pass
        for f in features or []:
            fid = f.get("id")
            if not fid:
                continue
            try:
                if not self.plan.get_feature(fid):
                    self.plan.add_feature(fid, f.get("title", ""), "core",
                                          f.get("priority") or "must-have", 1,
                                          description=f.get("title", ""))
                # B1 bridge: ensure the backlog item exists for this feature (non-fatal)
                try:
                    from core.backlog_link import ensure_feature_item
                    from core.product_plan import Feature
                    feat = self.plan.get_feature(fid) or Feature(id=fid, name=f.get("title", ""),
                                                                 status="planned",
                                                                 priority=f.get("priority") or "must-have",
                                                                 module="core", phase=1)
                    item = ensure_feature_item(self.project, feat)
                    if item and feat.backlog_id != item.get("id"):
                        feat.backlog_id = item.get("id", "")
                        self.plan.save()
                except Exception:
                    pass
            except Exception:
                pass
        self._seeded = True
        self.save()

    def mark_implemented(self, feature_ids, agent: Optional[str] = None, files=None):
        if not self.plan:
            return
        for fid in feature_ids or []:
            try:
                self.plan.record_implementation(fid, agent or "system", files=files or [])
                self.plan.update_feature_status(fid, "completed", agent=agent)
            except Exception:
                pass

    def mark_tested(self, feature_ids, status: str = "passed", agent: str = "validate"):
        if not self.plan:
            return
        for fid in feature_ids or []:
            try:
                self.plan.record_testing(fid, status)
                if status == "passed":
                    self.plan.update_feature_status(fid, "verified", agent=agent)
            except Exception:
                pass

    def mark_security(self, feature_ids, issues=None, status: str = "clean", agent: str = "security"):
        if not self.plan:
            return
        for fid in feature_ids or []:
            try:
                self.plan.record_security(fid, issues=issues or [], status=status)
            except Exception:
                pass

    def mark_reviewed(self, feature_ids, status: str = "approved", agent: str = "code-review"):
        if not self.plan:
            return
        for fid in feature_ids or []:
            try:
                self.plan.record_code_review(fid, status)
            except Exception:
                pass

    def health(self) -> Optional[Dict]:
        try:
            return self.plan.get_project_health() if self.plan else None
        except Exception:
            return None

    def save(self):
        try:
            if self.plan:
                self.plan.save()
                self.plan.save_markdown()
        except Exception:
            pass
