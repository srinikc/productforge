"""Tests for BYOT Integration"""
import sys
import tempfile
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestBYOTIntegrationManager:
    def test_create_manager(self, temp_dir):
        from core.byot_integration import BYOTIntegrationManager
        mgr = BYOTIntegrationManager(temp_dir)
        assert mgr is not None
        assert len(mgr.models) == 0
        assert len(mgr.mcp_servers) == 0
        assert len(mgr.tools) == 0

    def test_register_model(self, temp_dir):
        from core.byot_integration import BYOTIntegrationManager, CustomModel
        mgr = BYOTIntegrationManager(temp_dir)
        model = CustomModel(
            name="gpt-4",
            provider="openai",
            model_id="gpt-4",
            capabilities=["text", "code"],
            context_window=8192
        )
        result = mgr.register_model(model)
        assert result is True
        assert len(mgr.models) == 1

    def test_get_model(self, temp_dir):
        from core.byot_integration import BYOTIntegrationManager, CustomModel
        mgr = BYOTIntegrationManager(temp_dir)
        model = CustomModel(
            name="gpt-4",
            provider="openai",
            model_id="gpt-4",
            capabilities=["text"]
        )
        mgr.register_model(model)
        retrieved = mgr.get_model("gpt-4")
        assert retrieved is not None
        assert retrieved.provider == "openai"

    def test_list_models(self, temp_dir):
        from core.byot_integration import BYOTIntegrationManager, CustomModel
        mgr = BYOTIntegrationManager(temp_dir)
        for i in range(3):
            model = CustomModel(
                name=f"model-{i}",
                provider="custom",
                model_id=f"m-{i}",
                capabilities=["text"],
                enabled=(i < 2)
            )
            mgr.register_model(model)
        all_models = mgr.list_models()
        assert len(all_models) == 3
        enabled = mgr.list_models(enabled_only=True)
        assert len(enabled) == 2

    def test_register_mcp_server(self, temp_dir):
        from core.byot_integration import BYOTIntegrationManager, CustomMCPServer
        mgr = BYOTIntegrationManager(temp_dir)
        server = CustomMCPServer(
            name="test-server",
            description="Test server",
            command="python",
            args=["server.py"]
        )
        result = mgr.register_mcp_server(server)
        assert result is True
        assert len(mgr.mcp_servers) == 1

    def test_get_mcp_server(self, temp_dir):
        from core.byot_integration import BYOTIntegrationManager, CustomMCPServer
        mgr = BYOTIntegrationManager(temp_dir)
        server = CustomMCPServer(
            name="test-server",
            description="Test",
            command="python"
        )
        mgr.register_mcp_server(server)
        retrieved = mgr.get_mcp_server("test-server")
        assert retrieved is not None
        assert retrieved.command == "python"

    def test_register_tool(self, temp_dir):
        from core.byot_integration import BYOTIntegrationManager, CustomTool
        mgr = BYOTIntegrationManager(temp_dir)
        tool = CustomTool(
            name="github-api",
            description="GitHub API integration",
            type="api",
            required_permissions=["read:repo"]
        )
        result = mgr.register_tool(tool)
        assert result is True
        assert len(mgr.tools) == 1

    def test_get_tool(self, temp_dir):
        from core.byot_integration import BYOTIntegrationManager, CustomTool
        mgr = BYOTIntegrationManager(temp_dir)
        tool = CustomTool(
            name="github-api",
            description="Test",
            type="api"
        )
        mgr.register_tool(tool)
        retrieved = mgr.get_tool("github-api")
        assert retrieved is not None
        assert retrieved.type == "api"

    def test_find_models_by_capability(self, temp_dir):
        from core.byot_integration import BYOTIntegrationManager, CustomModel
        mgr = BYOTIntegrationManager(temp_dir)
        model1 = CustomModel(
            name="text-model",
            provider="openai",
            model_id="gpt-4",
            capabilities=["text", "code"]
        )
        model2 = CustomModel(
            name="image-model",
            provider="custom",
            model_id="dall-e",
            capabilities=["image"]
        )
        mgr.register_model(model1)
        mgr.register_model(model2)
        text_models = mgr.find_models_by_capability("text")
        assert len(text_models) == 1
        assert text_models[0].name == "text-model"

    def test_find_tools_by_type(self, temp_dir):
        from core.byot_integration import BYOTIntegrationManager, CustomTool
        mgr = BYOTIntegrationManager(temp_dir)
        for i, t in enumerate(["api", "cli", "api", "webhook"]):
            tool = CustomTool(
                name=f"tool-{i}-{t}",
                description="Test",
                type=t
            )
            mgr.register_tool(tool)
        api_tools = mgr.find_tools_by_type("api")
        assert len(api_tools) == 2

    def test_generate_integration_report(self, temp_dir):
        from core.byot_integration import BYOTIntegrationManager, CustomModel, CustomMCPServer, CustomTool
        mgr = BYOTIntegrationManager(temp_dir)
        model = CustomModel(
            name="test-model",
            provider="custom",
            model_id="m-1",
            capabilities=["text"]
        )
        server = CustomMCPServer(
            name="test-server",
            description="Test",
            command="python"
        )
        tool = CustomTool(
            name="test-tool",
            description="Test",
            type="api"
        )
        mgr.register_model(model)
        mgr.register_mcp_server(server)
        mgr.register_tool(tool)
        report = mgr.generate_integration_report()
        assert "BYOT" in report
        assert "Total Models" in report
        assert "Total MCP Servers" in report
        assert "Total Tools" in report
        assert "test-model" in report
        assert "test-server" in report
        assert "test-tool" in report
