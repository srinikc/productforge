"""
Business Model & Skills Selector

Selects relevant skills and knowledge based on:
- Business model (SaaS, marketplace, etc.)
- Product domain (fintech, healthtech, etc.)
- Techstack (React, FastAPI, PostgreSQL, etc.)
- Agent type and stage

Auto-selects skills that help in design, architecture, and implementation.
"""
import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime


@dataclass
class BusinessModel:
    """Business model definition."""
    id: str
    name: str
    description: str
    domain: str
    tags: List[str] = field(default_factory=list)
    key_features: List[str] = field(default_factory=list)
    recommended_skills: List[str] = field(default_factory=list)
    recommended_guidelines: List[str] = field(default_factory=list)
    architecture_patterns: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class SkillRecommendation:
    """Recommended skill for an agent."""
    skill_id: str
    name: str
    reason: str
    relevance_score: float
    source: str  # business_model, domain, techstack, agent_type
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class SelectionResult:
    """Result of business model and skills selection."""
    project: str
    business_model: Optional[BusinessModel]
    domain: str
    techstack: List[str]
    recommended_skills: List[SkillRecommendation]
    recommended_guidelines: List[str]
    architecture_patterns: List[str]
    agent_skills: Dict[str, List[SkillRecommendation]]
    
    def to_dict(self) -> Dict:
        return {
            "project": self.project,
            "business_model": self.business_model.to_dict() if self.business_model else None,
            "domain": self.domain,
            "techstack": self.techstack,
            "recommended_skills": [s.to_dict() for s in self.recommended_skills],
            "recommended_guidelines": self.recommended_guidelines,
            "architecture_patterns": self.architecture_patterns,
            "agent_skills": {k: [s.to_dict() for s in v] for k, v in self.agent_skills.items()},
        }


# Business Models Database
BUSINESS_MODELS = {
    "saas": BusinessModel(
        id="saas",
        name="SaaS (Software as a Service)",
        description="Cloud-based software with subscription billing",
        domain="technology",
        tags=["saas", "subscription", "cloud", "b2b", "b2c"],
        key_features=[
            "User authentication and authorization",
            "Subscription management",
            "Usage metering",
            "Multi-tenancy",
            "Billing integration",
            "Dashboard/analytics",
        ],
        recommended_skills=[
            "auth-management",
            "subscription-billing",
            "usage-metering",
            "multi-tenancy",
            "dashboard-analytics",
        ],
        recommended_guidelines=[
            "docs/guidelines/business/saas.md",
            "docs/guidelines/caching/strategies.md",
            "docs/guidelines/scaling/strategies.md",
        ],
        architecture_patterns=["multi-tenant", "event-driven", "microservices"],
    ),
    "marketplace": BusinessModel(
        id="marketplace",
        name="Marketplace",
        description="Two-sided platform connecting buyers and sellers",
        domain="ecommerce",
        tags=["marketplace", "platform", "two-sided", "ecommerce"],
        key_features=[
            "User profiles (buyers/sellers)",
            "Product/service listings",
            "Search and discovery",
            "Order management",
            "Payment processing",
            "Reviews/ratings",
            "Messaging",
        ],
        recommended_skills=[
            "search-discovery",
            "payment-processing",
            "order-management",
            "messaging-system",
            "reviews-ratings",
        ],
        recommended_guidelines=[
            "docs/guidelines/business/marketplace.md",
            "docs/guidelines/api/rest.md",
            "docs/guidelines/database/postgresql.md",
        ],
        architecture_patterns=["search-indexed", "event-sourcing", "cqrs"],
    ),
    "ecommerce": BusinessModel(
        id="ecommerce",
        name="E-Commerce",
        description="Online store with product catalog and checkout",
        domain="retail",
        tags=["ecommerce", "store", "retail", "shopping"],
        key_features=[
            "Product catalog",
            "Shopping cart",
            "Checkout flow",
            "Payment processing",
            "Order tracking",
            "Inventory management",
        ],
        recommended_skills=[
            "product-catalog",
            "cart-checkout",
            "payment-processing",
            "inventory-management",
            "order-tracking",
        ],
        recommended_guidelines=[
            "docs/guidelines/business/ecommerce.md",
            "docs/guidelines/security/owasp.md",
            "docs/guidelines/performance/optimization.md",
        ],
        architecture_patterns=["catalog-driven", "event-driven", "cached"],
    ),
    "fintech": BusinessModel(
        id="fintech",
        name="FinTech",
        description="Financial technology product",
        domain="finance",
        tags=["fintech", "finance", "payments", "banking"],
        key_features=[
            "Account management",
            "Transaction processing",
            "Compliance (KYC/AML)",
            "Security (PCI DSS)",
            "Reporting/analytics",
            "Integration with financial APIs",
        ],
        recommended_skills=[
            "transaction-processing",
            "compliance-kyc",
            "security-pci",
            "financial-reporting",
            "api-integration",
        ],
        recommended_guidelines=[
            "docs/guidelines/business/fintech.md",
            "docs/guidelines/security/owasp.md",
            "docs/guidelines/compliance/regulations.md",
        ],
        architecture_patterns=["event-sourced", "audit-logged", "encrypted"],
    ),
    "healthtech": BusinessModel(
        id="healthtech",
        name="HealthTech",
        description="Healthcare technology product",
        domain="healthcare",
        tags=["healthtech", "healthcare", "medical", "hipaa"],
        key_features=[
            "Patient management",
            "Appointment scheduling",
            "Medical records (EHR/EMR)",
            "Telehealth",
            "Compliance (HIPAA)",
            "Integration with health systems",
        ],
        recommended_skills=[
            "patient-management",
            "scheduling",
            "ehr-integration",
            "telehealth",
            "compliance-hipaa",
        ],
        recommended_guidelines=[
            "docs/guidelines/business/healthtech.md",
            "docs/guidelines/security/owasp.md",
            "docs/guidelines/compliance/regulations.md",
        ],
        architecture_patterns=["hipaa-compliant", "audit-logged", "encrypted"],
    ),
    "edtech": BusinessModel(
        id="edtech",
        name="EdTech",
        description="Education technology product",
        domain="education",
        tags=["edtech", "education", "learning", "lms"],
        key_features=[
            "Course management",
            "Content delivery",
            "Assessments/quizzes",
            "Progress tracking",
            "User roles (student/teacher)",
            "Reporting",
        ],
        recommended_skills=[
            "course-management",
            "content-delivery",
            "assessment-engine",
            "progress-tracking",
            "role-management",
        ],
        recommended_guidelines=[
            "docs/guidelines/business/edtech.md",
            "docs/guidelines/frontend/react.md",
            "docs/guidelines/performance/optimization.md",
        ],
        architecture_patterns=["content-driven", "progress-tracked", "role-based"],
    ),
    "internal-tool": BusinessModel(
        id="internal-tool",
        name="Internal Tool",
        description="Tool built for internal team productivity",
        domain="productivity",
        tags=["internal", "productivity", "dashboard", "admin"],
        key_features=[
            "User authentication",
            "Role-based access",
            "Dashboard",
            "CRUD operations",
            "Reporting",
            "Integration with internal systems",
        ],
        recommended_skills=[
            "auth-management",
            "role-access",
            "dashboard-builder",
            "crud-operations",
            "reporting",
        ],
        recommended_guidelines=[
            "docs/guidelines/business/enterprise.md",
            "docs/guidelines/frontend/react.md",
            "docs/guidelines/backend/fastapi.md",
        ],
        architecture_patterns=["crud", "dashboard", "role-based"],
    ),
    "api-product": BusinessModel(
        id="api-product",
        name="API Product",
        description="Standalone API service with usage-based pricing",
        domain="developer",
        tags=["api", "developer", "rest", "graphql"],
        key_features=[
            "API design",
            "Documentation",
            "Rate limiting",
            "Usage metering",
            "Developer portal",
            "SDK/client libraries",
        ],
        recommended_skills=[
            "api-design",
            "documentation",
            "rate-limiting",
            "usage-metering",
            "sdk-generation",
        ],
        recommended_guidelines=[
            "docs/guidelines/api/rest.md",
            "docs/guidelines/backend/fastapi.md",
            "docs/guidelines/performance/optimization.md",
        ],
        architecture_patterns=["restful", "rate-limited", "documented"],
    ),
}

# Domain to guidelines mapping
DOMAIN_GUIDELINES = {
    "finance": ["docs/guidelines/business/fintech.md"],
    "healthcare": ["docs/guidelines/business/healthtech.md"],
    "education": ["docs/guidelines/business/edtech.md"],
    "ecommerce": ["docs/guidelines/business/ecommerce.md", "docs/guidelines/business/marketplace.md"],
    "technology": ["docs/guidelines/business/saas.md"],
    "productivity": ["docs/guidelines/business/enterprise.md"],
    "developer": ["docs/guidelines/business/api-platform.md"],
    "gaming": ["docs/guidelines/business/gaming.md"],
    "iot": ["docs/guidelines/business/iot.md"],
    "media": ["docs/guidelines/business/media-entertainment.md"],
}

# Techstack to guidelines mapping
TECHSTACK_GUIDELINES = {
    "react": ["docs/guidelines/frontend/react.md"],
    "nextjs": ["docs/guidelines/frontend/react.md", "docs/guidelines/rendering/strategies.md"],
    "vue": ["docs/guidelines/frontend/react.md"],  # Similar patterns
    "angular": ["docs/guidelines/frontend/react.md"],
    "svelte": ["docs/guidelines/frontend/react.md"],
    "flutter": ["docs/guidelines/frontend/react.md"],  # Mobile patterns
    "react-native": ["docs/guidelines/frontend/react.md"],
    "fastapi": ["docs/guidelines/backend/fastapi.md"],
    "flask": ["docs/guidelines/backend/fastapi.md"],
    "django": ["docs/guidelines/backend/fastapi.md"],
    "express": ["docs/guidelines/backend/fastapi.md"],
    "nestjs": ["docs/guidelines/backend/fastapi.md"],
    "spring": ["docs/guidelines/backend/fastapi.md"],
    "dotnet": ["docs/guidelines/backend/fastapi.md"],
    "postgresql": ["docs/guidelines/database/postgresql.md"],
    "mysql": ["docs/guidelines/database/postgresql.md"],
    "mongodb": ["docs/guidelines/database/postgresql.md"],
    "redis": ["docs/guidelines/caching/strategies.md"],
    "docker": ["docs/guidelines/infrastructure/docker.md"],
    "kubernetes": ["docs/guidelines/infrastructure/docker.md"],
    "aws": ["docs/guidelines/cloud/aws.md"],
    "gcp": ["docs/guidelines/cloud/aws.md"],
    "azure": ["docs/guidelines/cloud/aws.md"],
    "python": ["docs/guidelines/coding/python/style-guide.md"],
    "typescript": ["docs/guidelines/coding/typescript/style-guide.md"],
    "javascript": ["docs/guidelines/coding/typescript/style-guide.md"],
    "go": ["docs/guidelines/coding/go/style-guide.md"],
    "java": ["docs/guidelines/coding/python/style-guide.md"],  # Similar patterns
    "csharp": ["docs/guidelines/coding/python/style-guide.md"],
    "flutter-dart": ["docs/guidelines/coding/python/style-guide.md"],
}

# Agent type to skills mapping
AGENT_SKILLS = {
    "ideation": ["market-research", "user-research", "competitive-analysis", "product-strategy"],
    "design": ["ui-design", "ux-research", "wireframing", "prototyping", "design-system"],
    "architect": ["system-design", "architecture-patterns", "database-design", "api-design"],
    "implement": ["coding", "testing", "debugging", "optimization"],
    "code-review": ["code-review", "security-review", "performance-review"],
    "validate": ["testing", "qa", "performance-testing", "security-testing"],
    "security": ["security-audit", "penetration-testing", "compliance-check"],
    "document": ["documentation", "api-docs", "user-guides"],
}


class BusinessSkillsSelector:
    """Select skills and guidelines based on business model and context."""
    
    def __init__(self, products_dir: str = "products"):
        self.products_dir = Path(products_dir)
    
    def select_for_project(
        self,
        project: str,
        business_model_id: Optional[str] = None,
        domain: Optional[str] = None,
        techstack: Optional[List[str]] = None,
    ) -> SelectionResult:
        """Select skills and guidelines for a project."""
        # Load project config if available
        project_config = self._load_project_config(project)
        
        # Get business model
        business_model = None
        if business_model_id:
            business_model = BUSINESS_MODELS.get(business_model_id)
        elif project_config:
            model_id = project_config.get("business_model")
            if model_id:
                business_model = BUSINESS_MODELS.get(model_id)
        
        # Get domain
        if not domain and project_config:
            domain = project_config.get("product_domain", "")
        if not domain and business_model:
            domain = business_model.domain
        
        # Get techstack
        if not techstack and project_config:
            techstack = project_config.get("tech_stack_hints", [])
        
        # Collect recommended skills
        recommended_skills = []
        recommended_guidelines = []
        architecture_patterns = []
        
        if business_model:
            # Add business model skills
            for skill in business_model.recommended_skills:
                recommended_skills.append(SkillRecommendation(
                    skill_id=skill,
                    name=skill.replace("-", " ").title(),
                    reason=f"Recommended for {business_model.name}",
                    relevance_score=0.9,
                    source="business_model",
                ))
            
            # Add business model guidelines
            recommended_guidelines.extend(business_model.recommended_guidelines)
            
            # Add architecture patterns
            architecture_patterns.extend(business_model.architecture_patterns)
        
        # Add domain guidelines
        if domain and domain in DOMAIN_GUIDELINES:
            recommended_guidelines.extend(DOMAIN_GUIDELINES[domain])
        
        # Add techstack guidelines
        if techstack:
            for tech in techstack:
                tech_lower = tech.lower()
                if tech_lower in TECHSTACK_GUIDELINES:
                    recommended_guidelines.extend(TECHSTACK_GUIDELINES[tech_lower])
        
        # Remove duplicates
        recommended_guidelines = list(set(recommended_guidelines))
        
        # Build agent-specific skills
        agent_skills = {}
        for agent_id, base_skills in AGENT_SKILLS.items():
            agent_skills[agent_id] = []
            for skill in base_skills:
                agent_skills[agent_id].append(SkillRecommendation(
                    skill_id=skill,
                    name=skill.replace("-", " ").title(),
                    reason=f"Standard skill for {agent_id} agent",
                    relevance_score=0.7,
                    source="agent_type",
                ))
        
        return SelectionResult(
            project=project,
            business_model=business_model,
            domain=domain or "",
            techstack=techstack or [],
            recommended_skills=recommended_skills,
            recommended_guidelines=recommended_guidelines,
            architecture_patterns=architecture_patterns,
            agent_skills=agent_skills,
        )
    
    def _load_project_config(self, project: str) -> Optional[Dict]:
        """Load project configuration."""
        config_file = self.products_dir / project / "project.json"
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        
        # Also try project-config.json
        config_file = self.products_dir / project / "project-config.json"
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        
        return None
    
    def get_business_model(self, model_id: str) -> Optional[BusinessModel]:
        """Get business model by ID."""
        return BUSINESS_MODELS.get(model_id)
    
    def list_business_models(self) -> List[BusinessModel]:
        """List all available business models."""
        return list(BUSINESS_MODELS.values())
    
    def detect_business_model_from_idea(self, idea: str) -> Optional[BusinessModel]:
        """Try to detect business model from product idea."""
        idea_lower = idea.lower()
        
        # Simple keyword matching
        if any(word in idea_lower for word in ["saas", "subscription", "monthly", "plan"]):
            return BUSINESS_MODELS.get("saas")
        elif any(word in idea_lower for word in ["marketplace", "connect buyers sellers", "platform"]):
            return BUSINESS_MODELS.get("marketplace")
        elif any(word in idea_lower for word in ["shop", "store", "buy", "sell", "product"]):
            return BUSINESS_MODELS.get("ecommerce")
        elif any(word in idea_lower for word in ["payment", "finance", "banking", "wallet"]):
            return BUSINESS_MODELS.get("fintech")
        elif any(word in idea_lower for word in ["health", "medical", "patient", "doctor"]):
            return BUSINESS_MODELS.get("healthtech")
        elif any(word in idea_lower for word in ["learn", "course", "education", "student"]):
            return BUSINESS_MODELS.get("edtech")
        elif any(word in idea_lower for word in ["internal", "admin", "dashboard", "tool"]):
            return BUSINESS_MODELS.get("internal-tool")
        elif any(word in idea_lower for word in ["api", "developer", "sdk", "rest"]):
            return BUSINESS_MODELS.get("api-product")
        
        return None
