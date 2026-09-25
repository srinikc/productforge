"""
BYOT (Bring Your Own Tools/Models) Integration Layer
Allows users to integrate custom models, MCP servers, tools, and services
"""
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field, asdict


@dataclass
class CustomModel:
    """Custom AI model configuration"""
    name: str
    provider: str  # openai, anthropic, cohere, custom
    model_id: str
    api_key: Optional[str] = None
    endpoint: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)  # text, image, code, etc.
    context_window: int = 4096
    cost_per_token: float = 0.0
    enabled: bool = True


@dataclass
class CustomMCPServer:
    """Custom MCP server configuration"""
    name: str
    description: str
    command: str
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    capabilities: List[str] = field(default_factory=list)


@dataclass
class CustomTool:
    """Custom tool/integration"""
    name: str
    description: str
    type: str  # api, cli, webhook, function
    config: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    required_permissions: List[str] = field(default_factory=list)


class BYOTIntegrationManager:
    """Manages BYOT (Bring Your Own Tools) integrations"""

    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
        self.config_dir = self.base_dir / "byot"
        self.config_dir.mkdir(exist_ok=True)

        self.models: Dict[str, CustomModel] = {}
        self.mcp_servers: Dict[str, CustomMCPServer] = {}
        self.tools: Dict[str, CustomTool] = {}

    def register_model(self, model: CustomModel) -> bool:
        """Register a custom model"""
        try:
            self.models[model.name] = model
            self._save_config()
            return True
        except Exception:
            return False

    def get_model(self, name: str) -> Optional[CustomModel]:
        """Get a model by name"""
        return self.models.get(name)

    def list_models(self, enabled_only: bool = False) -> List[CustomModel]:
        """List registered models"""
        models = list(self.models.values())
        if enabled_only:
            models = [m for m in models if m.enabled]
        return models

    def register_mcp_server(self, server: CustomMCPServer) -> bool:
        """Register a custom MCP server"""
        try:
            self.mcp_servers[server.name] = server
            self._save_config()
            return True
        except Exception:
            return False

    def get_mcp_server(self, name: str) -> Optional[CustomMCPServer]:
        """Get an MCP server by name"""
        return self.mcp_servers.get(name)

    def list_mcp_servers(self, enabled_only: bool = False) -> List[CustomMCPServer]:
        """List registered MCP servers"""
        servers = list(self.mcp_servers.values())
        if enabled_only:
            servers = [s for s in servers if s.enabled]
        return servers

    def register_tool(self, tool: CustomTool) -> bool:
        """Register a custom tool"""
        try:
            self.tools[tool.name] = tool
            self._save_config()
            return True
        except Exception:
            return False

    def get_tool(self, name: str) -> Optional[CustomTool]:
        """Get a tool by name"""
        return self.tools.get(name)

    def list_tools(self, enabled_only: bool = False) -> List[CustomTool]:
        """List registered tools"""
        tools = list(self.tools.values())
        if enabled_only:
            tools = [t for t in tools if t.enabled]
        return tools

    def find_models_by_capability(self, capability: str) -> List[CustomModel]:
        """Find models with a specific capability"""
        return [m for m in self.models.values()
                if capability in m.capabilities and m.enabled]

    def find_tools_by_type(self, tool_type: str) -> List[CustomTool]:
        """Find tools of a specific type"""
        return [t for t in self.tools.values()
                if t.type == tool_type and t.enabled]

    def _save_config(self):
        """Save configuration to disk"""
        config = {
            "models": {name: asdict(m) for name, m in self.models.items()},
            "mcp_servers": {name: asdict(s) for name, s in self.mcp_servers.items()},
            "tools": {name: asdict(t) for name, t in self.tools.items()},
            "last_updated": datetime.now().isoformat()
        }

        config_file = self.config_dir / "byot_config.json"
        import json
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    def generate_integration_report(self) -> str:
        """Generate integration report"""
        report = f"""# BYOT Integration Report

Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Summary

- **Total Models:** {len(self.models)}
- **Total MCP Servers:** {len(self.mcp_servers)}
- **Total Tools:** {len(self.tools)}

## Registered Models

"""
        for model in self.list_models():
            report += f"### {model.name}\n"
            report += f"- **Provider:** {model.provider}\n"
            report += f"- **Model ID:** {model.model_id}\n"
            report += f"- **Capabilities:** {', '.join(model.capabilities)}\n"
            report += f"- **Context Window:** {model.context_window}\n"
            report += f"- **Enabled:** {model.enabled}\n\n"

        report += "## Registered MCP Servers\n\n"
        for server in self.list_mcp_servers():
            report += f"### {server.name}\n"
            report += f"- **Description:** {server.description}\n"
            report += f"- **Command:** {server.command}\n"
            report += f"- **Enabled:** {server.enabled}\n"
            if server.capabilities:
                report += f"- **Capabilities:** {', '.join(server.capabilities)}\n"
            report += "\n"

        report += "## Registered Tools\n\n"
        for tool in self.list_tools():
            report += f"### {tool.name}\n"
            report += f"- **Description:** {tool.description}\n"
            report += f"- **Type:** {tool.type}\n"
            report += f"- **Enabled:** {tool.enabled}\n"
            if tool.required_permissions:
                report += f"- **Required Permissions:** {', '.join(tool.required_permissions)}\n"
            report += "\n"

        return report
