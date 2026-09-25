"""Tests for Workflow Documentation Generator"""
import sys
import tempfile
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest


@pytest.fixture
def temp_docs_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestWorkflowDocumentationGenerator:
    def test_create_generator(self, temp_docs_dir):
        from core.workflow_docs import WorkflowDocumentationGenerator
        gen = WorkflowDocumentationGenerator()
        assert gen is not None
        assert gen.PRODUCT_NAME == "Product Forge"
        assert gen.PRODUCT_TAGLINE == "Multi-Agent Multi-Project System"

    def test_get_pipeline_workflow(self, temp_docs_dir):
        from core.workflow_docs import WorkflowDocumentationGenerator
        gen = WorkflowDocumentationGenerator()
        workflow = gen.get_pipeline_workflow()
        assert "phases" in workflow
        assert len(workflow["phases"]) >= 10
        assert "Product Forge" in workflow["name"]

    def test_pipeline_workflow_has_phases(self, temp_docs_dir):
        from core.workflow_docs import WorkflowDocumentationGenerator
        gen = WorkflowDocumentationGenerator()
        workflow = gen.get_pipeline_workflow()
        phase_names = [p["name"] for p in workflow["phases"]]
        assert "Ideation" in phase_names
        assert "Design" in phase_names
        assert "Implementation" in phase_names
        assert "DevOps" in phase_names

    def test_get_agent_workflows(self, temp_docs_dir):
        from core.workflow_docs import WorkflowDocumentationGenerator
        gen = WorkflowDocumentationGenerator()
        workflows = gen.get_agent_workflows()
        assert len(workflows) >= 15
        agent_names = [w.agent_name for w in workflows]
        assert "ideation" in agent_names
        assert "design" in agent_names
        assert "implement" in agent_names
        assert "security" in agent_names

    def test_agent_workflow_has_steps(self, temp_docs_dir):
        from core.workflow_docs import WorkflowDocumentationGenerator
        gen = WorkflowDocumentationGenerator()
        workflows = gen.get_agent_workflows()
        for w in workflows:
            assert len(w.steps) > 0
            assert w.agent_name
            assert w.agent_role
            assert w.purpose

    def test_generate_pipeline_html(self, temp_docs_dir):
        from core.workflow_docs import WorkflowDocumentationGenerator
        gen = WorkflowDocumentationGenerator()
        html = gen.generate_pipeline_html()
        assert "Product Forge" in html
        assert "<!DOCTYPE html>" in html
        assert "Multi-Agent Multi-Project System" in html
        assert "Ideation" in html
        assert "Design" in html

    def test_generate_pipeline_drawio(self, temp_docs_dir):
        from core.workflow_docs import WorkflowDocumentationGenerator
        gen = WorkflowDocumentationGenerator()
        xml = gen.generate_pipeline_drawio()
        assert "<?xml" in xml
        assert "<mxfile" in xml
        assert "Product Forge" in xml
        assert "Ideation" in xml

    def test_generate_agent_html(self, temp_docs_dir):
        from core.workflow_docs import WorkflowDocumentationGenerator
        gen = WorkflowDocumentationGenerator()
        workflows = gen.get_agent_workflows()
        if workflows:
            html = gen.generate_agent_html(workflows[0])
            assert "Product Forge" in html
            assert "<!DOCTYPE html>" in html
            assert workflows[0].agent_name.upper() in html

    def test_generate_agent_drawio(self, temp_docs_dir):
        from core.workflow_docs import WorkflowDocumentationGenerator
        gen = WorkflowDocumentationGenerator()
        workflows = gen.get_agent_workflows()
        if workflows:
            xml = gen.generate_agent_drawio(workflows[0])
            assert "<?xml" in xml
            assert "<mxfile" in xml
            assert workflows[0].agent_name in xml

    def test_save_all_documentation(self, temp_docs_dir):
        from core.workflow_docs import WorkflowDocumentationGenerator
        gen = WorkflowDocumentationGenerator()
        gen.docs_dir = temp_docs_dir
        saved = gen.save_all_documentation()
        assert len(saved) > 30  # Pipeline + 17 agents * 2 + index
        # Check that files exist
        for f in saved:
            assert Path(f).exists()
            assert Path(f).stat().st_size > 0

    def test_save_creates_index(self, temp_docs_dir):
        from core.workflow_docs import WorkflowDocumentationGenerator
        gen = WorkflowDocumentationGenerator()
        gen.docs_dir = temp_docs_dir
        gen.save_all_documentation()
        index_path = temp_docs_dir / "index.html"
        assert index_path.exists()
        content = index_path.read_text(encoding="utf-8")
        assert "Product Forge" in content

    def test_save_creates_pipeline_html(self, temp_docs_dir):
        from core.workflow_docs import WorkflowDocumentationGenerator
        gen = WorkflowDocumentationGenerator()
        gen.docs_dir = temp_docs_dir
        gen.save_all_documentation()
        pipeline_html = temp_docs_dir / "pipeline-workflow.html"
        assert pipeline_html.exists()

    def test_save_creates_pipeline_drawio(self, temp_docs_dir):
        from core.workflow_docs import WorkflowDocumentationGenerator
        gen = WorkflowDocumentationGenerator()
        gen.docs_dir = temp_docs_dir
        gen.save_all_documentation()
        pipeline_drawio = temp_docs_dir / "pipeline-workflow.drawio"
        assert pipeline_drawio.exists()

    def test_save_creates_all_agent_htmls(self, temp_docs_dir):
        from core.workflow_docs import WorkflowDocumentationGenerator
        gen = WorkflowDocumentationGenerator()
        gen.docs_dir = temp_docs_dir
        gen.save_all_documentation()
        workflows = gen.get_agent_workflows()
        for w in workflows:
            agent_html = temp_docs_dir / f"agent-{w.agent_name}.html"
            assert agent_html.exists()

    def test_save_creates_all_agent_drawios(self, temp_docs_dir):
        from core.workflow_docs import WorkflowDocumentationGenerator
        gen = WorkflowDocumentationGenerator()
        gen.docs_dir = temp_docs_dir
        gen.save_all_documentation()
        workflows = gen.get_agent_workflows()
        for w in workflows:
            agent_drawio = temp_docs_dir / f"agent-{w.agent_name}.drawio"
            assert agent_drawio.exists()

    def test_workflow_step_dataclass(self):
        from core.workflow_docs import WorkflowStep
        step = WorkflowStep(
            id="test-1",
            name="Test Step",
            description="Test",
            agent="test-agent"
        )
        assert step.id == "test-1"
        assert step.agent == "test-agent"

    def test_agent_workflow_dataclass(self):
        from core.workflow_docs import AgentWorkflow, WorkflowStep
        wf = AgentWorkflow(
            agent_name="test",
            agent_role="Tester",
            purpose="Testing",
            steps=[WorkflowStep("s1", "Step 1", "Desc", "test")]
        )
        assert wf.agent_name == "test"
        assert len(wf.steps) == 1
