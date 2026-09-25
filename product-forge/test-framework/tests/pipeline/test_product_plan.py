"""
Product Plan Tests
Tests for the living product plan data model
"""

import pytest
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.product_plan import (
    ProductPlan, Module, Feature, FeatureImplementation,
    FeatureTesting, FeatureSecurity, FeatureQuality,
    AgentContribution, PlanHistory
)


class TestProductPlan:
    """Test suite for ProductPlan"""

    def test_create_empty_plan(self, temp_products_dir, sample_project):
        """Test creating an empty product plan"""
        plan = ProductPlan(sample_project, str(temp_products_dir))

        # Plan is created in memory, save to persist
        plan.save()

        assert plan.exists()
        assert plan.plan["project"] == sample_project
        assert plan.plan["version"] == "1.0.0"
        assert len(plan.plan["modules"]) == 0

    def test_set_vision(self, temp_products_dir, sample_project):
        """Test setting product vision"""
        plan = ProductPlan(sample_project, str(temp_products_dir))

        plan.set_vision(
            summary="Test product vision",
            target_users=["Developers", "Admins"],
            platforms=["Web", "Mobile"],
            constraints={"budget": "zero"}
        )
        plan.save()

        assert plan.plan["vision"]["summary"] == "Test product vision"
        assert "Developers" in plan.plan["vision"]["target_users"]
        assert "Web" in plan.plan["vision"]["platforms"]

    def test_add_module(self, temp_products_dir, sample_project):
        """Test adding a module"""
        plan = ProductPlan(sample_project, str(temp_products_dir))

        module = plan.add_module(
            module_id="MOD-1",
            name="Core Features",
            phase=1,
            description="Essential features"
        )
        plan.save()

        assert module.id == "MOD-1"
        assert module.name == "Core Features"
        assert len(plan.plan["modules"]) == 1

    def test_get_module(self, temp_products_dir, sample_project):
        """Test getting a module"""
        plan = ProductPlan(sample_project, str(temp_products_dir))

        plan.add_module("MOD-1", "Core Features", 1)
        plan.save()
        module = plan.get_module("MOD-1")

        assert module is not None
        assert module.id == "MOD-1"

    def test_update_module_status(self, temp_products_dir, sample_project):
        """Test updating module status"""
        plan = ProductPlan(sample_project, str(temp_products_dir))

        plan.add_module("MOD-1", "Core Features", 1)
        updated = plan.update_module_status("MOD-1", "in-progress")
        plan.save()

        assert updated is not None
        assert updated.status == "in-progress"

    def test_add_feature(self, temp_products_dir, sample_project):
        """Test adding a feature"""
        plan = ProductPlan(sample_project, str(temp_products_dir))

        plan.add_module("MOD-1", "Core Features", 1)

        feature = plan.add_feature(
            feature_id="F-001",
            name="Authentication",
            module_id="MOD-1",
            priority="must-have",
            phase=1,
            requirements=["FR-1"],
            architecture_decisions=["ADR-001"]
        )
        plan.save()

        assert feature.id == "F-001"
        assert feature.name == "Authentication"
        assert "FR-1" in plan.plan["requirements_index"]

    def test_get_feature(self, temp_products_dir, sample_project):
        """Test getting a feature"""
        plan = ProductPlan(sample_project, str(temp_products_dir))

        plan.add_module("MOD-1", "Core Features", 1)
        plan.add_feature("F-001", "Authentication", "MOD-1", "must-have", 1)
        plan.save()
        feature = plan.get_feature("F-001")

        assert feature is not None
        assert feature.id == "F-001"

    def test_update_feature_status(self, temp_products_dir, sample_project):
        """Test updating feature status"""
        plan = ProductPlan(sample_project, str(temp_products_dir))

        plan.add_module("MOD-1", "Core Features", 1)
        plan.add_feature("F-001", "Authentication", "MOD-1", "must-have", 1)

        updated = plan.update_feature_status("F-001", "completed", agent="implement")
        plan.save()

        assert updated is not None
        assert updated.status == "completed"
        assert len(plan.plan["history"]) > 0

    def test_record_implementation(self, temp_products_dir, sample_project):
        """Test recording implementation details"""
        plan = ProductPlan(sample_project, str(temp_products_dir))

        plan.add_module("MOD-1", "Core Features", 1)
        plan.add_feature("F-001", "Authentication", "MOD-1", "must-have", 1)

        feature = plan.record_implementation(
            "F-001",
            agent="implement",
            files=["src/auth.py", "src/auth_test.py"],
            commit="abc123"
        )
        plan.save()

        assert feature is not None
        assert feature.implementation is not None
        assert feature.implementation.agent == "implement"
        assert len(feature.implementation.files) == 2

    def test_record_testing(self, temp_products_dir, sample_project):
        """Test recording testing results"""
        plan = ProductPlan(sample_project, str(temp_products_dir))

        plan.add_module("MOD-1", "Core Features", 1)
        plan.add_feature("F-001", "Authentication", "MOD-1", "must-have", 1)

        feature = plan.record_testing(
            "F-001",
            status="passing",
            test_files=["tests/test_auth.py"],
            test_count=10,
            pass_rate=1.0
        )
        plan.save()

        assert feature is not None
        assert feature.testing is not None
        assert feature.testing.status == "passing"
        assert feature.testing.pass_rate == 1.0

    def test_record_security(self, temp_products_dir, sample_project):
        """Test recording security findings"""
        plan = ProductPlan(sample_project, str(temp_products_dir))

        plan.add_module("MOD-1", "Core Features", 1)
        plan.add_feature("F-001", "Authentication", "MOD-1", "must-have", 1)

        feature = plan.record_security(
            "F-001",
            issues=["SEC-001"],
            status="issues_found"
        )
        plan.save()

        assert feature is not None
        assert feature.security is not None
        assert "SEC-001" in feature.security.issues

    def test_record_code_review(self, temp_products_dir, sample_project):
        """Test recording code review result"""
        plan = ProductPlan(sample_project, str(temp_products_dir))

        plan.add_module("MOD-1", "Core Features", 1)
        plan.add_feature("F-001", "Authentication", "MOD-1", "must-have", 1)

        feature = plan.record_code_review("F-001", "approved")
        plan.save()

        assert feature is not None
        assert feature.quality is not None
        assert feature.quality.code_review_status == "approved"

    def test_record_agent_contribution(self, temp_products_dir, sample_project):
        """Test recording agent contribution"""
        plan = ProductPlan(sample_project, str(temp_products_dir))

        contribution = plan.record_agent_contribution(
            agent="design",
            stage=1,
            action="Created requirements",
            files_written=["docs/requirements.md"],
            decisions_made=["MVP scope defined"]
        )
        plan.save()

        assert contribution.agent == "design"
        assert len(plan.plan["agent_contributions"]) == 1

    def test_get_features_by_status(self, temp_products_dir, sample_project):
        """Test getting features by status"""
        plan = ProductPlan(sample_project, str(temp_products_dir))

        plan.add_module("MOD-1", "Core Features", 1)
        plan.add_feature("F-001", "Feature 1", "MOD-1", "must-have", 1)
        plan.add_feature("F-002", "Feature 2", "MOD-1", "must-have", 1)

        plan.update_feature_status("F-001", "completed")
        plan.save()

        completed = plan.get_features_by_status("completed")
        planned = plan.get_features_by_status("planned")

        assert len(completed) == 1
        assert len(planned) == 1

    def test_get_blocked_features(self, temp_products_dir, sample_project):
        """Test getting blocked features"""
        plan = ProductPlan(sample_project, str(temp_products_dir))

        plan.add_module("MOD-1", "Core Features", 1)
        plan.add_feature("F-001", "Feature 1", "MOD-1", "must-have", 1)
        plan.update_feature_status("F-001", "blocked")
        plan.save()

        blocked = plan.get_blocked_features()

        assert len(blocked) == 1
        assert blocked[0].status == "blocked"

    def test_get_features_needing_rework(self, temp_products_dir, sample_project):
        """Test getting features needing rework"""
        plan = ProductPlan(sample_project, str(temp_products_dir))

        plan.add_module("MOD-1", "Core Features", 1)
        plan.add_feature("F-001", "Feature 1", "MOD-1", "must-have", 1)

        # Debug: Check what's in the plan before record_testing
        print(f"\nBefore record_testing:")
        for mod_data in plan.plan["modules"]:
            for feat_data in mod_data.get("features", []):
                print(f"  Feature: {feat_data['id']}, testing: {feat_data.get('testing')}")

        plan.record_testing("F-001", "failing", test_count=10, pass_rate=0.5)

        # Debug: Check what's in the plan after record_testing
        print(f"\nAfter record_testing:")
        for mod_data in plan.plan["modules"]:
            for feat_data in mod_data.get("features", []):
                print(f"  Feature: {feat_data['id']}, testing: {feat_data.get('testing')}")

        plan.add_feature("F-002", "Feature 2", "MOD-1", "must-have", 1)
        plan.record_security("F-002", issues=["SEC-001"])

        # Debug: Check what's in the plan after record_security
        print(f"\nAfter record_security:")
        for mod_data in plan.plan["modules"]:
            for feat_data in mod_data.get("features", []):
                print(f"  Feature: {feat_data['id']}, security: {feat_data.get('security')}")

        plan.save()

        # Debug: Check all features
        all_features = plan.get_all_features()
        print(f"\nAll features:")
        for f in all_features:
            print(f"  Feature: {f.id}, testing: {f.testing}, security: {f.security}")

        rework = plan.get_features_needing_rework()

        assert len(rework) == 2

    def test_get_pending_features(self, temp_products_dir, sample_project):
        """Test getting pending features"""
        plan = ProductPlan(sample_project, str(temp_products_dir))

        plan.add_module("MOD-1", "Core Features", 1)
        plan.add_feature("F-001", "Feature 1", "MOD-1", "must-have", 1)
        plan.save()

        pending = plan.get_pending_features()

        assert len(pending) == 1
        assert pending[0].status == "planned"

    def test_get_metadata(self, temp_products_dir, sample_project):
        """Test getting metadata"""
        plan = ProductPlan(sample_project, str(temp_products_dir))

        plan.add_module("MOD-1", "Core Features", 1)
        plan.add_feature("F-001", "Feature 1", "MOD-1", "must-have", 1)
        plan.add_feature("F-002", "Feature 2", "MOD-1", "must-have", 1)
        plan.update_feature_status("F-001", "completed")
        plan.save()

        metadata = plan.get_metadata()

        assert metadata["total_features"] == 2
        assert metadata["completed_features"] == 1
        assert metadata["in_progress_features"] == 0

    def test_get_project_health(self, temp_products_dir, sample_project):
        """Test getting project health"""
        plan = ProductPlan(sample_project, str(temp_products_dir))

        plan.add_module("MOD-1", "Core Features", 1)
        plan.add_feature("F-001", "Feature 1", "MOD-1", "must-have", 1)
        plan.save()

        health = plan.get_project_health()

        assert health["project"] == sample_project
        assert "feature_completion" in health
        assert health["feature_completion"]["total"] == 1

    def test_record_change(self, temp_products_dir, sample_project):
        """Test recording change history"""
        plan = ProductPlan(sample_project, str(temp_products_dir))

        plan.record_change(
            agent="design",
            action="feature_added",
            details="Added F-001",
            diff={"field": "features", "old": None, "new": "F-001"}
        )
        plan.save()

        history = plan.get_history()

        assert len(history) == 1
        assert history[0].agent == "design"

    def test_generate_markdown(self, temp_products_dir, sample_project):
        """Test markdown generation"""
        plan = ProductPlan(sample_project, str(temp_products_dir))

        plan.set_vision(summary="Test vision")
        plan.add_module("MOD-1", "Core Features", 1)
        plan.add_feature("F-001", "Feature 1", "MOD-1", "must-have", 1)

        md = plan.generate_markdown()

        assert "Test vision" in md
        assert "MOD-1" in md
        assert "F-001" in md
        assert "AUTO-GENERATED" in md


class TestFeature:
    """Test suite for Feature dataclass"""

    def test_feature_creation(self):
        """Test Feature creation"""
        feature = Feature(
            id="F-001",
            name="Test Feature",
            status="planned",
            priority="must-have",
            module="MOD-1",
            phase=1
        )

        assert feature.id == "F-001"
        assert feature.status == "planned"

    def test_feature_serialization(self):
        """Test Feature serialization"""
        feature = Feature(
            id="F-001",
            name="Test Feature",
            status="planned",
            priority="must-have",
            module="MOD-1",
            phase=1,
            requirements=["FR-1"]
        )

        data = feature.to_dict()
        assert data["id"] == "F-001"
        assert "FR-1" in data["requirements"]

        restored = Feature.from_dict(data)
        assert restored.id == feature.id
        assert restored.requirements == feature.requirements


class TestModule:
    """Test suite for Module dataclass"""

    def test_module_creation(self):
        """Test Module creation"""
        module = Module(
            id="MOD-1",
            name="Test Module",
            phase=1,
            status="planned"
        )

        assert module.id == "MOD-1"
        assert module.status == "planned"

    def test_module_with_features(self):
        """Test Module with features"""
        feature = Feature(
            id="F-001",
            name="Feature 1",
            status="planned",
            priority="must-have",
            module="MOD-1",
            phase=1
        )
        module = Module(
            id="MOD-1",
            name="Test Module",
            phase=1,
            status="planned",
            features=[feature]
        )

        data = module.to_dict()
        assert len(data["features"]) == 1
