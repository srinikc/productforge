"""
Skills Registry - Registry of skills, MCP servers, and model recommendations.

Phase 2.6: Skills registry for capability discovery.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict, field


@dataclass
class Skill:
    """A skill that can be used by agents."""
    id: str
    name: str
    description: str
    category: str
    agent_types: list[str]
    tools: list[str] = field(default_factory=list)
    source: str = ""
    capabilities: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    added_at: str = ""
    
    def __post_init__(self):
        if not self.added_at:
            self.added_at = datetime.utcnow().isoformat()


@dataclass
class MCPServer:
    """An MCP (Model Context Protocol) server definition."""
    id: str
    name: str
    description: str
    category: str
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    source: str = ""
    command: str = ""
    args: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    added_at: str = ""
    
    def __post_init__(self):
        if not self.added_at:
            self.added_at = datetime.utcnow().isoformat()


@dataclass
class ModelRecommendation:
    """Model recommendation for a use case."""
    use_case: str
    recommended_model: str
    free_alternative: Optional[str] = None
    cheap_alternative: Optional[str] = None
    hybrid_option: Optional[str] = None
    provider: str = ""
    rationale: str = ""
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0


class SkillsRegistry:
    """Central registry for skills, MCP servers, and model recommendations."""
    
    REGISTRY_FILE = "skills-registry.json"   # canonical spelling (hyphen)
    
    DEFAULT_SKILLS = [
        Skill(
            id="python-coding",
            name="Python Coding",
            description="Write idiomatic Python code following PEP 8",
            category="coding",
            agent_types=["implement", "fix"],
            tools=["python", "pytest", "ruff"],
            capabilities=["code", "test"],
            tags=["python", "backend"],
        ),
        Skill(
            id="typescript-coding",
            name="TypeScript Coding",
            description="Write TypeScript code with React 19 and Next.js 15",
            category="coding",
            agent_types=["implement", "fix"],
            tools=["typescript", "next", "react"],
            capabilities=["code", "ui"],
            tags=["typescript", "frontend", "react"],
        ),
        Skill(
            id="api-design",
            name="REST API Design",
            description="Design RESTful APIs with proper status codes and error handling",
            category="api",
            agent_types=["design", "architect"],
            tools=["openapi", "fastapi"],
            capabilities=["design", "api"],
            tags=["api", "rest"],
        ),
        Skill(
            id="postgres-design",
            name="PostgreSQL Database Design",
            description="Design PostgreSQL schemas with proper normalization and RLS",
            category="database",
            agent_types=["architect", "implement"],
            tools=["postgres", "sqlalchemy"],
            capabilities=["database", "schema"],
            tags=["postgres", "database"],
        ),
        Skill(
            id="docker-packaging",
            name="Docker Containerization",
            description="Package applications as multi-stage Docker images",
            category="infrastructure",
            agent_types=["implement", "package"],
            tools=["docker"],
            capabilities=["build", "package"],
            tags=["docker", "containers"],
        ),
        Skill(
            id="unit-testing",
            name="Unit Testing",
            description="Write comprehensive unit tests with pytest/vitest",
            category="testing",
            agent_types=["implement", "validate"],
            tools=["pytest", "vitest"],
            capabilities=["test", "quality"],
            tags=["testing"],
        ),
    ]
    
    DEFAULT_MCP_SERVERS = [
        MCPServer(
            id="playwright-mcp",
            name="Playwright MCP",
            description="Browser automation for E2E testing",
            category="testing",
            inputs=["url", "actions"],
            outputs=["results", "screenshots"],
            capabilities=["e2e", "browser"],
            source="https://github.com/microsoft/playwright-mcp",
            command="npx",
            args=["-y", "@playwright/mcp"],
        ),
        MCPServer(
            id="github-mcp",
            name="GitHub MCP",
            description="Interact with GitHub for issues, PRs, and code",
            category="vcs",
            inputs=["repo", "action"],
            outputs=["result"],
            capabilities=["git", "github"],
            source="https://github.com/modelcontextprotocol/servers",
        ),
        MCPServer(
            id="filesystem-mcp",
            name="Filesystem MCP",
            description="Read and write files in the local filesystem",
            category="filesystem",
            inputs=["path", "operation"],
            outputs=["content"],
            capabilities=["file", "io"],
            source="https://github.com/modelcontextprotocol/servers",
        ),
    ]
    
    DEFAULT_MODEL_RECOMMENDATIONS = [
        ModelRecommendation(
            use_case="code",
            recommended_model="gpt-4-turbo",
            free_alternative="mimo",
            cheap_alternative="hy3",
            hybrid_option="gpt-4-turbo",
            provider="openai",
            rationale="Code generation needs strong reasoning",
        ),
        ModelRecommendation(
            use_case="architecture",
            recommended_model="claude-3-opus",
            free_alternative="mimo",
            cheap_alternative="claude-3-sonnet",
            hybrid_option="claude-3-sonnet",
            provider="anthropic",
            rationale="Architecture needs deep understanding",
        ),
        ModelRecommendation(
            use_case="review",
            recommended_model="gpt-4-turbo",
            free_alternative="mimo",
            cheap_alternative="hy3",
            hybrid_option="gpt-4-turbo",
            provider="openai",
            rationale="Code review needs precision",
        ),
        ModelRecommendation(
            use_case="validation",
            recommended_model="gpt-3.5-turbo",
            free_alternative="mimo",
            cheap_alternative="gpt-3.5-turbo",
            hybrid_option="gpt-3.5-turbo",
            provider="openai",
            rationale="Validation is rule-based, cheaper model sufficient",
        ),
        ModelRecommendation(
            use_case="documentation",
            recommended_model="claude-3-sonnet",
            free_alternative="mimo",
            cheap_alternative="hy3",
            hybrid_option="claude-3-sonnet",
            provider="anthropic",
            rationale="Documentation needs clarity, not deep reasoning",
        ),
    ]
    
    def __init__(self, products_dir: str = "products"):
        self.products_dir = Path(products_dir)
        self.registry_file = self.products_dir / ".pipeline" / self.REGISTRY_FILE
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        self._migrate_legacy()
        
        if not self.registry_file.exists():
            self._initialize()
        
        self.data = self._load()

    def _migrate_legacy(self) -> None:
        """One-time: legacy misspelled `skills_registry.json` -> canonical hyphen form."""
        legacy = self.registry_file.parent / "skills_registry.json"
        try:
            if legacy.exists() and not self.registry_file.exists():
                legacy.rename(self.registry_file)
        except OSError:
            pass
    
    def _initialize(self) -> None:
        """Initialize with default skills and models."""
        initial = {
            "skills": [asdict(s) for s in self.DEFAULT_SKILLS],
            "mcp_servers": [asdict(s) for s in self.DEFAULT_MCP_SERVERS],
            "model_recommendations": [asdict(m) for m in self.DEFAULT_MODEL_RECOMMENDATIONS],
        }
        self.registry_file.write_text(json.dumps(initial, indent=2, default=str))
    
    def _load(self) -> dict:
        """Load registry data."""
        try:
            return json.loads(self.registry_file.read_text())
        except (json.JSONDecodeError, OSError):
            self._initialize()
            return json.loads(self.registry_file.read_text())
    
    def _save(self) -> None:
        """Save registry data."""
        self.registry_file.write_text(json.dumps(self.data, indent=2, default=str))
    
    def seed_defaults(self) -> None:
        """Seed default skills and models (if not already present)."""
        if not self.data.get("skills"):
            self.data["skills"] = [asdict(s) for s in self.DEFAULT_SKILLS]
        if not self.data.get("mcp_servers"):
            self.data["mcp_servers"] = [asdict(s) for s in self.DEFAULT_MCP_SERVERS]
        if not self.data.get("model_recommendations"):
            self.data["model_recommendations"] = [asdict(m) for m in self.DEFAULT_MODEL_RECOMMENDATIONS]
        self._save()
    
    def add_skill(self, skill: Skill) -> None:
        """Add a skill to the registry."""
        self.data["skills"].append(asdict(skill))
        self._save()
    
    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """Get a skill by ID."""
        for s in self.data.get("skills", []):
            if s["id"] == skill_id:
                return Skill(**s)
        return None
    
    def list_skills(self, category: Optional[str] = None) -> list[Skill]:
        """List all skills, optionally filtered by category."""
        skills = self.data.get("skills", [])
        
        if category:
            skills = [s for s in skills if s.get("category") == category]
        
        return [Skill(**s) for s in skills]
    
    def get_skills_for_agent(self, agent_type: str) -> list[Skill]:
        """Get all skills for a specific agent type."""
        return [
            Skill(**s) for s in self.data.get("skills", [])
            if agent_type in s.get("agent_types", [])
        ]
    
    def search_skills(self, query: str) -> list[Skill]:
        """Search skills by name, description, or tags."""
        query_lower = query.lower()
        results = []
        
        for s in self.data.get("skills", []):
            if (query_lower in s.get("name", "").lower() or
                query_lower in s.get("description", "").lower() or
                any(query_lower in tag.lower() for tag in s.get("tags", []))):
                results.append(Skill(**s))
        
        return results
    
    def add_mcp_server(self, server: MCPServer) -> None:
        """Add an MCP server to the registry."""
        self.data["mcp_servers"].append(asdict(server))
        self._save()
    
    def get_mcp_server(self, server_id: str) -> Optional[MCPServer]:
        """Get an MCP server by ID."""
        for s in self.data.get("mcp_servers", []):
            if s["id"] == server_id:
                return MCPServer(**s)
        return None
    
    def list_mcp_servers(self, category: Optional[str] = None) -> list[MCPServer]:
        """List MCP servers."""
        servers = self.data.get("mcp_servers", [])
        
        if category:
            servers = [s for s in servers if s.get("category") == category]
        
        return [MCPServer(**s) for s in servers]
    
    def add_model_recommendation(self, recommendation: ModelRecommendation) -> None:
        """Add a model recommendation."""
        self.data["model_recommendations"].append(asdict(recommendation))
        self._save()
    
    def get_model_for_use_case(self, use_case: str) -> Optional[ModelRecommendation]:
        """Get model recommendation for a use case."""
        for m in self.data.get("model_recommendations", []):
            if m["use_case"] == use_case:
                return ModelRecommendation(**m)
        return None
    
    def list_model_recommendations(self) -> list[ModelRecommendation]:
        """List all model recommendations."""
        return [ModelRecommendation(**m) for m in self.data.get("model_recommendations", [])]
    
    def recommend_for_project(self, project_type: str) -> dict:
        """Recommend skills and MCP servers for a project type."""
        # Map project types to recommended skills
        skill_map = {
            "web_app": ["python-coding", "typescript-coding", "api-design", "postgres-design", "docker-packaging"],
            "api": ["python-coding", "api-design", "postgres-design", "docker-packaging"],
            "cli": ["python-coding"],
            "library": ["python-coding", "typescript-coding"],
            "mobile": ["typescript-coding"],
        }
        
        recommended_skill_ids = skill_map.get(project_type, ["python-coding"])
        recommended_skills = [
            self.get_skill(sid) for sid in recommended_skill_ids
            if self.get_skill(sid)
        ]
        
        # Always include some MCP servers
        recommended_mcp = self.list_mcp_servers()[:3]
        
        # Recommend models per use case
        use_cases = ["code", "architecture", "review", "validation", "documentation"]
        recommended_models = {
            uc: self.get_model_for_use_case(uc) for uc in use_cases
            if self.get_model_for_use_case(uc)
        }
        
        return {
            "project_type": project_type,
            "recommended_skills": [s.id for s in recommended_skills if s],
            "recommended_mcp": [m.id for m in recommended_mcp],
            "recommended_models": {k: v.recommended_model for k, v in recommended_models.items()},
        }
