"""
Product Plan
Living document for tracking product features, implementation status, and agent contributions.
Single source of truth: products/<name>/product-plan.json
Human-readable view: products/<name>/architecture/product-plan.md (auto-generated)
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict, field
from datetime import datetime


@dataclass
class FeatureImplementation:
    """Implementation details for a feature"""
    agent: str
    session_id: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    files: List[str] = field(default_factory=list)
    commit: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FeatureImplementation':
        return cls(**data)


@dataclass
class FeatureTesting:
    """Testing details for a feature"""
    status: str = "pending"
    test_files: List[str] = field(default_factory=list)
    test_count: int = 0
    pass_rate: float = 0.0
    last_run: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FeatureTesting':
        return cls(**data)


@dataclass
class FeatureSecurity:
    """Security details for a feature"""
    issues: List[str] = field(default_factory=list)
    status: str = "pending"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FeatureSecurity':
        return cls(**data)


@dataclass
class FeatureQuality:
    """Quality details for a feature"""
    code_review_status: str = "pending"
    defect_count: int = 0
    last_review: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FeatureQuality':
        return cls(**data)


@dataclass
class Feature:
    """Product feature"""
    id: str
    name: str
    status: str  # planned, in-progress, completed, verified, blocked
    priority: str  # must-have, should-have, nice-to-have
    module: str
    phase: int
    description: str = ""
    requirements: List[str] = field(default_factory=list)
    architecture_decisions: List[str] = field(default_factory=list)
    backlog_id: str = ""          # link to the backlog item (BI-####) for this feature
    implementation: Optional[FeatureImplementation] = None
    testing: Optional[FeatureTesting] = None
    security: Optional[FeatureSecurity] = None
    quality: Optional[FeatureQuality] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.implementation:
            data["implementation"] = self.implementation.to_dict()
        if self.testing:
            data["testing"] = self.testing.to_dict()
        if self.security:
            data["security"] = self.security.to_dict()
        if self.quality:
            data["quality"] = self.quality.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Feature':
        impl_data = data.pop("implementation", None)
        test_data = data.pop("testing", None)
        sec_data = data.pop("security", None)
        qual_data = data.pop("quality", None)

        feature = cls(**data)
        if impl_data:
            feature.implementation = FeatureImplementation.from_dict(impl_data)
        if test_data:
            feature.testing = FeatureTesting.from_dict(test_data)
        if sec_data:
            feature.security = FeatureSecurity.from_dict(sec_data)
        if qual_data:
            feature.quality = FeatureQuality.from_dict(qual_data)
        return feature


@dataclass
class Module:
    """Product module containing features"""
    id: str
    name: str
    phase: int
    status: str  # planned, in-progress, completed, blocked
    description: str = ""
    features: List[Feature] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "phase": self.phase,
            "status": self.status,
            "description": self.description,
            "features": [f.to_dict() for f in self.features]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Module':
        features_data = data.pop("features", [])
        module = cls(**data)
        module.features = [Feature.from_dict(f) for f in features_data]
        return module


@dataclass
class AgentContribution:
    """Record of what an agent did"""
    agent: str
    session_id: Optional[str] = None
    timestamp: str = ""
    stage: int = 0
    action: str = ""
    files_written: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    decisions_made: List[str] = field(default_factory=list)
    artifacts: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentContribution':
        return cls(**data)


@dataclass
class PlanHistory:
    """History entry for plan changes"""
    timestamp: str
    agent: str
    action: str
    details: str = ""
    diff: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlanHistory':
        return cls(**data)


class ProductPlan:
    """
    Living Product Plan — structured, queryable data model for project tracking.

    Manages products/<name>/product-plan.json as the machine-readable source of truth.
    Agents read/write this; docs/product-plan.md remains the human-readable view.
    """

    def __init__(self, project: str, products_dir: str = "products"):
        """
        Initialize for a specific project.

        Args:
            project: Project name
            products_dir: Path to products directory
        """
        self.project = project
        self.products_dir = Path(products_dir)
        self.project_dir = self.products_dir / project
        self.plan_path = self.project_dir / "product-plan.json"
        self.plan: Dict[str, Any] = {}
        self._load_or_create()

    def _load_or_create(self):
        """Load existing plan or create new one"""
        if self.plan_path.exists():
            with open(self.plan_path, 'r', encoding='utf-8') as f:
                self.plan = json.load(f)
        else:
            self.plan = self._create_empty_plan()

    def _create_empty_plan(self) -> Dict[str, Any]:
        """Create empty product plan structure"""
        return {
            "$schema": "product-plan-v1",
            "version": "1.0.0",
            "project": self.project,
            "last_updated": datetime.now().isoformat(),
            "updated_by": "system",
            "vision": {
                "summary": "",
                "target_users": [],
                "platforms": [],
                "constraints": {}
            },
            "modules": [],
            "requirements_index": {},
            "architecture_decisions": {},
            "agent_contributions": [],
            "history": [],
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "created_by": "system",
                "schema_version": "1.0.0",
                "total_features": 0,
                "completed_features": 0,
                "in_progress_features": 0,
                "planned_features": 0,
                "blocked_features": 0,
                "needs_rework": 0
            }
        }

    def save(self):
        """Atomic write to product-plan.json"""
        self.plan["last_updated"] = datetime.now().isoformat()
        self._update_metadata()

        self.plan_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.plan_path.with_suffix('.tmp')
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(self.plan, f, indent=2, ensure_ascii=False)
            if self.plan_path.exists():
                self.plan_path.unlink()
            temp_path.rename(self.plan_path)
            # U8 (BI-0016): keep requirements_index <-> traceability linked by id (non-fatal).
            try:
                from core.requirement_link import synchronize
                synchronize(self.project, str(self.plan_path.parent.parent))
            except Exception:
                pass
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise Exception(f"Failed to save product plan: {e}")

    def exists(self) -> bool:
        """Check if product plan exists"""
        return self.plan_path.exists()

    # --- Vision Management ---

    def set_vision(self, summary: str, target_users: List[str] = None,
                   platforms: List[str] = None, constraints: Dict[str, Any] = None):
        """Set product vision"""
        self.plan["vision"]["summary"] = summary
        if target_users:
            self.plan["vision"]["target_users"] = target_users
        if platforms:
            self.plan["vision"]["platforms"] = platforms
        if constraints:
            self.plan["vision"]["constraints"] = constraints

    # --- Module Management ---

    def add_module(self, module_id: str, name: str, phase: int,
                   description: str = "", status: str = "planned") -> Module:
        """Add a new module"""
        module = Module(
            id=module_id,
            name=name,
            phase=phase,
            status=status,
            description=description
        )
        self.plan["modules"].append(module.to_dict())
        return module

    def get_module(self, module_id: str) -> Optional[Module]:
        """Get module by ID"""
        for mod_data in self.plan["modules"]:
            if mod_data["id"] == module_id:
                return Module.from_dict(mod_data)
        return None

    def update_module_status(self, module_id: str, status: str) -> Optional[Module]:
        """Update module status"""
        for mod_data in self.plan["modules"]:
            if mod_data["id"] == module_id:
                mod_data["status"] = status
                return Module.from_dict(mod_data)
        return None

    def get_modules(self) -> List[Module]:
        """Get all modules"""
        return [Module.from_dict(m) for m in self.plan["modules"]]

    # --- Feature Management ---

    def add_feature(self, feature_id: str, name: str, module_id: str,
                    priority: str, phase: int, description: str = "",
                    requirements: List[str] = None,
                    architecture_decisions: List[str] = None) -> Feature:
        """Add a new feature to a module"""
        feature = Feature(
            id=feature_id,
            name=name,
            status="planned",
            priority=priority,
            module=module_id,
            phase=phase,
            description=description,
            requirements=requirements or [],
            architecture_decisions=architecture_decisions or []
        )

        # Find module and add feature
        for mod_data in self.plan["modules"]:
            if mod_data["id"] == module_id:
                mod_data.setdefault("features", []).append(feature.to_dict())
                break

        # Update requirements index
        for req_id in (requirements or []):
            if req_id not in self.plan["requirements_index"]:
                self.plan["requirements_index"][req_id] = {
                    "title": name,
                    "status": "planned",
                    "features": [],
                    "architecture_decisions": [],
                    "test_coverage": 0.0,
                    "security_issues": 0
                }
            self.plan["requirements_index"][req_id]["features"].append(feature_id)

        return feature

    def get_feature(self, feature_id: str) -> Optional[Feature]:
        """Get feature by ID"""
        for mod_data in self.plan["modules"]:
            for feat_data in mod_data.get("features", []):
                if feat_data["id"] == feature_id:
                    # Return a copy to avoid from_dict popping from original
                    return Feature.from_dict(feat_data.copy())
        return None

    def update_feature_status(self, feature_id: str, status: str,
                              agent: str = None, session_id: str = None) -> Optional[Feature]:
        """Update feature status with audit trail"""
        old_status = None
        for mod_data in self.plan["modules"]:
            for feat_data in mod_data.get("features", []):
                if feat_data["id"] == feature_id:
                    old_status = feat_data["status"]
                    feat_data["status"] = status

                    # Record change in history
                    self.record_change(
                        agent=agent or "system",
                        action="feature_status_updated",
                        details=f"{feature_id} status changed from {old_status} to {status}",
                        diff={
                            "field": f"features[{feature_id}].status",
                            "old": old_status,
                            "new": status
                        }
                    )
                    # B1 bridge: mirror into the backlog registry (non-fatal)
                    try:
                        from core.backlog_link import mirror_feature_status
                        item = mirror_feature_status(
                            getattr(self, "project", "") or "",
                            feature_id, status,
                            title=feat_data.get("name", ""),
                            priority=feat_data.get("priority", ""))
                        if item and feat_data.get("backlog_id") != item.get("id"):
                            feat_data["backlog_id"] = item.get("id", "")
                    except Exception:
                        pass
                    # Return a copy to avoid from_dict popping from original
                    return Feature.from_dict(feat_data.copy())
        return None

    def record_implementation(self, feature_id: str, agent: str,
                              files: List[str] = None, commit: str = None,
                              session_id: str = None) -> Optional[Feature]:
        """Record implementation details for a feature"""
        for mod_data in self.plan["modules"]:
            for feat_data in mod_data.get("features", []):
                if feat_data["id"] == feature_id:
                    feat_data["implementation"] = FeatureImplementation(
                        agent=agent,
                        session_id=session_id,
                        started_at=datetime.now().isoformat(),
                        files=files or [],
                        commit=commit
                    ).to_dict()
                    # Return a copy to avoid from_dict popping from original
                    return Feature.from_dict(feat_data.copy())
        return None

    def record_testing(self, feature_id: str, status: str,
                       test_files: List[str] = None, test_count: int = 0,
                       pass_rate: float = 0.0) -> Optional[Feature]:
        """Record testing results for a feature"""
        for mod_data in self.plan["modules"]:
            for feat_data in mod_data.get("features", []):
                if feat_data["id"] == feature_id:
                    testing_data = FeatureTesting(
                        status=status,
                        test_files=test_files or [],
                        test_count=test_count,
                        pass_rate=pass_rate,
                        last_run=datetime.now().isoformat()
                    ).to_dict()
                    # Directly modify the dictionary in place
                    feat_data["testing"] = testing_data
                    # Return a new Feature object from a copy of the dictionary
                    # (from_dict uses pop which modifies the original)
                    return Feature.from_dict(feat_data.copy())
        return None

    def record_security(self, feature_id: str, issues: List[str] = None,
                        status: str = "clean") -> Optional[Feature]:
        """Record security findings for a feature"""
        for mod_data in self.plan["modules"]:
            for feat_data in mod_data.get("features", []):
                if feat_data["id"] == feature_id:
                    feat_data["security"] = FeatureSecurity(
                        issues=issues or [],
                        status=status
                    ).to_dict()
                    # Return a copy to avoid from_dict popping from original
                    return Feature.from_dict(feat_data.copy())
        return None

    def record_code_review(self, feature_id: str, status: str,
                           reviewer: str = None) -> Optional[Feature]:
        """Record code review result for a feature"""
        for mod_data in self.plan["modules"]:
            for feat_data in mod_data.get("features", []):
                if feat_data["id"] == feature_id:
                    feat_data["quality"] = FeatureQuality(
                        code_review_status=status,
                        last_review=datetime.now().isoformat()
                    ).to_dict()
                    # Return a copy to avoid from_dict popping from original
                    return Feature.from_dict(feat_data.copy())
        return None

    # --- Agent Contributions ---

    def record_agent_contribution(self, agent: str, stage: int, action: str,
                                  files_written: List[str] = None,
                                  files_modified: List[str] = None,
                                  decisions_made: List[str] = None,
                                  session_id: str = None,
                                  artifacts: Dict[str, Dict[str, Any]] = None) -> AgentContribution:
        """Record what an agent did during its run"""
        contribution = AgentContribution(
            agent=agent,
            session_id=session_id,
            timestamp=datetime.now().isoformat(),
            stage=stage,
            action=action,
            files_written=files_written or [],
            files_modified=files_modified or [],
            decisions_made=decisions_made or [],
            artifacts=artifacts or {}
        )
        self.plan["agent_contributions"].append(contribution.to_dict())
        return contribution

    # --- Queries ---

    def get_features_by_status(self, status: str) -> List[Feature]:
        """Get all features with a given status"""
        features = []
        for mod_data in self.plan["modules"]:
            for feat_data in mod_data.get("features", []):
                if feat_data["status"] == status:
                    # Return a copy to avoid from_dict popping from original
                    features.append(Feature.from_dict(feat_data.copy()))
        return features

    def get_features_by_module(self, module_id: str) -> List[Feature]:
        """Get all features in a module"""
        for mod_data in self.plan["modules"]:
            if mod_data["id"] == module_id:
                # Return copies to avoid from_dict popping from original
                return [Feature.from_dict(f.copy()) for f in mod_data.get("features", [])]
        return []

    def get_blocked_features(self) -> List[Feature]:
        """Get all blocked features"""
        return self.get_features_by_status("blocked")

    def get_features_needing_rework(self) -> List[Feature]:
        """Get features that need rework (failed tests, security issues)"""
        rework = []
        for mod_data in self.plan["modules"]:
            for feat_data in mod_data.get("features", []):
                # Return a copy to avoid from_dict popping from original
                feature = Feature.from_dict(feat_data.copy())
                needs_rework = False

                # Check testing
                if feature.testing and feature.testing.pass_rate < 1.0:
                    needs_rework = True

                # Check security
                if feature.security and feature.security.issues:
                    needs_rework = True

                # Check quality
                if feature.quality and feature.quality.code_review_status == "rejected":
                    needs_rework = True

                if needs_rework:
                    rework.append(feature)
        return rework

    def get_pending_features(self) -> List[Feature]:
        """Get features that are planned but not started"""
        return self.get_features_by_status("planned")

    def get_all_features(self) -> List[Feature]:
        """Get all features across all modules"""
        features = []
        for mod_data in self.plan["modules"]:
            for feat_data in mod_data.get("features", []):
                # Return a copy to avoid from_dict popping from original
                features.append(Feature.from_dict(feat_data.copy()))
        return features

    def get_requirements_for_feature(self, feature_id: str) -> List[str]:
        """Get requirement IDs linked to a feature"""
        feature = self.get_feature(feature_id)
        return feature.requirements if feature else []

    def get_features_for_requirement(self, req_id: str) -> List[Feature]:
        """Get all features implementing a requirement"""
        features = []
        for mod_data in self.plan["modules"]:
            for feat_data in mod_data.get("features", []):
                if req_id in feat_data.get("requirements", []):
                    features.append(Feature.from_dict(feat_data))
        return features

    # --- Metrics ---

    def _update_metadata(self):
        """Update computed metadata"""
        all_features = self.get_all_features()
        completed_states = {"completed", "verified"}
        self.plan["metadata"]["total_features"] = len(all_features)
        self.plan["metadata"]["completed_features"] = len([f for f in all_features if f.status in completed_states])
        self.plan["metadata"]["in_progress_features"] = len([f for f in all_features if f.status == "in-progress"])
        self.plan["metadata"]["planned_features"] = len([f for f in all_features if f.status == "planned"])
        self.plan["metadata"]["blocked_features"] = len([f for f in all_features if f.status == "blocked"])
        self.plan["metadata"]["needs_rework"] = len(self.get_features_needing_rework())

    def get_metadata(self) -> Dict[str, Any]:
        """Get computed metadata"""
        self._update_metadata()
        return self.plan["metadata"]

    def get_project_health(self) -> Dict[str, Any]:
        """Get overall project health summary"""
        metadata = self.get_metadata()
        total = metadata["total_features"]

        return {
            "project": self.project,
            "overall_status": "healthy" if metadata["blocked_features"] == 0 else "at-risk",
            "feature_completion": {
                "total": total,
                "completed": metadata["completed_features"],
                "in_progress": metadata["in_progress_features"],
                "planned": metadata["planned_features"],
                "blocked": metadata["blocked_features"],
                "percent_complete": (metadata["completed_features"] / total * 100) if total > 0 else 0
            },
            "needs_rework": metadata["needs_rework"],
            "last_updated": self.plan.get("last_updated", ""),
            "modules": len(self.plan.get("modules", []))
        }

    # --- History ---

    def record_change(self, agent: str, action: str, details: str,
                      diff: Dict[str, Any] = None):
        """Record a change in history"""
        entry = PlanHistory(
            timestamp=datetime.now().isoformat(),
            agent=agent,
            action=action,
            details=details,
            diff=diff
        )
        self.plan["history"].append(entry.to_dict())

    def get_history(self, limit: int = 50) -> List[PlanHistory]:
        """Get recent history entries"""
        entries = self.plan.get("history", [])[-limit:]
        return [PlanHistory.from_dict(e) for e in entries]

    # --- Markdown Generation ---

    def generate_markdown(self) -> str:
        """Generate human-readable product plan as markdown"""
        md = []
        md.append(f"# Product Plan: {self.project}")
        md.append("")
        md.append("> ⚠️ AUTO-GENERATED — Do not edit directly.")
        md.append("> Source of truth: `product-plan.json`")
        md.append("> Regenerated after each pipeline run. Edit the JSON, not this file.")
        md.append("")

        # Vision
        vision = self.plan.get("vision", {})
        if vision.get("summary"):
            md.append("## Vision")
            md.append("")
            md.append(vision["summary"])
            md.append("")
            if vision.get("target_users"):
                md.append("**Target Users:** " + ", ".join(vision["target_users"]))
            if vision.get("platforms"):
                md.append("**Platforms:** " + ", ".join(vision["platforms"]))
            md.append("")

        # Metadata
        metadata = self.get_metadata()
        md.append("## Status Summary")
        md.append("")
        md.append(f"| Metric | Value |")
        md.append(f"|--------|-------|")
        md.append(f"| Total Features | {metadata['total_features']} |")
        md.append(f"| Completed | {metadata['completed_features']} |")
        md.append(f"| In Progress | {metadata['in_progress_features']} |")
        md.append(f"| Planned | {metadata['planned_features']} |")
        md.append(f"| Blocked | {metadata['blocked_features']} |")
        md.append(f"| Needs Rework | {metadata['needs_rework']} |")
        md.append("")

        # Modules and Features
        md.append("## Modules")
        md.append("")
        for mod_data in self.plan.get("modules", []):
            # Use a copy to avoid from_dict popping from original
            module = Module.from_dict(mod_data.copy())
            status_icon = {"completed": "✅", "in-progress": "🔄", "planned": "📋", "blocked": "🚫"}.get(module.status, "❓")
            md.append(f"### {status_icon} {module.id}: {module.name} (Phase {module.phase})")
            md.append("")
            if module.description:
                md.append(module.description)
                md.append("")

            # Use original mod_data to iterate features (since module.features was popped)
            features = mod_data.get("features", [])
            if features:
                md.append("| Feature | Status | Priority | Requirements | Tests | Security |")
                md.append("|---------|--------|----------|--------------|-------|----------|")
                for feat_data in features:
                    # Use a copy to avoid from_dict popping from original
                    feature = Feature.from_dict(feat_data.copy())
                    feat_icon = {"completed": "✅", "in-progress": "🔄", "planned": "📋", "blocked": "🚫", "verified": "✔️"}.get(feature.status, "❓")
                    reqs = ", ".join(feature.requirements) if feature.requirements else "-"
                    tests = f"{int(feature.testing.pass_rate * 100)}%" if feature.testing and feature.testing.test_count > 0 else "-"
                    sec = feature.security.status if feature.security else "-"
                    md.append(f"| {feat_icon} {feature.id}: {feature.name} | {feature.status} | {feature.priority} | {reqs} | {tests} | {sec} |")
                md.append("")
            else:
                md.append("*No features defined*")
                md.append("")

        # Agent Contributions
        contributions = self.plan.get("agent_contributions", [])
        if contributions:
            md.append("## Agent Contributions")
            md.append("")
            md.append("| Agent | Stage | Action | Timestamp |")
            md.append("|-------|-------|--------|-----------|")
            for contrib in contributions[-10:]:  # Last 10
                md.append(f"| {contrib['agent']} | {contrib['stage']} | {contrib['action']} | {contrib['timestamp']} |")
            md.append("")

        return "\n".join(md)

    def save_markdown(self):
        """Save generated markdown to architecture directory"""
        arch_dir = self.project_dir / "architecture"
        arch_dir.mkdir(parents=True, exist_ok=True)

        md_content = self.generate_markdown()
        md_path = arch_dir / "product-plan.md"

        temp_path = md_path.with_suffix('.tmp')
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
            if md_path.exists():
                md_path.unlink()
            temp_path.rename(md_path)
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise Exception(f"Failed to save product plan markdown: {e}")

    # --- Migration ---

    @classmethod
    def migrate_from_markdown(cls, project: str, products_dir: str = "products") -> 'ProductPlan':
        """Create product-plan.json from existing docs"""
        plan = cls(project, products_dir)

        project_dir = Path(products_dir) / project
        docs_dir = project_dir / "docs"

        # Try to parse requirements.md for FR-NNN entries
        req_path = docs_dir / "requirements.md"
        if req_path.exists():
            with open(req_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Simple parser for FR-NNN patterns
                import re
                fr_pattern = re.compile(r'FR-(\d+)[\s:]+(.+?)(?:\n|$)')
                for match in fr_pattern.finditer(content):
                    fr_id = f"FR-{match.group(1)}"
                    title = match.group(2).strip()
                    plan.plan["requirements_index"][fr_id] = {
                        "title": title,
                        "status": "planned",
                        "features": [],
                        "architecture_decisions": [],
                        "test_coverage": 0.0,
                        "security_issues": 0
                    }

        # Try to parse architecture.md for ADR entries
        arch_path = docs_dir / "architecture.md"
        if arch_path.exists():
            with open(arch_path, 'r', encoding='utf-8') as f:
                content = f.read()
                import re
                adr_pattern = re.compile(r'ADR-(\d+)[\s:]+(.+?)(?:\n|$)')
                for match in adr_pattern.finditer(content):
                    adr_id = f"ADR-{match.group(1)}"
                    title = match.group(2).strip()
                    plan.plan["architecture_decisions"][adr_id] = {
                        "title": title,
                        "status": "accepted",
                        "features": [],
                        "requirements": [],
                        "document": f"docs/architecture.md#{adr_id.lower()}"
                    }

        plan.save()
        return plan
