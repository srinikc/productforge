"""
Product Forge - Workflow Documentation Generator
Generates HTML, Draw.io diagrams, and PDF documentation for the pipeline and agents
"""
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
import json


@dataclass
class WorkflowStep:
    """A single step in a workflow"""
    id: str
    name: str
    description: str
    agent: str
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    duration_estimate: str = ""
    dependencies: List[str] = field(default_factory=list)
    parallel: bool = False


@dataclass
class AgentWorkflow:
    """Complete workflow for an agent"""
    agent_name: str
    agent_role: str
    purpose: str
    steps: List[WorkflowStep]
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    model_recommendation: str = ""


class WorkflowDocumentationGenerator:
    """Generates workflow documentation for Product Forge pipeline and agents"""

    PRODUCT_NAME = "Product Forge"
    PRODUCT_TAGLINE = "Multi-Agent Multi-Project System"

    def __init__(self, products_dir: str = "products"):
        self.products_dir = Path(products_dir)
        self.docs_dir = Path("dashboard/docs")
        self.docs_dir.mkdir(parents=True, exist_ok=True)

    def get_pipeline_workflow(self) -> Dict[str, Any]:
        """Get the complete pipeline workflow"""
        return {
            "name": f"{self.PRODUCT_NAME} Pipeline",
            "tagline": self.PRODUCT_TAGLINE,
            "description": "End-to-end product development pipeline with 17+ agents",
            "phases": [
                {
                    "id": "phase-0",
                    "name": "Ideation",
                    "color": "#58a6ff",
                    "steps": [
                        {"id": "0", "name": "Capture Idea", "agent": "ideation", "duration": "5-15 min"},
                        {"id": "1", "name": "Classify Product Type", "agent": "ideation", "duration": "2-5 min"},
                        {"id": "2", "name": "360° Brainstorming", "agent": "ideation", "duration": "15-30 min"},
                        {"id": "3", "name": "Domain Research", "agent": "domain-research", "duration": "10-20 min"}
                    ]
                },
                {
                    "id": "phase-1",
                    "name": "Design",
                    "color": "#a371f7",
                    "steps": [
                        {"id": "4", "name": "Requirements", "agent": "design", "duration": "30-60 min"},
                        {"id": "5", "name": "User Flows", "agent": "design", "duration": "30-60 min"},
                        {"id": "6", "name": "Wireframes", "agent": "design", "duration": "1-2 hours"},
                        {"id": "7", "name": "Component Design", "agent": "design", "duration": "1-2 hours"},
                        {"id": "8", "name": "Threat Modeling (1-S)", "agent": "security", "duration": "30-60 min", "parallel": True}
                    ]
                },
                {
                    "id": "phase-2",
                    "name": "Architecture",
                    "color": "#3fb950",
                    "steps": [
                        {"id": "9", "name": "Tech Stack Selection", "agent": "architect", "duration": "1-2 hours"},
                        {"id": "10", "name": "System Design", "agent": "architect", "duration": "2-4 hours"},
                        {"id": "11", "name": "ADRs", "agent": "architect", "duration": "1-2 hours"},
                        {"id": "12", "name": "Security Architecture (2-S)", "agent": "security", "duration": "1-2 hours", "parallel": True}
                    ]
                },
                {
                    "id": "phase-3",
                    "name": "Review",
                    "color": "#d29922",
                    "steps": [
                        {"id": "13", "name": "Design Review", "agent": "review", "duration": "1-2 hours"},
                        {"id": "14", "name": "Architecture Review", "agent": "review", "duration": "1-2 hours"},
                        {"id": "15", "name": "Cross-Agent Review", "agent": "cross-review", "duration": "1-2 hours"}
                    ]
                },
                {
                    "id": "phase-4",
                    "name": "Implementation",
                    "color": "#f85149",
                    "steps": [
                        {"id": "16", "name": "Code Generation", "agent": "implement", "duration": "4-40 hours"},
                        {"id": "17", "name": "Unit Tests", "agent": "implement", "duration": "2-8 hours"},
                        {"id": "18", "name": "SAST Scan (4-S)", "agent": "security", "duration": "30-60 min", "parallel": True},
                        {"id": "19", "name": "Dependency Audit (4-S)", "agent": "security", "duration": "15-30 min", "parallel": True}
                    ]
                },
                {
                    "id": "phase-5",
                    "name": "Quality Assurance",
                    "color": "#58a6ff",
                    "steps": [
                        {"id": "20", "name": "Code Review", "agent": "code-review", "duration": "1-2 hours"},
                        {"id": "21", "name": "Integration Tests", "agent": "validate", "duration": "1-2 hours"},
                        {"id": "22", "name": "E2E Tests", "agent": "validate", "duration": "1-2 hours"},
                        {"id": "23", "name": "DAST Scan (6-S)", "agent": "security", "duration": "1-2 hours", "parallel": True}
                    ]
                },
                {
                    "id": "phase-6",
                    "name": "Fix Loop",
                    "color": "#d29922",
                    "steps": [
                        {"id": "24", "name": "Issue Triage", "agent": "fix", "duration": "15-30 min"},
                        {"id": "25", "name": "Fix Issues", "agent": "fix", "duration": "1-4 hours"},
                        {"id": "26", "name": "Re-validate", "agent": "validate", "duration": "1-2 hours"}
                    ]
                },
                {
                    "id": "phase-7",
                    "name": "Documentation & Onboarding",
                    "color": "#a371f7",
                    "steps": [
                        {"id": "27", "name": "Generate Docs", "agent": "document", "duration": "1-2 hours"},
                        {"id": "28", "name": "User Manual", "agent": "document", "duration": "1-2 hours"},
                        {"id": "29", "name": "Customer Onboarding", "agent": "customer-onboarding", "duration": "1-2 hours", "parallel": True}
                    ]
                },
                {
                    "id": "phase-8",
                    "name": "Package",
                    "color": "#3fb950",
                    "steps": [
                        {"id": "30", "name": "Version Bump", "agent": "package", "duration": "5 min"},
                        {"id": "31", "name": "Build Artifacts", "agent": "package", "duration": "15-30 min"},
                        {"id": "32", "name": "Generate Checksums", "agent": "package", "duration": "1 min"}
                    ]
                },
                {
                    "id": "phase-9",
                    "name": "DevOps",
                    "color": "#58a6ff",
                    "steps": [
                        {"id": "33", "name": "CI/CD Setup", "agent": "devops", "duration": "1-2 hours"},
                        {"id": "34", "name": "Deploy to Staging", "agent": "devops", "duration": "15-30 min"},
                        {"id": "35", "name": "Deploy to Production", "agent": "devops", "duration": "15-30 min"}
                    ]
                },
                {
                    "id": "phase-10",
                    "name": "Marketing",
                    "color": "#f85149",
                    "steps": [
                        {"id": "36", "name": "GTM Strategy", "agent": "marketing", "duration": "1-2 hours"},
                        {"id": "37", "name": "Generate Presentation", "agent": "presentation", "duration": "1-2 hours"},
                        {"id": "38", "name": "Generate Demo Video", "agent": "presentation", "duration": "1-2 hours"},
                        {"id": "39", "name": "Marketing Materials", "agent": "marketing", "duration": "1-2 hours"}
                    ]
                },
                {
                    "id": "phase-11",
                    "name": "Operations",
                    "color": "#3fb950",
                    "steps": [
                        {"id": "40", "name": "Maintenance Setup", "agent": "maintenance", "duration": "30-60 min", "parallel": True},
                        {"id": "41", "name": "FinOps Tracking", "agent": "finops", "duration": "30-60 min", "parallel": True}
                    ]
                }
            ]
        }

    def get_agent_workflows(self) -> List[AgentWorkflow]:
        """Get workflows for all 17 agents"""
        workflows = []

        # Ideation Agent
        workflows.append(AgentWorkflow(
            agent_name="ideation",
            agent_role="Pipeline Orchestrator",
            purpose="Capture and refine product ideas, classify product type, and perform 360-degree brainstorming",
            steps=[
                WorkflowStep("ide-1", "Capture Initial Idea", "Receive and acknowledge the product idea", "ideation",
                            inputs=["User's product idea"], outputs=["Acknowledged idea"]),
                WorkflowStep("ide-2", "Classify Product Type", "Determine if exploration/learning/fun/prototype/personal/internal/product/business",
                            "ideation", inputs=["Idea description"], outputs=["Product type classification"]),
                WorkflowStep("ide-3", "Domain Identification", "Identify the product domain (finance/healthcare/etc.)",
                            "ideation", inputs=["Product type"], outputs=["Domain classification"]),
                WorkflowStep("ide-4", "Adaptive Questions", "Ask 2-20 questions based on product type",
                            "ideation", inputs=["Product type"], outputs=["Requirements clarification"]),
                WorkflowStep("ide-5", "360° Brainstorming", "Multi-perspective analysis (engineering, product, marketing, customer, financial, competitive)",
                            "ideation", inputs=["All gathered info"], outputs=["Comprehensive analysis report"]),
                WorkflowStep("ide-6", "Model Recommendation", "Suggest optimal AI models for the project",
                            "ideation", inputs=["Task requirements"], outputs=["Model recommendations"])
            ],
            inputs=["Initial product idea"],
            outputs=["Product plan", "360° analysis", "Model recommendations"],
            model_recommendation="mimo-v2.5-free"
        ))

        # Design Agent
        workflows.append(AgentWorkflow(
            agent_name="design",
            agent_role="Product Designer",
            purpose="Create requirements, user flows, wireframes, and component designs",
            steps=[
                WorkflowStep("des-1", "Requirements Gathering", "Create formal requirements document",
                            "design", inputs=["Product plan"], outputs=["requirements.md"]),
                WorkflowStep("des-2", "User Flow Design", "Map out user journeys and flows",
                            "design", inputs=["Requirements"], outputs=["User flow diagrams"]),
                WorkflowStep("des-3", "Wireframe Creation", "Create low-fidelity wireframes",
                            "design", inputs=["User flows"], outputs=["Wireframes"]),
                WorkflowStep("des-4", "Component Design", "Design reusable UI components",
                            "design", inputs=["Wireframes"], outputs=["Component library"]),
                WorkflowStep("des-5", "Design Review", "Self-review and quality check",
                            "design", inputs=["All design artifacts"], outputs=["Reviewed design"])
            ],
            inputs=["Product plan from ideation"],
            outputs=["requirements.md", "design.md", "wireframes/"],
            model_recommendation="mimo-v2.5-free"
        ))

        # Architect Agent
        workflows.append(AgentWorkflow(
            agent_name="architect",
            agent_role="System Architect",
            purpose="Design system architecture, select tech stack, and create ADRs",
            steps=[
                WorkflowStep("arc-1", "Tech Stack Selection", "Choose appropriate technologies",
                            "architect", inputs=["Requirements"], outputs=["Tech stack list"]),
                WorkflowStep("arc-2", "System Design", "Design overall system architecture",
                            "architect", inputs=["Requirements", "Tech stack"], outputs=["architecture.md"]),
                WorkflowStep("arc-3", "ADR Creation", "Document Architecture Decision Records",
                            "architect", inputs=["Key decisions"], outputs=["ADR documents"]),
                WorkflowStep("arc-4", "Diagram Generation", "Create architecture diagrams",
                            "architect", inputs=["Architecture"], outputs=["Diagrams"])
            ],
            inputs=["Design documents"],
            outputs=["architecture.md", "ADRs/", "diagrams/"],
            model_recommendation="hy3-free"
        ))

        # Security Agent
        workflows.append(AgentWorkflow(
            agent_name="security",
            agent_role="Security Analyst",
            purpose="Perform security analysis at 4 phases: Design, Architecture, Implementation, Validation",
            steps=[
                WorkflowStep("sec-1", "Threat Modeling (1-S)", "Identify threats during design phase",
                            "security", inputs=["Design docs"], outputs=["Threat model"], parallel=True),
                WorkflowStep("sec-2", "Security Architecture (2-S)", "Review security architecture",
                            "security", inputs=["Architecture"], outputs=["Security review"], parallel=True),
                WorkflowStep("sec-3", "SAST Scan (4-S)", "Static Application Security Testing",
                            "security", inputs=["Source code"], outputs=["SAST report"]),
                WorkflowStep("sec-4", "Dependency Audit (4-S)", "Check for vulnerable dependencies",
                            "security", inputs=["Dependencies"], outputs=["Dependency report"]),
                WorkflowStep("sec-5", "Secret Detection (4-S)", "Scan for hardcoded secrets",
                            "security", inputs=["Source code"], outputs=["Secret scan report"]),
                WorkflowStep("sec-6", "DAST Scan (6-S)", "Dynamic Application Security Testing",
                            "security", inputs=["Running app"], outputs=["DAST report"])
            ],
            inputs=["Design/Architecture/Code/Deployed app"],
            outputs=["Security reports", "Threat models", "Vulnerability lists"],
            model_recommendation="nemotron-3-ultra-free"
        ))

        # Implement Agent
        workflows.append(AgentWorkflow(
            agent_name="implement",
            agent_role="Software Engineer",
            purpose="Build the product using TDD approach",
            steps=[
                WorkflowStep("imp-1", "Test-First Development", "Write tests before implementation",
                            "implement", inputs=["Requirements", "Design"], outputs=["Test files"]),
                WorkflowStep("imp-2", "Code Generation", "Implement features to pass tests",
                            "implement", inputs=["Tests", "Architecture"], outputs=["Source code"]),
                WorkflowStep("imp-3", "Refactoring", "Improve code quality",
                            "implement", inputs=["Working code"], outputs=["Refactored code"]),
                WorkflowStep("imp-4", "Integration", "Integrate components",
                            "implement", inputs=["Components"], outputs=["Integrated system"])
            ],
            inputs=["Architecture, Design, Requirements"],
            outputs=["src/", "tests/"],
            model_recommendation="mimo-v2.5-free"
        ))

        # Code Review Agent
        workflows.append(AgentWorkflow(
            agent_name="code-review",
            agent_role="Code Reviewer",
            purpose="Review code quality, identify issues, and suggest improvements",
            steps=[
                WorkflowStep("cr-1", "Style Review", "Check coding style and conventions",
                            "code-review", inputs=["Source code"], outputs=["Style report"]),
                WorkflowStep("cr-2", "Logic Review", "Review business logic correctness",
                            "code-review", inputs=["Source code"], outputs=["Logic report"]),
                WorkflowStep("cr-3", "Performance Review", "Identify performance issues",
                            "code-review", inputs=["Source code"], outputs=["Performance report"]),
                WorkflowStep("cr-4", "Security Review", "Quick security check",
                            "code-review", inputs=["Source code"], outputs=["Security findings"])
            ],
            inputs=["Source code", "Requirements"],
            outputs=["code-review.md"],
            model_recommendation="big-pickle"
        ))

        # Validate Agent
        workflows.append(AgentWorkflow(
            agent_name="validate",
            agent_role="QA Engineer",
            purpose="Run tests, validate functionality, and check quality",
            steps=[
                WorkflowStep("val-1", "Unit Test Execution", "Run all unit tests",
                            "validate", inputs=["Test files", "Code"], outputs=["Unit test results"]),
                WorkflowStep("val-2", "Integration Testing", "Test component integration",
                            "validate", inputs=["Integrated system"], outputs=["Integration results"]),
                WorkflowStep("val-3", "E2E Testing", "Test complete user flows",
                            "validate", inputs=["Running app"], outputs=["E2E results"]),
                WorkflowStep("val-4", "Coverage Analysis", "Measure test coverage",
                            "validate", inputs=["Test results"], outputs=["Coverage report"]),
                WorkflowStep("val-5", "Issue Reporting", "Generate issues.md with all findings",
                            "validate", inputs=["All test results"], outputs=["issues.md"])
            ],
            inputs=["Source code", "Tests", "Requirements"],
            outputs=["issues.md", "coverage/", "test-results/"],
            model_recommendation="nemotron-3.5-lightning-free"
        ))

        # Document Agent
        workflows.append(AgentWorkflow(
            agent_name="document",
            agent_role="Technical Writer",
            purpose="Generate comprehensive documentation for the product",
            steps=[
                WorkflowStep("doc-1", "README Generation", "Create project README",
                            "document", inputs=["Product plan"], outputs=["README.md"]),
                WorkflowStep("doc-2", "API Documentation", "Generate API reference",
                            "document", inputs=["Source code"], outputs=["api-docs.md"]),
                WorkflowStep("doc-3", "User Guide", "Create user manual",
                            "document", inputs=["Features"], outputs=["user-guide.md"]),
                WorkflowStep("doc-4", "Architecture Docs", "Document architecture",
                            "document", inputs=["Architecture"], outputs=["architecture-docs.md"])
            ],
            inputs=["Product plan", "Source code", "Architecture"],
            outputs=["README.md", "docs/"],
            model_recommendation="mimo-v2.5-free"
        ))

        # Package Agent
        workflows.append(AgentWorkflow(
            agent_name="package",
            agent_role="Release Manager",
            purpose="Version, package, and prepare for distribution",
            steps=[
                WorkflowStep("pkg-1", "Version Bump", "Update version using SemVer",
                            "package", inputs=["Changes since last release"], outputs=["version.json"]),
                WorkflowStep("pkg-2", "Changelog Update", "Generate changelog entry",
                            "package", inputs=["Changes"], outputs=["CHANGELOG.md"]),
                WorkflowStep("pkg-3", "Build Artifacts", "Create distributable packages",
                            "package", inputs=["Source code"], outputs=["Artifacts"]),
                WorkflowStep("pkg-4", "Generate Checksums", "Create SHA256 checksums",
                            "package", inputs=["Artifacts"], outputs=["checksums.txt"]),
                WorkflowStep("pkg-5", "Sign Artifacts", "Digital signature for verification",
                            "package", inputs=["Artifacts"], outputs=["Signed artifacts"])
            ],
            inputs=["Source code", "Version info"],
            outputs=["Artifacts", "CHANGELOG.md", "version.json"],
            model_recommendation="mimo-v2.5-free"
        ))

        # DevOps Agent
        workflows.append(AgentWorkflow(
            agent_name="devops",
            agent_role="DevOps Engineer",
            purpose="Set up CI/CD, deploy, and monitor the product",
            steps=[
                WorkflowStep("dev-1", "CI/CD Setup", "Configure GitHub Actions/GitLab CI/Jenkins",
                            "devops", inputs=["Project type"], outputs=[".github/workflows/"]),
                WorkflowStep("dev-2", "Container Build", "Create Docker image",
                            "devops", inputs=["Application"], outputs=["Dockerfile", "Image"]),
                WorkflowStep("dev-3", "Deploy Staging", "Deploy to staging environment",
                            "devops", inputs=["Docker image"], outputs=["Staging deployment"]),
                WorkflowStep("dev-4", "Deploy Production", "Deploy to production with rollback plan",
                            "devops", inputs=["Staging validation"], outputs=["Production deployment"]),
                WorkflowStep("dev-5", "Monitor Setup", "Configure monitoring and alerts",
                            "devops", inputs=["Application"], outputs=["Monitoring config"])
            ],
            inputs=["Artifacts", "Application"],
            outputs=[".github/workflows/", "Dockerfile", "Deployments"],
            model_recommendation="mimo-v2.5-free"
        ))

        # Customer Onboarding Agent
        workflows.append(AgentWorkflow(
            agent_name="customer-onboarding",
            agent_role="Customer Success",
            purpose="Create onboarding materials to help customers get started",
            steps=[
                WorkflowStep("onb-1", "Welcome Email", "Generate personalized welcome email",
                            "customer-onboarding", inputs=["Product info"], outputs=["welcome-email.md"]),
                WorkflowStep("onb-2", "Setup Checklist", "Create account setup guide",
                            "customer-onboarding", inputs=["Product features"], outputs=["setup-checklist.md"]),
                WorkflowStep("onb-3", "Installation Guide", "Detailed installation instructions",
                            "customer-onboarding", inputs=["Tech stack"], outputs=["installation-guide.md"]),
                WorkflowStep("onb-4", "First-Run Wizard", "Interactive tutorial content",
                            "customer-onboarding", inputs=["Product features"], outputs=["first-run-wizard.md"]),
                WorkflowStep("onb-5", "Communication Plan", "Day 1, 3, 7, 14, 30, 60, 90 emails",
                            "customer-onboarding", inputs=["Product type"], outputs=["communication-plan.md"])
            ],
            inputs=["Product info", "Features"],
            outputs=["onboarding/ folder with 11 files"],
            model_recommendation="mimo-v2.5-free"
        ))

        # Marketing Agent
        workflows.append(AgentWorkflow(
            agent_name="marketing",
            agent_role="Marketing Manager",
            purpose="Create go-to-market strategy and marketing materials",
            steps=[
                WorkflowStep("mkt-1", "GTM Strategy", "Define target market, positioning, pricing",
                            "marketing", inputs=["Product info"], outputs=["gtm-strategy.md"]),
                WorkflowStep("mkt-2", "Content Calendar", "Create editorial calendar",
                            "marketing", inputs=["GTM strategy"], outputs=["content-calendar.md"]),
                WorkflowStep("mkt-3", "Campaign Plan", "Define marketing campaigns",
                            "marketing", inputs=["Budget", "Goals"], outputs=["campaign-plan.md"]),
                WorkflowStep("mkt-4", "Social Media Strategy", "Platform-specific tactics",
                            "marketing", inputs=["Target audience"], outputs=["social-media.md"]),
                WorkflowStep("mkt-5", "Email Templates", "Launch, feature, testimonial emails",
                            "marketing", inputs=["Product info"], outputs=["email-templates.md"])
            ],
            inputs=["Product info", "Target market"],
            outputs=["marketing/ folder with 8 files"],
            model_recommendation="hy3-free"
        ))

        # Presentation Agent
        workflows.append(AgentWorkflow(
            agent_name="presentation",
            agent_role="Presentation Designer",
            purpose="Generate presentations, demo videos, and marketing materials",
            steps=[
                WorkflowStep("pres-1", "PPTX Generation", "Create PowerPoint presentation",
                            "presentation", inputs=["Product info"], outputs=["presentation.pptx"]),
                WorkflowStep("pres-2", "PDF Generation", "Create PDF version",
                            "presentation", inputs=["Slides"], outputs=["presentation.pdf"]),
                WorkflowStep("pres-3", "HTML Presentation", "Web-viewable presentation",
                            "presentation", inputs=["Slides"], outputs=["presentation.html"]),
                WorkflowStep("pres-4", "Video Script", "Generate narration script",
                            "presentation", inputs=["Features"], outputs=["demo-script.md"]),
                WorkflowStep("pres-5", "ffmpeg Commands", "Generate video creation commands",
                            "presentation", inputs=["Script"], outputs=["video-commands.sh"]),
                WorkflowStep("pres-6", "Social Media Content", "Twitter, LinkedIn, Reddit posts",
                            "presentation", inputs=["Product info"], outputs=["social-media.md"]),
                WorkflowStep("pres-7", "Landing Page", "Hero, features, pricing, FAQ",
                            "presentation", inputs=["Product info"], outputs=["landing-page.md"]),
                WorkflowStep("pres-8", "Blog Post", "Introduction and deep dive",
                            "presentation", inputs=["Product info"], outputs=["blog-post.md"])
            ],
            inputs=["Product info", "Features"],
            outputs=["PPTX, PDF, HTML, Video scripts, Marketing content"],
            model_recommendation="mimo-v2.5-free"
        ))

        # Maintenance Agent
        workflows.append(AgentWorkflow(
            agent_name="maintenance",
            agent_role="Site Reliability Engineer",
            purpose="Handle post-deployment maintenance, monitoring, and health checks",
            steps=[
                WorkflowStep("mnt-1", "Health Check", "Run multi-component health checks",
                            "maintenance", inputs=["Running system"], outputs=["Health status"]),
                WorkflowStep("mnt-2", "Issue Tracking", "Track and manage issues",
                            "maintenance", inputs=["Issue reports"], outputs=["Issue database"]),
                WorkflowStep("mnt-3", "Patch Management", "Apply security and bug fix patches",
                            "maintenance", inputs=["Patch list"], outputs=["Applied patches"]),
                WorkflowStep("mnt-4", "Performance Monitoring", "Track metrics and alerts",
                            "maintenance", inputs=["Metrics"], outputs=["Performance reports"])
            ],
            inputs=["Running system", "Issue reports"],
            outputs=["Health reports", "Patch logs", "Issue tracking"],
            model_recommendation="nemotron-3-ultra-free"
        ))

        # FinOps Agent
        workflows.append(AgentWorkflow(
            agent_name="finops",
            agent_role="FinOps Engineer",
            purpose="Optimize cloud costs, track budgets, and provide financial insights",
            steps=[
                WorkflowStep("fin-1", "Cost Tracking", "Track costs by service and tag",
                            "finops", inputs=["Cloud billing data"], outputs=["Cost reports"]),
                WorkflowStep("fin-2", "Budget Management", "Set and monitor budgets",
                            "finops", inputs=["Budget limits"], outputs=["Budget status"]),
                WorkflowStep("fin-3", "Optimization", "Identify cost savings opportunities",
                            "finops", inputs=["Usage data"], outputs=["Optimization recommendations"]),
                WorkflowStep("fin-4", "Forecasting", "Predict future spending",
                            "finops", inputs=["Historical data"], outputs=["Cost forecasts"])
            ],
            inputs=["Cloud costs", "Usage data"],
            outputs=["Cost reports", "Budget status", "Optimization recommendations"],
            model_recommendation="nemotron-3-ultra-free"
        ))

        # Domain Research Agent
        workflows.append(AgentWorkflow(
            agent_name="domain-research",
            agent_role="Domain Researcher",
            purpose="Research domain trends, best practices, and industry insights",
            steps=[
                WorkflowStep("dom-1", "Trend Analysis", "Identify current and emerging trends",
                            "domain-research", inputs=["Domain"], outputs=["Trend report"]),
                WorkflowStep("dom-2", "Best Practices", "Compile industry best practices",
                            "domain-research", inputs=["Domain"], outputs=["Best practices guide"]),
                WorkflowStep("dom-3", "Research Synthesis", "Synthesize findings into recommendations",
                            "domain-research", inputs=["Research data"], outputs=["Research report"])
            ],
            inputs=["Domain specification"],
            outputs=["Trend reports", "Best practices", "Research synthesis"],
            model_recommendation="hy3-free"
        ))

        # Product Analyzer Agent
        workflows.append(AgentWorkflow(
            agent_name="product-analyzer",
            agent_role="Product Analyzer",
            purpose="Comprehensively analyze existing products for pipeline integration",
            steps=[
                WorkflowStep("ana-1", "Structure Analysis", "Analyze project structure and organization",
                            "product-analyzer", inputs=["Source path"], outputs=["Structure report"]),
                WorkflowStep("ana-2", "Code Quality Analysis", "Measure code quality metrics",
                            "product-analyzer", inputs=["Source code"], outputs=["Quality report"]),
                WorkflowStep("ana-3", "Test Coverage Analysis", "Assess testing completeness",
                            "product-analyzer", inputs=["Test files"], outputs=["Coverage report"]),
                WorkflowStep("ana-4", "Security Scanning", "Scan for security issues",
                            "product-analyzer", inputs=["Source code"], outputs=["Security findings"]),
                WorkflowStep("ana-5", "Gap Analysis", "Compare against pipeline standards",
                            "product-analyzer", inputs=["All analyses"], outputs=["Gap report"]),
                WorkflowStep("ana-6", "Agent Work Planning", "Plan which agents need to run",
                            "product-analyzer", inputs=["Gap analysis"], outputs=["Work plan"]),
                WorkflowStep("ana-7", "Recommendations", "Generate prioritized recommendations",
                            "product-analyzer", inputs=["All analyses"], outputs=["Recommendations"]),
                WorkflowStep("ana-8", "User Questions", "Create questions for user clarification",
                            "product-analyzer", inputs=["Analyses"], outputs=["User questions"])
            ],
            inputs=["Existing product path"],
            outputs=["Comprehensive analysis report", "Agent work plan", "User questions"],
            model_recommendation="mimo-v2.5-free"
        ))

        return workflows

    def generate_pipeline_html(self) -> str:
        """Generate HTML documentation for the entire pipeline"""
        workflow = self.get_pipeline_workflow()

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{self.PRODUCT_NAME} - Pipeline Workflow</title>
<style>
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #0d1117;
    color: #e6edf3;
    margin: 0;
    padding: 20px;
    line-height: 1.6;
}}
.container {{
    max-width: 1200px;
    margin: 0 auto;
}}
h1 {{
    color: #58a6ff;
    border-bottom: 2px solid #30363d;
    padding-bottom: 10px;
    font-size: 2.5rem;
}}
h2 {{
    color: #58a6ff;
    margin-top: 40px;
    border-left: 4px solid #58a6ff;
    padding-left: 12px;
}}
.subtitle {{
    color: #8b949e;
    font-size: 1.1rem;
    margin-bottom: 30px;
}}
.brand {{
    background: linear-gradient(135deg, #58a6ff, #a371f7);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    font-weight: bold;
}}
.phase {{
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 20px;
    margin: 20px 0;
}}
.phase-header {{
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid #30363d;
}}
.phase-color {{
    width: 20px;
    height: 20px;
    border-radius: 4px;
}}
.phase-name {{
    font-size: 1.3rem;
    font-weight: 600;
}}
.phase-badge {{
    background: #30363d;
    color: #8b949e;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.75rem;
    margin-left: auto;
}}
.steps {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 12px;
}}
.step {{
    background: #0d1117;
    border: 1px solid #21262d;
    border-radius: 8px;
    padding: 12px;
    transition: border-color 0.2s;
}}
.step:hover {{
    border-color: #58a6ff;
}}
.step-id {{
    color: #8b949e;
    font-size: 0.7rem;
    font-family: monospace;
}}
.step-name {{
    font-weight: 600;
    margin: 4px 0;
}}
.step-agent {{
    color: #a371f7;
    font-size: 0.8rem;
    font-family: monospace;
}}
.step-duration {{
    color: #8b949e;
    font-size: 0.7rem;
    margin-top: 4px;
}}
.parallel-badge {{
    background: rgba(88, 166, 255, 0.2);
    color: #58a6ff;
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 0.65rem;
    margin-left: 6px;
}}
.summary {{
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 20px;
    margin: 20px 0;
}}
.summary-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 16px;
    margin-top: 12px;
}}
.summary-item {{
    text-align: center;
    padding: 12px;
    background: #0d1117;
    border-radius: 8px;
}}
.summary-value {{
    font-size: 2rem;
    font-weight: 700;
    color: #58a6ff;
}}
.summary-label {{
    color: #8b949e;
    font-size: 0.75rem;
    text-transform: uppercase;
    margin-top: 4px;
}}
.footer {{
    margin-top: 40px;
    padding-top: 20px;
    border-top: 1px solid #30363d;
    color: #8b949e;
    text-align: center;
    font-size: 0.85rem;
}}
</style>
</head>
<body>
<div class="container">

<h1>🚀 <span class="brand">{self.PRODUCT_NAME}</span> Pipeline Workflow</h1>
<p class="subtitle">{self.PRODUCT_TAGLINE} - {workflow['description']}</p>

<div class="summary">
    <h3>📊 Pipeline Overview</h3>
    <div class="summary-grid">
        <div class="summary-item">
            <div class="summary-value">{len(workflow['phases'])}</div>
            <div class="summary-label">Phases</div>
        </div>
        <div class="summary-item">
            <div class="summary-value">{sum(len(p['steps']) for p in workflow['phases'])}</div>
            <div class="summary-label">Total Steps</div>
        </div>
        <div class="summary-item">
            <div class="summary-value">17+</div>
            <div class="summary-label">Agents</div>
        </div>
        <div class="summary-item">
            <div class="summary-value">4</div>
            <div class="summary-label">Security Phases</div>
        </div>
    </div>
</div>

<h2>🔄 Workflow Phases</h2>
"""

        for phase in workflow['phases']:
            parallel_count = sum(1 for s in phase['steps'] if s.get('parallel'))
            html += f"""
<div class="phase">
    <div class="phase-header">
        <div class="phase-color" style="background: {phase['color']}"></div>
        <div class="phase-name">{phase['name']}</div>
        <div class="phase-badge">{len(phase['steps'])} steps{f' • {parallel_count} parallel' if parallel_count else ''}</div>
    </div>
    <div class="steps">
"""
            for step in phase['steps']:
                parallel_badge = '<span class="parallel-badge">⚡ parallel</span>' if step.get('parallel') else ''
                html += f"""
        <div class="step">
            <div class="step-id">Step {step['id']}{parallel_badge}</div>
            <div class="step-name">{step['name']}</div>
            <div class="step-agent">@ {step['agent']}</div>
            <div class="step-duration">⏱ {step['duration']}</div>
        </div>
"""
            html += """
    </div>
</div>
"""

        html += f"""
<div class="footer">
    <p>🤖 <span class="brand">{self.PRODUCT_NAME}</span> - {self.PRODUCT_TAGLINE}</p>
    <p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    <p>For the Draw.io diagram, see <a href="pipeline-workflow.drawio" style="color: #58a6ff">pipeline-workflow.drawio</a></p>
    <p>For PDF version, see <a href="pipeline-workflow.pdf" style="color: #58a6ff">pipeline-workflow.pdf</a></p>
</div>

</div>
</body>
</html>
"""
        return html

    def generate_pipeline_drawio(self) -> str:
        """Generate Draw.io XML for pipeline workflow diagram"""
        workflow = self.get_pipeline_workflow()

        # Draw.io XML
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="app.diagrams.net" modified="''' + datetime.now().isoformat() + '''" agent="ProductForge" version="1.0" type="device">
  <diagram name="Pipeline Workflow" id="pipeline-workflow">
    <mxGraphModel dx="2000" dy="1200" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="2000" pageHeight="1400" math="0" shadow="0">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />

        <!-- Title -->
        <mxCell id="title" value="Product Forge - Pipeline Workflow" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=24;fontStyle=1;fontColor=#58a6ff" vertex="1" parent="1">
          <mxGeometry x="600" y="20" width="800" height="40" as="geometry" />
        </mxCell>

'''

        # Add phase boxes
        y = 100
        phase_colors = {
            "Ideation": "#58a6ff",
            "Design": "#a371f7",
            "Architecture": "#3fb950",
            "Review": "#d29922",
            "Implementation": "#f85149",
            "Quality Assurance": "#58a6ff",
            "Fix Loop": "#d29922",
            "Documentation &amp; Onboarding": "#a371f7",
            "Package": "#3fb950",
            "DevOps": "#58a6ff",
            "Marketing": "#f85149",
            "Operations": "#3fb950"
        }

        x = 50
        cell_id = 100
        for i, phase in enumerate(workflow['phases']):
            color = phase['color'].replace('#', '')
            steps_text = "\\n".join([f"• {s['name']} ({s['agent']})" for s in phase['steps'][:5]])

            xml += f'''
        <mxCell id="phase-{i}" value="{phase['name']}\\n{steps_text}" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#{color};strokeColor=#30363d;fontColor=#ffffff;fontSize=11;fontStyle=1" vertex="1" parent="1">
          <mxGeometry x="{x}" y="{y}" width="280" height="120" as="geometry" />
        </mxCell>
'''

            # Add arrow to next phase
            if i < len(workflow['phases']) - 1:
                xml += f'''
        <mxCell id="arrow-{i}" style="endArrow=classic;html=1;exitX=1;exitY=0.5;entryX=0;entryY=0.5;strokeColor=#58a6ff;strokeWidth=2" edge="1" parent="1" source="phase-{i}" target="phase-{i+1}">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
'''
            cell_id += 1

        xml += '''
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
'''
        return xml

    def generate_agent_html(self, agent_workflow: AgentWorkflow) -> str:
        """Generate HTML documentation for a specific agent"""
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{self.PRODUCT_NAME} - {agent_workflow.agent_name.upper()} Agent</title>
<style>
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #0d1117;
    color: #e6edf3;
    margin: 0;
    padding: 20px;
    line-height: 1.6;
}}
.container {{
    max-width: 1000px;
    margin: 0 auto;
}}
h1 {{
    color: #58a6ff;
    border-bottom: 2px solid #30363d;
    padding-bottom: 10px;
    font-size: 2.2rem;
}}
h2 {{
    color: #58a6ff;
    margin-top: 30px;
    border-left: 4px solid #58a6ff;
    padding-left: 12px;
}}
.brand {{
    background: linear-gradient(135deg, #58a6ff, #a371f7);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    font-weight: bold;
}}
.agent-header {{
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 20px;
    margin: 20px 0;
}}
.agent-role {{
    color: #a371f7;
    font-size: 1.1rem;
    font-weight: 600;
    margin-bottom: 8px;
}}
.agent-purpose {{
    color: #c9d1d9;
    font-size: 0.95rem;
}}
.steps {{
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 20px;
    margin: 20px 0;
}}
.step {{
    background: #0d1117;
    border: 1px solid #21262d;
    border-left: 4px solid #58a6ff;
    border-radius: 8px;
    padding: 16px;
    margin: 12px 0;
    position: relative;
}}
.step-id {{
    color: #8b949e;
    font-size: 0.7rem;
    font-family: monospace;
    position: absolute;
    top: 8px;
    right: 12px;
}}
.step-name {{
    font-weight: 600;
    font-size: 1.1rem;
    margin-bottom: 8px;
}}
.step-desc {{
    color: #c9d1d9;
    font-size: 0.9rem;
    margin-bottom: 8px;
}}
.step-io {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-top: 8px;
    font-size: 0.8rem;
}}
.io-section {{
    background: #161b22;
    padding: 8px;
    border-radius: 4px;
}}
.io-label {{
    color: #8b949e;
    font-size: 0.7rem;
    text-transform: uppercase;
    margin-bottom: 4px;
}}
.io-item {{
    color: #c9d1d9;
    font-family: monospace;
    font-size: 0.75rem;
    margin: 2px 0;
}}
.io-input {{ color: #58a6ff; }}
.io-output {{ color: #3fb950; }}
.model-info {{
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 16px;
    margin: 20px 0;
    display: flex;
    align-items: center;
    gap: 12px;
}}
.model-label {{
    color: #8b949e;
    font-size: 0.8rem;
}}
.model-value {{
    color: #a371f7;
    font-family: monospace;
    font-weight: 600;
}}
.footer {{
    margin-top: 40px;
    padding-top: 20px;
    border-top: 1px solid #30363d;
    color: #8b949e;
    text-align: center;
    font-size: 0.85rem;
}}
</style>
</head>
<body>
<div class="container">

<h1>🤖 <span class="brand">{self.PRODUCT_NAME}</span> - {agent_workflow.agent_name.upper()}</h1>

<div class="agent-header">
    <div class="agent-role">{agent_workflow.agent_role}</div>
    <div class="agent-purpose">{agent_workflow.purpose}</div>
</div>

<div class="model-info">
    <span class="model-label">Recommended Model:</span>
    <span class="model-value">{agent_workflow.model_recommendation}</span>
</div>

<h2>📥 Inputs</h2>
<div class="steps">
"""
        for inp in agent_workflow.inputs:
            html += f'<div class="io-item io-input">→ {inp}</div>\n'

        html += """
</div>

<h2>📤 Outputs</h2>
<div class="steps">
"""
        for out in agent_workflow.outputs:
            html += f'<div class="io-item io-output">← {out}</div>\n'

        html += f"""
</div>

<h2>🔄 Workflow Steps</h2>
<div class="steps">
"""
        for step in agent_workflow.steps:
            html += f"""
<div class="step">
    <div class="step-id">{step.id}</div>
    <div class="step-name">{step.name}</div>
    <div class="step-desc">{step.description}</div>
    <div class="step-io">
        <div class="io-section">
            <div class="io-label">Inputs</div>
"""
            for inp in step.inputs:
                html += f'<div class="io-item io-input">→ {inp}</div>\n'
            html += """
        </div>
        <div class="io-section">
            <div class="io-label">Outputs</div>
"""
            for out in step.outputs:
                html += f'<div class="io-item io-output">← {out}</div>\n'
            html += """
        </div>
    </div>
</div>
"""

        html += f"""
</div>

<div class="footer">
    <p>🤖 <span class="brand">{self.PRODUCT_NAME}</span> - {self.PRODUCT_TAGLINE}</p>
    <p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
</div>

</div>
</body>
</html>
"""
        return html

    def generate_agent_drawio(self, agent_workflow: AgentWorkflow) -> str:
        """Generate Draw.io XML for agent workflow"""
        xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="app.diagrams.net" modified="{datetime.now().isoformat()}" agent="ProductForge" version="1.0" type="device">
  <diagram name="{agent_workflow.agent_name}" id="agent-{agent_workflow.agent_name}">
    <mxGraphModel dx="1500" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1500" pageHeight="900" math="0" shadow="0">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />

        <!-- Title -->
        <mxCell id="title" value="{agent_workflow.agent_name.upper()} Agent Workflow" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=20;fontStyle=1;fontColor=#58a6ff" vertex="1" parent="1">
          <mxGeometry x="500" y="20" width="500" height="30" as="geometry" />
        </mxCell>

        <!-- Input Box -->
        <mxCell id="input" value="Inputs:&#10;{chr(10).join(agent_workflow.inputs)}" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#0d419d;strokeColor=#58a6ff;fontColor=#ffffff;fontSize=11" vertex="1" parent="1">
          <mxGeometry x="50" y="100" width="250" height="120" as="geometry" />
        </mxCell>

        <!-- Output Box -->
        <mxCell id="output" value="Outputs:&#10;{chr(10).join(agent_workflow.outputs)}" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#1a4d1a;strokeColor=#3fb950;fontColor=#ffffff;fontSize=11" vertex="1" parent="1">
          <mxGeometry x="1200" y="100" width="250" height="120" as="geometry" />
        </mxCell>
'''

        # Add step boxes
        y = 100
        x = 350
        for i, step in enumerate(agent_workflow.steps):
            xml += f'''
        <mxCell id="step-{i}" value="{step.id}: {step.name}&#10;{step.description[:50]}..." style="rounded=1;whiteSpace=wrap;html=1;fillColor=#161b22;strokeColor=#58a6ff;fontColor=#e6edf3;fontSize=10" vertex="1" parent="1">
          <mxGeometry x="{x + i * 180}" y="{y}" width="160" height="80" as="geometry" />
        </mxCell>
'''
            # Add arrow between steps
            if i > 0:
                xml += f'''
        <mxCell id="arrow-{i-1}" style="endArrow=classic;html=1;exitX=1;exitY=0.5;entryX=0;entryY=0.5;strokeColor=#58a6ff;strokeWidth=2" edge="1" parent="1" source="step-{i-1}" target="step-{i}">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
'''
            # Add arrow from input to first step
            if i == 0:
                xml += f'''
        <mxCell id="arrow-in" style="endArrow=classic;html=1;exitX=1;exitY=0.5;entryX=0;entryY=0.5;strokeColor=#58a6ff;strokeWidth=2" edge="1" parent="1" source="input" target="step-0">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
'''
            # Add arrow from last step to output
            if i == len(agent_workflow.steps) - 1:
                xml += f'''
        <mxCell id="arrow-out" style="endArrow=classic;html=1;exitX=1;exitY=0.5;entryX=0;entryY=0.5;strokeColor=#3fb950;strokeWidth=2" edge="1" parent="1" source="step-{i}" target="output">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
'''

        xml += '''
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
'''
        return xml

    def save_all_documentation(self):
        """Generate and save all documentation"""
        saved_files = []

        # 1. Pipeline HTML
        pipeline_html = self.generate_pipeline_html()
        pipeline_html_path = self.docs_dir / "pipeline-workflow.html"
        pipeline_html_path.write_text(pipeline_html, encoding="utf-8")
        saved_files.append(str(pipeline_html_path))

        # 2. Pipeline Draw.io
        pipeline_drawio = self.generate_pipeline_drawio()
        pipeline_drawio_path = self.docs_dir / "pipeline-workflow.drawio"
        pipeline_drawio_path.write_text(pipeline_drawio, encoding="utf-8")
        saved_files.append(str(pipeline_drawio_path))

        # 3. Agent documentation
        agent_workflows = self.get_agent_workflows()
        for workflow in agent_workflows:
            # HTML
            agent_html = self.generate_agent_html(workflow)
            agent_html_path = self.docs_dir / f"agent-{workflow.agent_name}.html"
            agent_html_path.write_text(agent_html, encoding="utf-8")
            saved_files.append(str(agent_html_path))

            # Draw.io
            agent_drawio = self.generate_agent_drawio(workflow)
            agent_drawio_path = self.docs_dir / f"agent-{workflow.agent_name}.drawio"
            agent_drawio_path.write_text(agent_drawio, encoding="utf-8")
            saved_files.append(str(agent_drawio_path))

        # 4. Index page
        index_html = self._generate_index_page(agent_workflows)
        index_path = self.docs_dir / "index.html"
        index_path.write_text(index_html, encoding="utf-8")
        saved_files.append(str(index_path))

        return saved_files

    def _generate_index_page(self, agent_workflows: List[AgentWorkflow]) -> str:
        """Generate index page listing all docs"""
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{self.PRODUCT_NAME} - Documentation</title>
<style>
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #0d1117;
    color: #e6edf3;
    margin: 0;
    padding: 20px;
}}
.container {{ max-width: 1200px; margin: 0 auto; }}
h1 {{ color: #58a6ff; border-bottom: 2px solid #30363d; padding-bottom: 10px; }}
h2 {{ color: #58a6ff; margin-top: 30px; border-left: 4px solid #58a6ff; padding-left: 12px; }}
.brand {{
    background: linear-gradient(135deg, #58a6ff, #a371f7);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    font-weight: bold;
}}
.doc-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 16px;
    margin: 20px 0;
}}
.doc-card {{
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 20px;
    transition: border-color 0.2s;
    text-decoration: none;
    color: #e6edf3;
    display: block;
}}
.doc-card:hover {{ border-color: #58a6ff; }}
.doc-title {{
    font-size: 1.1rem;
    font-weight: 600;
    margin-bottom: 8px;
    color: #58a6ff;
}}
.doc-desc {{
    color: #8b949e;
    font-size: 0.85rem;
    margin-bottom: 12px;
}}
.doc-links {{
    display: flex;
    gap: 8px;
}}
.doc-link {{
    background: #21262d;
    color: #58a6ff;
    padding: 4px 10px;
    border-radius: 4px;
    font-size: 0.75rem;
    text-decoration: none;
    border: 1px solid #30363d;
}}
.doc-link:hover {{ background: #30363d; }}
.pipeline-card {{
    background: linear-gradient(135deg, #161b22, #0d1117);
    border: 2px solid #58a6ff;
}}
</style>
</head>
<body>
<div class="container">

<h1>🚀 <span class="brand">{self.PRODUCT_NAME}</span> Documentation</h1>
<p style="color: #8b949e; font-size: 1.1rem;">{self.PRODUCT_TAGLINE}</p>

<h2>📋 Pipeline Overview</h2>
<div class="doc-grid">
    <a href="pipeline-workflow.html" class="doc-card pipeline-card">
        <div class="doc-title">🔄 Complete Pipeline Workflow</div>
        <div class="doc-desc">End-to-end pipeline with all phases, steps, and agents</div>
        <div class="doc-links">
            <span class="doc-link">📄 HTML</span>
            <span class="doc-link">🎨 Draw.io</span>
            <span class="doc-link">📑 PDF</span>
        </div>
    </a>
</div>

<h2>🤖 Agent Workflows</h2>
<div class="doc-grid">
"""
        for workflow in agent_workflows:
            html += f"""
    <a href="agent-{workflow.agent_name}.html" class="doc-card">
        <div class="doc-title">{workflow.agent_name.upper()}</div>
        <div class="doc-desc">{workflow.agent_role}</div>
        <div class="doc-links">
            <span class="doc-link">📄 HTML</span>
            <span class="doc-link">🎨 Draw.io</span>
        </div>
    </a>
"""
        html += f"""
</div>

</div>
</body>
</html>
"""
        return html
