"""
Tests for Version Manager, Release Manager, Logging, Cross-Review, and Skills Registry
"""
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


class TestVersionManager:
    def test_create_version(self, temp_products_dir):
        from core.version_manager import VersionManager
        vm = VersionManager("test-proj", str(temp_products_dir))
        assert vm.get_current_version() == "0.1.0"

    def test_bump_patch(self, temp_products_dir):
        from core.version_manager import VersionManager
        vm = VersionManager("test-proj", str(temp_products_dir))
        manifest = vm.bump("patch")
        assert manifest.version == "0.1.1"
        assert manifest.bump_type == "patch"
        assert manifest.git_tag == "v0.1.1"

    def test_bump_minor(self, temp_products_dir):
        from core.version_manager import VersionManager
        vm = VersionManager("test-proj", str(temp_products_dir))
        manifest = vm.bump("minor")
        assert manifest.version == "0.2.0"
        assert manifest.bump_type == "minor"

    def test_bump_major(self, temp_products_dir):
        from core.version_manager import VersionManager
        vm = VersionManager("test-proj", str(temp_products_dir))
        manifest = vm.bump("major")
        assert manifest.version == "1.0.0"
        assert manifest.breaking is True

    def test_parse_semver(self):
        from core.version_manager import VersionManager
        v = VersionManager.parse_semver("1.2.3-beta+build")
        assert v["major"] == 1
        assert v["minor"] == 2
        assert v["patch"] == 3
        assert v["pre_release"] == "beta"
        assert v["build_metadata"] == "build"

    def test_format_semver(self):
        from core.version_manager import VersionManager
        assert VersionManager.format_semver(1, 2, 3) == "1.2.3"
        assert VersionManager.format_semver(1, 2, 3, "rc1") == "1.2.3-rc1"

    def test_add_changelog_entry(self, temp_products_dir):
        from core.version_manager import VersionManager
        vm = VersionManager("test-proj", str(temp_products_dir))
        vm.add_changelog_entry("feat", "Added new feature", scope="auth")
        assert len(vm.data["changelog"]) == 1

    def test_generate_changelog(self, temp_products_dir):
        from core.version_manager import VersionManager
        vm = VersionManager("test-proj", str(temp_products_dir))
        vm.bump("minor")
        vm.add_changelog_entry("feat", "New feature")
        vm.add_changelog_entry("fix", "Bug fix")
        md = vm.generate_changelog()
        assert "Changelog" in md
        assert "New feature" in md

    def test_get_version_info(self, temp_products_dir):
        from core.version_manager import VersionManager
        vm = VersionManager("test-proj", str(temp_products_dir))
        info = vm.get_version_info()
        assert info["version"] == "0.1.0"
        assert info["git_tag"] == "v0.1.0"

    def test_persistence(self, temp_products_dir):
        from core.version_manager import VersionManager
        vm = VersionManager("test-proj", str(temp_products_dir))
        vm.bump("patch")
        vm2 = VersionManager("test-proj", str(temp_products_dir))
        assert vm2.get_current_version() == "0.1.1"


class TestReleaseManager:
    def test_create_release_manager(self, temp_products_dir):
        from core.release_manager import ReleaseManager
        rm = ReleaseManager("test-proj", str(temp_products_dir))
        assert rm.data["version"] == "1.0.0"

    def test_select_strategy(self, temp_products_dir):
        from core.release_manager import ReleaseManager
        rm = ReleaseManager("test-proj", str(temp_products_dir))
        assert rm.select_strategy("critical", "saas") == "blue-green"
        assert rm.select_strategy("high", "microservice") == "canary"
        assert rm.select_strategy("medium", "monolith") == "rolling"
        assert rm.select_strategy("low", "desktop") == "in-place"

    def test_create_backup(self, temp_products_dir):
        from core.release_manager import ReleaseManager
        rm = ReleaseManager("test-proj", str(temp_products_dir))
        backup = rm.create_backup("0.1.0", "pre-upgrade")
        assert backup["version"] == "0.1.0"
        assert backup["type"] == "pre-upgrade"

    def test_estimate_footprint(self, temp_products_dir):
        from core.release_manager import ReleaseManager
        rm = ReleaseManager("test-proj", str(temp_products_dir))
        fp = rm.estimate_footprint("web_app", ["docker", "postgres"])
        assert fp.min_ram_mb > 0
        assert fp.runtime_disk_mb > 0

    def test_check_compatibility(self, temp_products_dir):
        from core.release_manager import ReleaseManager
        rm = ReleaseManager("test-proj", str(temp_products_dir))
        result = rm.check_compatibility("1.2.0", "1.1.0")
        assert result["is_upgrade"] is True
        assert result["compatible"] is True

    def test_create_deploy_ticket(self, temp_products_dir):
        from core.release_manager import ReleaseManager
        rm = ReleaseManager("test-proj", str(temp_products_dir))
        ticket = rm.create_deploy_ticket("1.0.0", "art-1", strategy="canary")
        assert ticket.version == "1.0.0"
        assert ticket.strategy == "canary"
        assert ticket.rollback_plan is not None


class TestLoggingManager:
    def test_product_logger(self, temp_products_dir):
        from core.logging_manager import ProductLogger
        logger = ProductLogger("test-proj", str(temp_products_dir))
        logger.info("implement", 1, "build", "Building module")
        logs = logger.get_logs()
        logger.close()
        assert len(logs) > 0

    def test_log_levels(self, temp_products_dir):
        from core.logging_manager import ProductLogger
        logger = ProductLogger("test-proj", str(temp_products_dir))
        logger.debug("implement", 1, "test", "Debug message")
        logger.warning("implement", 1, "test", "Warning message")
        logger.error("implement", 1, "test", "Error message")
        logs = logger.get_logs(level="ERROR")
        logger.close()
        assert any(l.level == "ERROR" for l in logs)

    def test_log_files(self, temp_products_dir):
        from core.logging_manager import ProductLogger
        logger = ProductLogger("test-proj", str(temp_products_dir))
        logger.info("implement", 1, "build", "Test")
        files = logger.get_log_files()
        logger.close()
        assert len(files) > 0

    def test_pipeline_logger(self, temp_products_dir):
        from core.logging_manager import PipelineLogger
        logger = PipelineLogger(str(temp_products_dir))
        logger.info("orchestrator", 0, "start", "Pipeline started")
        logs = logger.get_logs()
        logger.close()
        assert len(logs) > 0


class TestCrossReview:
    def test_request_review(self, temp_products_dir):
        from core.cross_review import CrossReviewManager
        crm = CrossReviewManager("test-proj", str(temp_products_dir))
        request = crm.request_review("implement", "code-review", 5, "src/main.py")
        assert request.target_agent == "implement"
        assert request.reviewer_agent == "code-review"

    def test_auto_reviews(self, temp_products_dir):
        from core.cross_review import CrossReviewManager
        crm = CrossReviewManager("test-proj", str(temp_products_dir))
        requests = crm.request_auto_reviews("implement", 5, "src/main.py")
        assert len(requests) > 0

    def test_add_feedback(self, temp_products_dir):
        from core.cross_review import CrossReviewManager
        crm = CrossReviewManager("test-proj", str(temp_products_dir))
        request = crm.request_review("implement", "code-review", 5, "src/main.py")
        feedback = crm.add_feedback(request.id, "major", "security", "SQL injection risk")
        assert feedback.severity == "major"
        assert feedback.category == "security"

    def test_address_feedback(self, temp_products_dir):
        from core.cross_review import CrossReviewManager
        crm = CrossReviewManager("test-proj", str(temp_products_dir))
        request = crm.request_review("implement", "code-review", 5, "src/main.py")
        feedback = crm.add_feedback(request.id, "minor", "quality", "Missing docstring")
        crm.address_feedback(feedback.id, "implement", "Added docstring")
        open_fb = crm.get_open_feedback()
        assert len(open_fb) == 0

    def test_get_metrics(self, temp_products_dir):
        from core.cross_review import CrossReviewManager
        crm = CrossReviewManager("test-proj", str(temp_products_dir))
        request = crm.request_review("implement", "code-review", 5, "src/main.py")
        crm.add_feedback(request.id, "critical", "security", "Vulnerability")
        crm.update_review_status(request.id, "completed", verdict="changes_required")
        metrics = crm.get_review_metrics()
        assert metrics["total_reviews"] == 1

    def test_agent_quality_score(self, temp_products_dir):
        from core.cross_review import CrossReviewManager
        crm = CrossReviewManager("test-proj", str(temp_products_dir))
        request = crm.request_review("implement", "code-review", 5, "src/main.py")
        crm.add_feedback(request.id, "major", "quality", "Issue")
        score = crm.get_agent_quality_score("implement")
        assert score["quality_score"] < 100


class TestSkillsRegistry:
    def test_create_registry(self, temp_products_dir):
        from core.skills_registry import SkillsRegistry
        sr = SkillsRegistry(str(temp_products_dir))
        sr.seed_defaults()
        assert len(sr.data["skills"]) > 0

    def test_add_skill(self, temp_products_dir):
        from core.skills_registry import SkillsRegistry, Skill
        sr = SkillsRegistry(str(temp_products_dir))
        skill = Skill(
            id="test-skill", name="Test Skill",
            description="A test skill", category="testing",
            agent_types=["validate"], tools=["pytest"],
            source="https://github.com", capabilities=["code"],
        )
        sr.add_skill(skill)
        assert sr.get_skill("test-skill") is not None

    def test_get_skills_for_agent(self, temp_products_dir):
        from core.skills_registry import SkillsRegistry
        sr = SkillsRegistry(str(temp_products_dir))
        sr.seed_defaults()
        skills = sr.get_skills_for_agent("implement")
        assert len(skills) > 0

    def test_add_mcp_server(self, temp_products_dir):
        from core.skills_registry import SkillsRegistry, MCPServer
        sr = SkillsRegistry(str(temp_products_dir))
        server = MCPServer(
            id="test-mcp", name="Test MCP",
            description="A test MCP", category="test",
            inputs=["input"], outputs=["output"],
            capabilities=["test"], source="https://github.com",
        )
        sr.add_mcp_server(server)
        assert sr.get_mcp_server("test-mcp") is not None

    def test_add_model_recommendation(self, temp_products_dir):
        from core.skills_registry import SkillsRegistry, ModelRecommendation
        sr = SkillsRegistry(str(temp_products_dir))
        rec = ModelRecommendation(
            use_case="code",
            recommended_model="gpt-4",
            free_alternative="mimo",
            cheap_alternative="hy3",
            hybrid_option="gpt-4",
            provider="openai",
        )
        sr.add_model_recommendation(rec)
        assert sr.get_model_for_use_case("code") is not None

    def test_recommend_for_project(self, temp_products_dir):
        from core.skills_registry import SkillsRegistry
        sr = SkillsRegistry(str(temp_products_dir))
        sr.seed_defaults()
        rec = sr.recommend_for_project("web_app")
        assert "recommended_skills" in rec
        assert "recommended_mcp" in rec

    def test_search_skills(self, temp_products_dir):
        from core.skills_registry import SkillsRegistry
        sr = SkillsRegistry(str(temp_products_dir))
        sr.seed_defaults()
        results = sr.search_skills("test")
        assert len(results) > 0

    def test_persistence(self, temp_products_dir):
        from core.skills_registry import SkillsRegistry
        sr = SkillsRegistry(str(temp_products_dir))
        sr.seed_defaults()
        sr2 = SkillsRegistry(str(temp_products_dir))
        assert len(sr2.data["skills"]) > 0
