"""
Skills & MCP Registry
Knowledge base of available skills and MCP servers for agent selection.

Industry Standard: GitHub-based registry with weekly refresh,
local cache with version tracking, capability descriptions.

Provides:
- Skills catalog (per-role, per-domain)
- MCP server catalog (inputs, outputs, capabilities)
- Project-specific recommendations
- Model recommendations (text/image/voice/video/numbers)
- Auto-refresh mechanism
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List


@dataclass
class Skill:
    """Skill definition"""
    id: str
    name: str
    description: str
    category: str  # code, design, security, testing, devops, marketing, etc.
    agent_types: List[str]  # Which agents can use this
    tools: List[str]  # Required tools
    source: str  # GitHub URL, docs URL, etc.
    version: str = "1.0.0"
    tags: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    input_types: List[str] = field(default_factory=list)  # text, image, voice, video, numbers
    output_types: List[str] = field(default_factory=list)
    last_updated: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Skill":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class MCPServer:
    """MCP Server definition"""
    id: str
    name: str
    description: str
    category: str  # code, data, api, filesystem, database, etc.
    inputs: List[str]  # What it accepts
    outputs: List[str]  # What it provides
    capabilities: List[str]
    source: str  # GitHub URL
    version: str = "1.0.0"
    transport: str = "stdio"  # stdio, sse, http
    requires_auth: bool = False
    tags: List[str] = field(default_factory=list)
    agent_types: List[str] = field(default_factory=list)
    last_updated: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPServer":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ModelRecommendation:
    """Model recommendation for a specific use case"""
    use_case: str  # text, image, voice, video, numbers, code
    recommended_model: str
    free_alternative: str
    cheap_alternative: str
    hybrid_option: str
    provider: str
    context_window: int = 0
    capabilities: List[str] = field(default_factory=list)
    cost_per_1k_tokens: float = 0.0
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelRecommendation":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class SkillsRegistry:
    """
    Knowledge base of skills and MCP servers.

    Data stored in: pipeline/skills-registry.json
    Auto-refreshed weekly via pipeline cron job.
    """

    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
        self.registry_dir = self.base_dir / "pipeline"
        self.registry_dir.mkdir(parents=True, exist_ok=True)

        self.registry_file = self.registry_dir / "skills-registry.json"
        self._load_or_create()

    def _load_or_create(self):
        if self.registry_file.exists():
            with open(self.registry_file, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = self._create_empty()

    def _create_empty(self) -> Dict[str, Any]:
        return {
            "$schema": "skills-registry-v1",
            "version": "1.0.0",
            "last_refresh": datetime.now(timezone.utc).isoformat(),
            "skills": [],
            "mcp_servers": [],
            "model_recommendations": [],
            "metadata": {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": "skills_registry",
            },
        }

    # ==================== SKILLS ====================

    def add_skill(self, skill: Skill) -> Skill:
        """Add or update a skill"""
        # Check if exists
        for i, s in enumerate(self.data["skills"]):
            if s["id"] == skill.id:
                self.data["skills"][i] = skill.to_dict()
                self._save()
                return skill

        skill.last_updated = datetime.now(timezone.utc).isoformat()
        self.data["skills"].append(skill.to_dict())
        self._save()
        return skill

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """Get skill by ID"""
        for s in self.data["skills"]:
            if s["id"] == skill_id:
                return Skill.from_dict(s)
        return None

    def get_skills_for_agent(self, agent_type: str) -> List[Skill]:
        """Get skills available for a specific agent type"""
        return [
            Skill.from_dict(s)
            for s in self.data["skills"]
            if agent_type in s.get("agent_types", [])
        ]

    def get_skills_by_category(self, category: str) -> List[Skill]:
        """Get skills by category"""
        return [
            Skill.from_dict(s)
            for s in self.data["skills"]
            if s.get("category") == category
        ]

    def get_skills_by_capability(self, capability: str) -> List[Skill]:
        """Get skills by capability (text, image, voice, video, numbers)"""
        return [
            Skill.from_dict(s)
            for s in self.data["skills"]
            if capability in s.get("capabilities", [])
        ]

    def search_skills(self, query: str) -> List[Skill]:
        """Search skills by name, description, or tags"""
        query_lower = query.lower()
        results = []
        for s in self.data["skills"]:
            if (
                query_lower in s.get("name", "").lower()
                or query_lower in s.get("description", "").lower()
                or query_lower in " ".join(s.get("tags", [])).lower()
            ):
                results.append(Skill.from_dict(s))
        return results

    # ==================== MCP SERVERS ====================

    def add_mcp_server(self, server: MCPServer) -> MCPServer:
        """Add or update an MCP server"""
        for i, s in enumerate(self.data["mcp_servers"]):
            if s["id"] == server.id:
                self.data["mcp_servers"][i] = server.to_dict()
                self._save()
                return server

        server.last_updated = datetime.now(timezone.utc).isoformat()
        self.data["mcp_servers"].append(server.to_dict())
        self._save()
        return server

    def get_mcp_server(self, server_id: str) -> Optional[MCPServer]:
        """Get MCP server by ID"""
        for s in self.data["mcp_servers"]:
            if s["id"] == server_id:
                return MCPServer.from_dict(s)
        return None

    def get_mcp_for_agent(self, agent_type: str) -> List[MCPServer]:
        """Get MCP servers available for a specific agent type"""
        return [
            MCPServer.from_dict(s)
            for s in self.data["mcp_servers"]
            if agent_type in s.get("agent_types", [])
        ]

    def get_mcp_by_category(self, category: str) -> List[MCPServer]:
        """Get MCP servers by category"""
        return [
            MCPServer.from_dict(s)
            for s in self.data["mcp_servers"]
            if s.get("category") == category
        ]

    # ==================== MODEL RECOMMENDATIONS ====================

    def add_model_recommendation(self, rec: ModelRecommendation) -> ModelRecommendation:
        """Add or update a model recommendation"""
        for i, r in enumerate(self.data["model_recommendations"]):
            if r["use_case"] == rec.use_case:
                self.data["model_recommendations"][i] = rec.to_dict()
                self._save()
                return rec

        self.data["model_recommendations"].append(rec.to_dict())
        self._save()
        return rec

    def get_model_for_use_case(self, use_case: str) -> Optional[ModelRecommendation]:
        """Get model recommendation for a specific use case"""
        for r in self.data["model_recommendations"]:
            if r["use_case"] == use_case:
                return ModelRecommendation.from_dict(r)
        return None

    def get_all_recommendations(self) -> List[ModelRecommendation]:
        """Get all model recommendations"""
        return [
            ModelRecommendation.from_dict(r)
            for r in self.data["model_recommendations"]
        ]

    # ==================== PROJECT RECOMMENDATIONS ====================

    def recommend_for_project(self, project_type: str, tech_stack: List[str] = None) -> Dict[str, Any]:
        """Recommend skills, MCPs, and models for a specific project"""
        # Skills by project type
        project_skills = {
            "web_app": ["tdd", "code-development", "e2e-testing", "playwright-pro"],
            "api_service": ["tdd", "code-development", "testing-strategy"],
            "mobile_app": ["tdd", "code-development", "e2e-testing"],
            "desktop_app": ["tdd", "code-development"],
            "microservice": ["tdd", "code-development", "testing-strategy", "e2e-testing"],
            "data_pipeline": ["tdd", "code-development", "testing-strategy"],
        }

        recommended_skills = project_skills.get(project_type, ["tdd", "code-development"])

        # MCP by project type
        project_mcp = {
            "web_app": ["filesystem", "browser", "database"],
            "api_service": ["filesystem", "database", "http"],
            "mobile_app": ["filesystem", "browser"],
            "desktop_app": ["filesystem"],
            "microservice": ["filesystem", "database", "http", "docker"],
        }

        recommended_mcp = project_mcp.get(project_type, ["filesystem"])

        # Models by capabilities needed
        capabilities_needed = set()
        if project_type in ("web_app", "mobile_app", "desktop_app"):
            capabilities_needed.add("text")
            capabilities_needed.add("code")
        if "image" in str(tech_stack or []):
            capabilities_needed.add("image")
        if "video" in str(tech_stack or []):
            capabilities_needed.add("video")

        recommended_models = []
        for cap in capabilities_needed:
            rec = self.get_model_for_use_case(cap)
            if rec:
                recommended_models.append(rec.to_dict())

        return {
            "project_type": project_type,
            "recommended_skills": recommended_skills,
            "recommended_mcp": recommended_mcp,
            "recommended_models": recommended_models,
        }

    # ==================== REFRESH ====================

    def mark_refreshed(self):
        """Mark registry as refreshed"""
        self.data["last_refresh"] = datetime.now(timezone.utc).isoformat()
        self._save()

    def get_refresh_status(self) -> Dict[str, Any]:
        """Get refresh status"""
        last = self.data.get("last_refresh")
        return {
            "last_refresh": last,
            "skills_count": len(self.data.get("skills", [])),
            "mcp_count": len(self.data.get("mcp_servers", [])),
            "models_count": len(self.data.get("model_recommendations", [])),
        }

    # ==================== SEED DATA ====================

    def seed_defaults(self):
        """Seed registry with default skills and MCP servers"""
        # Default skills - comprehensive list
        default_skills = [
            # Testing skills
            Skill(
                id="tdd", name="Test-Driven Development",
                description="RED-GREEN-REFACTOR cycle with vertical slicing",
                category="testing", agent_types=["implement", "fix"],
                tools=["pytest", "vitest"], source="https://github.com",
                capabilities=["code"], tags=["testing", "tdd"],
            ),
            Skill(
                id="e2e-testing", name="End-to-End Testing",
                description="Playwright and Cypress flows with stable locators",
                category="testing", agent_types=["validate"],
                tools=["playwright", "cypress"], source="https://github.com",
                capabilities=["code"], tags=["testing", "e2e"],
            ),
            Skill(
                id="unit-testing", name="Unit Testing",
                description="Isolated unit tests with mocks and fixtures",
                category="testing", agent_types=["validate", "implement"],
                tools=["pytest", "jest", "vitest"], source="https://github.com",
                capabilities=["code"], tags=["testing", "unit"],
            ),
            Skill(
                id="integration-testing", name="Integration Testing",
                description="Component integration and API testing",
                category="testing", agent_types=["validate"],
                tools=["pytest", "supertest"], source="https://github.com",
                capabilities=["code"], tags=["testing", "integration"],
            ),
            Skill(
                id="performance-testing", name="Performance Testing",
                description="Load testing and performance benchmarking",
                category="testing", agent_types=["validate"],
                tools=["k6", "locust", "artillery"], source="https://github.com",
                capabilities=["code", "numbers"], tags=["testing", "performance"],
            ),
            Skill(
                id="security-testing", name="Security Testing",
                description="SAST/DAST/SCA scanning and penetration testing",
                category="security", agent_types=["security", "validate"],
                tools=["bandit", "semgrep", "trivy"], source="https://github.com",
                capabilities=["code"], tags=["security", "testing"],
            ),
            
            # Code skills
            Skill(
                id="code-development", name="Code Development",
                description="Full-stack code implementation with design patterns",
                category="code", agent_types=["implement"],
                tools=["python", "node", "docker"], source="https://github.com",
                capabilities=["code", "text"], tags=["coding", "implementation"],
            ),
            Skill(
                id="code-review", name="Code Review",
                description="Systematic code review with best practices",
                category="code", agent_types=["code-review"],
                tools=[], source="https://github.com",
                capabilities=["code", "text"], tags=["review", "quality"],
            ),
            Skill(
                id="refactoring", name="Refactoring",
                description="Code improvement while maintaining behavior",
                category="code", agent_types=["implement", "fix"],
                tools=[], source="https://github.com",
                capabilities=["code"], tags=["refactoring", "clean-code"],
            ),
            Skill(
                id="debugging", name="Debugging",
                description="Systematic debugging and root cause analysis",
                category="code", agent_types=["fix", "implement"],
                tools=[], source="https://github.com",
                capabilities=["code", "text"], tags=["debugging", "troubleshooting"],
            ),
            
            # Architecture skills
            Skill(
                id="architecture-design", name="Architecture Design",
                description="System design, ADRs, and technical architecture",
                category="architecture", agent_types=["architect"],
                tools=[], source="https://github.com",
                capabilities=["text"], tags=["architecture", "design"],
            ),
            Skill(
                id="api-design", name="API Design",
                description="RESTful and GraphQL API design patterns",
                category="architecture", agent_types=["architect", "implement"],
                tools=[], source="https://github.com",
                capabilities=["text"], tags=["api", "rest", "graphql"],
            ),
            Skill(
                id="database-design", name="Database Design",
                description="Schema design, normalization, and optimization",
                category="architecture", agent_types=["architect", "implement-db"],
                tools=["postgresql", "mysql", "mongodb"], source="https://github.com",
                capabilities=["text"], tags=["database", "schema", "design"],
            ),
            Skill(
                id="microservices", name="Microservices Architecture",
                description="Distributed systems and service decomposition",
                category="architecture", agent_types=["architect"],
                tools=[], source="https://github.com",
                capabilities=["text"], tags=["microservices", "distributed"],
            ),
            Skill(
                id="event-driven", name="Event-Driven Architecture",
                description="Event sourcing and CQRS patterns",
                category="architecture", agent_types=["architect"],
                tools=["kafka", "rabbitmq", "redis"], source="https://github.com",
                capabilities=["text"], tags=["events", "messaging"],
            ),
            
            # Security skills
            Skill(
                id="security-audit", name="Security Audit",
                description="Comprehensive security assessment and compliance",
                category="security", agent_types=["security"],
                tools=["bandit", "semgrep", "trivy"], source="https://github.com",
                capabilities=["code"], tags=["security", "compliance"],
            ),
            Skill(
                id="owasp-compliance", name="OWASP Compliance",
                description="OWASP Top 10 vulnerability assessment",
                category="security", agent_types=["security"],
                tools=[], source="https://github.com",
                capabilities=["code", "text"], tags=["owasp", "security"],
            ),
            Skill(
                id="authentication", name="Authentication Design",
                description="Auth systems (OAuth, JWT, sessions)",
                category="security", agent_types=["architect", "implement"],
                tools=[], source="https://github.com",
                capabilities=["code"], tags=["auth", "security"],
            ),
            
            # DevOps skills
            Skill(
                id="ci-cd", name="CI/CD Pipeline",
                description="Continuous integration and deployment setup",
                category="devops", agent_types=["devops", "package"],
                tools=["github-actions", "gitlab-ci", "jenkins"], source="https://github.com",
                capabilities=["code"], tags=["ci-cd", "automation"],
            ),
            Skill(
                id="containerization", name="Containerization",
                description="Docker and container orchestration",
                category="devops", agent_types=["devops", "package"],
                tools=["docker", "kubernetes"], source="https://github.com",
                capabilities=["code"], tags=["docker", "containers"],
            ),
            Skill(
                id="monitoring", name="Monitoring & Observability",
                description="Logging, metrics, and alerting setup",
                category="devops", agent_types=["devops", "post-production"],
                tools=["prometheus", "grafana", "datadog"], source="https://github.com",
                capabilities=["text", "numbers"], tags=["monitoring", "observability"],
            ),
            
            # Design skills
            Skill(
                id="ui-design", name="UI Design",
                description="User interface design and component systems",
                category="design", agent_types=["design"],
                tools=["figma", "sketch"], source="https://github.com",
                capabilities=["text", "image"], tags=["ui", "design"],
            ),
            Skill(
                id="ux-research", name="UX Research",
                description="User research and usability testing",
                category="design", agent_types=["design", "ideation"],
                tools=[], source="https://github.com",
                capabilities=["text"], tags=["ux", "research"],
            ),
            Skill(
                id="wireframing", name="Wireframing",
                description="Low-fidelity wireframes and prototypes",
                category="design", agent_types=["design"],
                tools=[], source="https://github.com",
                capabilities=["text", "image"], tags=["wireframe", "prototype"],
            ),
            Skill(
                id="design-system", name="Design System",
                description="Component libraries and design tokens",
                category="design", agent_types=["design", "implement-ui"],
                tools=["figma", "storybook"], source="https://github.com",
                capabilities=["text", "code"], tags=["design-system", "components"],
            ),
            
            # Business skills
            Skill(
                id="market-research", name="Market Research",
                description="Market analysis and competitive intelligence",
                category="business", agent_types=["ideation"],
                tools=[], source="https://github.com",
                capabilities=["text"], tags=["market", "research"],
            ),
            Skill(
                id="product-strategy", name="Product Strategy",
                description="Product roadmap and feature prioritization",
                category="business", agent_types=["ideation"],
                tools=[], source="https://github.com",
                capabilities=["text"], tags=["strategy", "roadmap"],
            ),
            Skill(
                id="user-story", name="User Story Writing",
                description="INVEST-compliant user stories and acceptance criteria",
                category="business", agent_types=["ideation", "design"],
                tools=[], source="https://github.com",
                capabilities=["text"], tags=["user-story", "agile"],
            ),
            
            # Documentation skills
            Skill(
                id="documentation", name="Documentation",
                description="Technical writing and API documentation",
                category="documentation", agent_types=["document"],
                tools=[], source="https://github.com",
                capabilities=["text"], tags=["docs", "technical-writing"],
            ),
            Skill(
                id="api-docs", name="API Documentation",
                description="OpenAPI/Swagger specification generation",
                category="documentation", agent_types=["document"],
                tools=["swagger", "openapi"], source="https://github.com",
                capabilities=["text", "code"], tags=["api", "docs"],
            ),
            
            # Frontend skills
            Skill(
                id="react-development", name="React Development",
                description="React component development with hooks",
                category="frontend", agent_types=["implement-ui"],
                tools=["react", "nextjs"], source="https://github.com",
                capabilities=["code"], tags=["react", "frontend"],
            ),
            Skill(
                id="responsive-design", name="Responsive Design",
                description="Mobile-first responsive layouts",
                category="frontend", agent_types=["implement-ui", "design"],
                tools=["css", "tailwind"], source="https://github.com",
                capabilities=["code"], tags=["responsive", "mobile"],
            ),
            Skill(
                id="state-management", name="State Management",
                description="Client-side state management patterns",
                category="frontend", agent_types=["implement-ui"],
                tools=["redux", "zustand", "pinia"], source="https://github",
                capabilities=["code"], tags=["state", "frontend"],
            ),
            
            # Backend skills
            Skill(
                id="api-development", name="API Development",
                description="RESTful and GraphQL API implementation",
                category="backend", agent_types=["implement-api"],
                tools=["fastapi", "express", "spring"], source="https://github.com",
                capabilities=["code"], tags=["api", "backend"],
            ),
            Skill(
                id="authentication-impl", name="Authentication Implementation",
                description="Auth system implementation (OAuth, JWT)",
                category="backend", agent_types=["implement-api"],
                tools=["passport", "authlib"], source="https://github.com",
                capabilities=["code"], tags=["auth", "security"],
            ),
            Skill(
                id="caching", name="Caching Strategies",
                description="Redis and in-memory caching implementation",
                category="backend", agent_types=["implement-api", "implement-logic"],
                tools=["redis", "memcached"], source="https://github.com",
                capabilities=["code"], tags=["caching", "performance"],
            ),
            
            # Database skills
            Skill(
                id="sql-optimization", name="SQL Optimization",
                description="Query optimization and index design",
                category="database", agent_types=["implement-db"],
                tools=["postgresql", "mysql"], source="https://github.com",
                capabilities=["code"], tags=["sql", "optimization"],
            ),
            Skill(
                id="migrations", name="Database Migrations",
                description="Schema migration strategies and versioning",
                category="database", agent_types=["implement-db"],
                tools=["alembic", "flyway", "liquibase"], source="https://github.com",
                capabilities=["code"], tags=["migrations", "schema"],
            ),
            
            # Data skills
            Skill(
                id="data-modeling", name="Data Modeling",
                description="Entity-relationship and domain modeling",
                category="data", agent_types=["architect", "implement-db"],
                tools=[], source="https://github.com",
                capabilities=["text"], tags=["data", "modeling"],
            ),
            Skill(
                id="etl-pipeline", name="ETL Pipeline",
                description="Data extraction, transformation, and loading",
                category="data", agent_types=["implement-logic"],
                tools=["airflow", "dbt"], source="https://github.com",
                capabilities=["code", "text"], tags=["etl", "data"],
            ),
            
            # Compliance skills
            Skill(
                id="gdpr-compliance", name="GDPR Compliance",
                description="Data privacy and GDPR implementation",
                category="compliance", agent_types=["security"],
                tools=[], source="https://github.com",
                capabilities=["code", "text"], tags=["gdpr", "privacy"],
            ),
            Skill(
                id="hipaa-compliance", name="HIPAA Compliance",
                description="Healthcare data protection compliance",
                category="compliance", agent_types=["security"],
                tools=[], source="https://github.com",
                capabilities=["code", "text"], tags=["hipaa", "healthcare"],
            ),
            Skill(
                id="pci-compliance", name="PCI DSS Compliance",
                description="Payment card industry compliance",
                category="compliance", agent_types=["security"],
                tools=[], source="https://github.com",
                capabilities=["code", "text"], tags=["pci", "payments"],
            ),
        ]

        for skill in default_skills:
            self.add_skill(skill)

        # Default MCP servers
        default_mcp = [
            MCPServer(
                id="filesystem", name="Filesystem MCP",
                description="File system access for reading/writing files",
                category="filesystem",
                inputs=["file_path", "content"],
                outputs=["file_content", "directory_listing"],
                capabilities=["read_file", "write_file", "list_dir"],
                source="https://github.com/modelcontextprotocol/servers",
                transport="stdio",
                agent_types=["ideation", "design", "architect", "implement", "validate", "fix", "document"],
            ),
            MCPServer(
                id="database", name="Database MCP",
                description="Database access for queries and schema management",
                category="database",
                inputs=["query", "schema"],
                outputs=["query_results", "schema_info"],
                capabilities=["query", "migrate", "backup"],
                source="https://github.com/modelcontextprotocol/servers",
                transport="stdio",
                agent_types=["implement", "validate", "devops"],
            ),
            MCPServer(
                id="http", name="HTTP MCP",
                description="HTTP client for API calls and web requests",
                category="api",
                inputs=["url", "method", "headers", "body"],
                outputs=["response_body", "status_code"],
                capabilities=["get", "post", "put", "delete"],
                source="https://github.com/modelcontextprotocol/servers",
                transport="stdio",
                agent_types=["implement", "validate", "security", "devops"],
            ),
            MCPServer(
                id="browser", name="Browser MCP",
                description="Browser automation for testing and scraping",
                category="browser",
                inputs=["url", "action"],
                outputs=["page_content", "screenshot"],
                capabilities=["navigate", "click", "type", "screenshot"],
                source="https://github.com/modelcontextprotocol/servers",
                transport="stdio",
                agent_types=["validate", "design"],
            ),
            MCPServer(
                id="docker", name="Docker MCP",
                description="Docker container management for deployment",
                category="devops",
                inputs=["image", "command"],
                outputs=["container_id", "logs"],
                capabilities=["build", "run", "stop", "push"],
                source="https://github.com/modelcontextprotocol/servers",
                transport="stdio",
                agent_types=["devops", "package"],
            ),
        ]

        for mcp in default_mcp:
            self.add_mcp_server(mcp)

        # Default model recommendations
        default_models = [
            ModelRecommendation(
                use_case="text",
                recommended_model="opencode/mimo-v2.5-free",
                free_alternative="opencode/mimo-v2.5-free",
                cheap_alternative="opencode/hy3-free",
                hybrid_option="opencode/mimo-v2.5-free",
                provider="opencode",
                capabilities=["text", "code", "reasoning"],
            ),
            ModelRecommendation(
                use_case="code",
                recommended_model="opencode/mimo-v2.5-free",
                free_alternative="opencode/mimo-v2.5-free",
                cheap_alternative="opencode/hy3-free",
                hybrid_option="opencode/big-pickle",
                provider="opencode",
                capabilities=["code", "reasoning"],
            ),
            ModelRecommendation(
                use_case="image",
                recommended_model="openai/dall-e-3",
                free_alternative="stable-diffusion",
                cheap_alternative="flux-schnell",
                hybrid_option="openai/dall-e-3",
                provider="openai",
                capabilities=["image-generation", "image-analysis"],
            ),
            ModelRecommendation(
                use_case="voice",
                recommended_model="openai/whisper-1",
                free_alternative="whisper-local",
                cheap_alternative="openai/whisper-1",
                hybrid_option="openai/whisper-1",
                provider="openai",
                capabilities=["speech-to-text", "text-to-speech"],
            ),
            ModelRecommendation(
                use_case="video",
                recommended_model="runway/gen-3",
                free_alternative="none",
                cheap_alternative="runway/gen-3",
                hybrid_option="runway/gen-3",
                provider="runway",
                capabilities=["video-generation", "video-analysis"],
            ),
            ModelRecommendation(
                use_case="numbers",
                recommended_model="openai/gpt-4o",
                free_alternative="opencode/mimo-v2.5-free",
                cheap_alternative="opencode/hy3-free",
                hybrid_option="opencode/mimo-v2.5-free",
                provider="opencode",
                capabilities=["reasoning", "math", "data-analysis"],
            ),
        ]

        for model in default_models:
            self.add_model_recommendation(model)

        self.mark_refreshed()

    def _save(self):
        """Save registry to disk"""
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        with open(self.registry_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)
