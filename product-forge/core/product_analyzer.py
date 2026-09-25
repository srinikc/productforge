# DEPRECATED (2026-09-12): superseded by PipelineExecutor + core/orchestrator/*.
# Kept for reference; not part of the generic pipeline. See docs/UNWIRED-MODULES-TRIAGE.md.
"""
Product Analyzer
Comprehensive E2E analysis of existing products/projects
Identifies gaps, plans agent work, and provides recommendations
"""
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
import json
import re


@dataclass
class StructureAnalysis:
    """Analysis of project structure"""
    total_files: int = 0
    total_directories: int = 0
    code_files: int = 0
    test_files: int = 0
    doc_files: int = 0
    config_files: int = 0
    main_entry_points: List[str] = field(default_factory=list)
    directory_structure: Dict[str, Any] = field(default_factory=dict)
    tech_stack: List[str] = field(default_factory=list)
    detected_frameworks: List[str] = field(default_factory=list)
    architecture_pattern: str = "unknown"


@dataclass
class CodeQualityMetrics:
    """Code quality metrics"""
    avg_file_size: float = 0.0
    largest_files: List[Dict[str, Any]] = field(default_factory=list)
    code_smells: List[Dict[str, Any]] = field(default_factory=list)
    naming_consistency: float = 0.0
    error_handling_score: float = 0.0
    documentation_score: float = 0.0
    overall_quality_score: float = 0.0


@dataclass
class TestCoverageAnalysis:
    """Test coverage analysis"""
    has_tests: bool = False
    test_frameworks: List[str] = field(default_factory=list)
    test_directories: List[str] = field(default_factory=list)
    estimated_coverage: float = 0.0
    test_types: List[str] = field(default_factory=list)  # unit, integration, e2e
    test_quality: str = "unknown"
    missing_test_types: List[str] = field(default_factory=list)


@dataclass
class SecurityFinding:
    """Security finding"""
    severity: str  # critical, high, medium, low
    type: str  # vulnerability, secret, misconfig
    file: str
    line: Optional[int] = None
    description: str = ""
    recommendation: str = ""


@dataclass
class GapAnalysis:
    """Gap analysis against pipeline standards"""
    missing_artifacts: List[str] = field(default_factory=list)
    compliance_issues: List[str] = field(default_factory=list)
    improvement_areas: List[str] = field(default_factory=list)
    best_practice_score: float = 0.0
    pipeline_readiness: float = 0.0


@dataclass
class AgentWorkItem:
    """Planned work for an agent"""
    agent: str
    stage: int
    action: str
    description: str
    estimated_effort: str  # hours
    priority: str  # critical, high, medium, low
    dependencies: List[str] = field(default_factory=list)
    deliverables: List[str] = field(default_factory=list)


@dataclass
class Recommendation:
    """A recommendation for the user"""
    title: str
    description: str
    priority: str
    effort: str
    impact: str
    category: str
    agent_responsible: str


@dataclass
class UserQuestion:
    """A question to ask the user"""
    question: str
    context: str
    options: List[str] = field(default_factory=list)
    default: Optional[str] = None
    required: bool = True


@dataclass
class AnalysisReport:
    """Complete analysis report"""
    product_name: str
    timestamp: str
    structure: StructureAnalysis
    code_quality: CodeQualityMetrics
    test_coverage: TestCoverageAnalysis
    security_findings: List[SecurityFinding]
    gap_analysis: GapAnalysis
    agent_work_plan: List[AgentWorkItem]
    recommendations: List[Recommendation]
    user_questions: List[UserQuestion]
    overall_score: float = 0.0
    pipeline_ready: bool = False


class ProductAnalyzer:
    """Comprehensive product analyzer"""

    def __init__(self, products_dir: str = "products"):
        self.products_dir = Path(products_dir)

    def analyze_product(self, product_name: str, source_path: str) -> AnalysisReport:
        """Perform comprehensive E2E analysis of a product"""
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"Source path not found: {source_path}")

        # 1. Structure Analysis
        structure = self._analyze_structure(source)

        # 2. Code Quality Analysis
        code_quality = self._analyze_code_quality(source)

        # 3. Test Coverage Analysis
        test_coverage = self._analyze_test_coverage(source)

        # 4. Security Analysis
        security_findings = self._analyze_security(source)

        # 5. Gap Analysis
        gap_analysis = self._analyze_gaps(structure, code_quality, test_coverage, security_findings)

        # 6. Agent Work Planning
        agent_work_plan = self._plan_agent_work(structure, code_quality, test_coverage, security_findings, gap_analysis)

        # 7. Recommendations
        recommendations = self._generate_recommendations(structure, code_quality, test_coverage, security_findings, gap_analysis)

        # 8. User Questions
        user_questions = self._generate_user_questions(structure, gap_analysis)

        # Calculate overall score
        overall_score = self._calculate_overall_score(structure, code_quality, test_coverage, gap_analysis)

        # Determine pipeline readiness
        pipeline_ready = overall_score >= 70 and len(security_findings) == 0

        return AnalysisReport(
            product_name=product_name,
            timestamp=datetime.now().isoformat(),
            structure=structure,
            code_quality=code_quality,
            test_coverage=test_coverage,
            security_findings=security_findings,
            gap_analysis=gap_analysis,
            agent_work_plan=agent_work_plan,
            recommendations=recommendations,
            user_questions=user_questions,
            overall_score=overall_score,
            pipeline_ready=pipeline_ready
        )

    def _analyze_structure(self, source: Path) -> StructureAnalysis:
        """Analyze project structure"""
        analysis = StructureAnalysis()

        all_files = list(source.rglob("*"))
        files = [f for f in all_files if f.is_file()]
        dirs = [d for d in all_files if d.is_dir()]

        analysis.total_files = len(files)
        analysis.total_directories = len(dirs)

        # Categorize files
        code_extensions = {".py", ".js", ".ts", ".java", ".go", ".rs", ".rb", ".php", ".cs", ".cpp", ".c", ".h"}
        test_patterns = ["test_", "_test.", "tests/", "spec/", "__tests__"]
        doc_extensions = {".md", ".rst", ".txt", ".adoc"}
        config_patterns = ["config", "settings", ".env", "package.json", "requirements.txt", "Cargo.toml", "go.mod", "pom.xml", "build.gradle"]

        for f in files:
            if f.suffix in code_extensions:
                analysis.code_files += 1
            if any(p in str(f) for p in test_patterns):
                analysis.test_files += 1
            if f.suffix in doc_extensions:
                analysis.doc_files += 1
            if any(p in str(f).lower() for p in config_patterns):
                analysis.config_files += 1

        # Detect tech stack
        analysis.tech_stack = self._detect_tech_stack(source)

        # Detect frameworks
        analysis.detected_frameworks = self._detect_frameworks(source)

        # Detect entry points
        analysis.main_entry_points = self._detect_entry_points(source)

        # Detect architecture pattern
        analysis.architecture_pattern = self._detect_architecture(source)

        # Directory structure
        analysis.directory_structure = self._build_directory_tree(source, max_depth=3)

        return analysis

    def _detect_tech_stack(self, source: Path) -> List[str]:
        """Detect technology stack"""
        stack = []
        indicators = {
            "package.json": "Node.js",
            "requirements.txt": "Python",
            "Pipfile": "Python (Pipenv)",
            "pyproject.toml": "Python (Poetry)",
            "Cargo.toml": "Rust",
            "go.mod": "Go",
            "pom.xml": "Java (Maven)",
            "build.gradle": "Java (Gradle)",
            "Gemfile": "Ruby",
            "composer.json": "PHP",
            "Dockerfile": "Docker",
            "docker-compose.yml": "Docker Compose",
            ".github": "GitHub Actions",
            ".gitlab-ci.yml": "GitLab CI",
            "Jenkinsfile": "Jenkins",
            "terraform": "Terraform",
            "ansible": "Ansible",
            "kubernetes": "Kubernetes"
        }

        for indicator, tech in indicators.items():
            if list(source.rglob(indicator)):
                stack.append(tech)

        return stack

    def _detect_frameworks(self, source: Path) -> List[str]:
        """Detect frameworks used"""
        frameworks = []

        # Python frameworks
        requirements_files = list(source.rglob("requirements.txt"))
        for req_file in requirements_files:
            try:
                content = req_file.read_text(encoding="utf-8", errors="ignore").lower()
                if "django" in content:
                    frameworks.append("Django")
                if "flask" in content:
                    frameworks.append("Flask")
                if "fastapi" in content:
                    frameworks.append("FastAPI")
                if "pytest" in content:
                    frameworks.append("pytest")
            except:
                pass

        # Node.js frameworks
        package_files = list(source.rglob("package.json"))
        for pkg_file in package_files:
            try:
                content = pkg_file.read_text(encoding="utf-8", errors="ignore").lower()
                if "react" in content:
                    frameworks.append("React")
                if "vue" in content:
                    frameworks.append("Vue")
                if "angular" in content:
                    frameworks.append("Angular")
                if "express" in content:
                    frameworks.append("Express")
                if "jest" in content:
                    frameworks.append("Jest")
            except:
                pass

        return list(set(frameworks))

    def _detect_entry_points(self, source: Path) -> List[str]:
        """Detect main entry points"""
        entry_points = []

        # Common entry point patterns
        patterns = [
            "main.py", "app.py", "server.py", "index.js", "index.ts",
            "main.go", "Main.java", "Program.cs", "main.rs"
        ]

        for pattern in patterns:
            matches = list(source.rglob(pattern))
            for match in matches:
                entry_points.append(str(match.relative_to(source)))

        return entry_points[:10]  # Limit to 10

    def _detect_architecture(self, source: Path) -> str:
        """Detect architecture pattern"""
        # Check for common architecture patterns
        if (source / "src" / "controllers").exists() or (source / "app" / "controllers").exists():
            return "MVC"
        if (source / "src" / "api").exists() or (source / "api").exists():
            return "API-based"
        if (source / "src" / "services").exists():
            return "Service-oriented"
        if (source / "src" / "components").exists():
            return "Component-based"
        if (source / "lib").exists():
            return "Library"
        return "Unknown"

    def _build_directory_tree(self, source: Path, max_depth: int = 3) -> Dict[str, Any]:
        """Build directory tree representation"""
        def build_tree(path: Path, depth: int = 0) -> Dict[str, Any]:
            if depth > max_depth:
                return {"name": path.name, "truncated": True}

            tree = {"name": path.name, "type": "dir", "children": []}
            try:
                for item in sorted(path.iterdir()):
                    if item.name.startswith('.'):
                        continue
                    if item.is_dir():
                        tree["children"].append(build_tree(item, depth + 1))
                    else:
                        tree["children"].append({"name": item.name, "type": "file"})
            except PermissionError:
                pass
            return tree

        return build_tree(source)

    def _analyze_code_quality(self, source: Path) -> CodeQualityMetrics:
        """Analyze code quality"""
        metrics = CodeQualityMetrics()

        code_extensions = {".py", ".js", ".ts", ".java", ".go", ".rs", ".rb", ".php"}
        code_files = [f for f in source.rglob("*") if f.suffix in code_extensions and f.is_file()]

        if not code_files:
            return metrics

        file_sizes = []
        for f in code_files:
            try:
                size = f.stat().st_size
                file_sizes.append({"file": str(f.relative_to(source)), "size": size})
            except:
                pass

        if file_sizes:
            metrics.avg_file_size = sum(f["size"] for f in file_sizes) / len(file_sizes)
            metrics.largest_files = sorted(file_sizes, key=lambda x: x["size"], reverse=True)[:5]

        # Check for code smells
        metrics.code_smells = self._detect_code_smells(code_files)

        # Calculate scores
        metrics.naming_consistency = self._check_naming_consistency(code_files)
        metrics.error_handling_score = self._check_error_handling(code_files)
        metrics.documentation_score = self._check_documentation(code_files)
        metrics.overall_quality_score = (
            metrics.naming_consistency * 0.3 +
            metrics.error_handling_score * 0.3 +
            metrics.documentation_score * 0.4
        )

        return metrics

    def _detect_code_smells(self, code_files: List[Path]) -> List[Dict[str, Any]]:
        """Detect common code smells"""
        smells = []

        for f in code_files[:20]:  # Limit to 20 files
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                lines = content.split("\n")

                # Long files
                if len(lines) > 500:
                    smells.append({
                        "type": "long_file",
                        "file": str(f.relative_to(f.parents[len(f.parents) - 1])),
                        "lines": len(lines),
                        "severity": "medium"
                    })

                # Long functions (simple heuristic)
                for i, line in enumerate(lines):
                    if line.strip().startswith("def ") or line.strip().startswith("function "):
                        func_start = i
                        indent = len(line) - len(line.lstrip())
                        for j in range(i + 1, min(i + 200, len(lines))):
                            if lines[j].strip() and not lines[j].startswith(" " * (indent + 1)):
                                if j - func_start > 50:
                                    smells.append({
                                        "type": "long_function",
                                        "file": str(f.relative_to(f.parents[len(f.parents) - 1])),
                                        "line": func_start + 1,
                                        "severity": "low"
                                    })
                                break

                # TODO comments
                todo_count = content.count("TODO")
                if todo_count > 0:
                    smells.append({
                        "type": "todo_comments",
                        "file": str(f.relative_to(f.parents[len(f.parents) - 1])),
                        "count": todo_count,
                        "severity": "low"
                    })
            except:
                pass

        return smells[:20]

    def _check_naming_consistency(self, code_files: List[Path]) -> float:
        """Check naming consistency"""
        snake_case = 0
        camelCase = 0
        PascalCase = 0

        for f in code_files[:10]:
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                # Python functions/variables (snake_case)
                snake_case += len(re.findall(r'\bdef\s+[a-z][a-z0-9_]*\b', content))
                snake_case += len(re.findall(r'\b[a-z][a-z0-9_]*\s*=\s*', content))
                # camelCase
                camelCase += len(re.findall(r'\b[a-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*\b', content))
                # PascalCase
                PascalCase += len(re.findall(r'\bclass\s+[A-Z][a-zA-Z0-9]*\b', content))
            except:
                pass

        total = snake_case + camelCase + PascalCase
        if total == 0:
            return 0.5

        # Check for consistency (one style should dominate)
        max_style = max(snake_case, camelCase, PascalCase)
        return max_style / total if total > 0 else 0.5

    def _check_error_handling(self, code_files: List[Path]) -> float:
        """Check error handling"""
        error_keywords = ["try", "except", "catch", "error", "Error", "Exception"]
        total_score = 0
        file_count = 0

        for f in code_files[:10]:
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                has_error_handling = any(keyword in content for keyword in error_keywords)
                if has_error_handling:
                    total_score += 1
                file_count += 1
            except:
                pass

        return total_score / file_count if file_count > 0 else 0.0

    def _check_documentation(self, code_files: List[Path]) -> float:
        """Check documentation"""
        doc_score = 0
        file_count = 0

        for f in code_files[:10]:
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                lines = content.split("\n")

                # Check for docstrings/comments
                has_docstring = '"""' in content or "'''" in content or "/*" in content or "//" in content
                if has_docstring:
                    doc_score += 1
                file_count += 1
            except:
                pass

        return doc_score / file_count if file_count > 0 else 0.0

    def _analyze_test_coverage(self, source: Path) -> TestCoverageAnalysis:
        """Analyze test coverage"""
        analysis = TestCoverageAnalysis()

        # Detect test directories
        test_dirs = ["test", "tests", "spec", "__tests__", "test_"]
        for td in test_dirs:
            if (source / td).exists():
                analysis.test_directories.append(td)
                analysis.has_tests = True

        # Detect test files
        test_files = []
        for pattern in ["test_*.py", "*_test.py", "*.test.js", "*.spec.js", "*Test.java"]:
            test_files.extend(list(source.rglob(pattern)))

        if test_files:
            analysis.has_tests = True
            analysis.test_types.append("unit")  # Assume unit tests

            # Check for integration tests
            integration_indicators = ["integration", "e2e", "end-to-end", "system"]
            for indicator in integration_indicators:
                if any(indicator in str(f).lower() for f in test_files):
                    analysis.test_types.append(indicator)
                    break

        # Detect test frameworks
        if list(source.rglob("pytest.ini")) or list(source.rglob("conftest.py")):
            analysis.test_frameworks.append("pytest")
        if list(source.rglob("jest.config.*")):
            analysis.test_frameworks.append("Jest")
        if list(source.rglob("*.test.ts")):
            analysis.test_frameworks.append("Jest/TypeScript")

        # Estimate coverage (very rough)
        code_files = [f for f in source.rglob("*.py") if "test" not in str(f).lower()]
        if code_files and test_files:
            analysis.estimated_coverage = min(100, (len(test_files) / len(code_files)) * 100)

        # Determine missing test types
        if "unit" not in analysis.test_types:
            analysis.missing_test_types.append("unit")
        if "integration" not in analysis.test_types:
            analysis.missing_test_types.append("integration")
        if "e2e" not in analysis.test_types:
            analysis.missing_test_types.append("e2e")

        # Assess test quality
        if not analysis.has_tests:
            analysis.test_quality = "none"
        elif analysis.estimated_coverage < 30:
            analysis.test_quality = "poor"
        elif analysis.estimated_coverage < 60:
            analysis.test_quality = "fair"
        elif analysis.estimated_coverage < 80:
            analysis.test_quality = "good"
        else:
            analysis.test_quality = "excellent"

        return analysis

    def _analyze_security(self, source: Path) -> List[SecurityFinding]:
        """Analyze security"""
        findings = []

        # Check for hardcoded secrets
        secret_patterns = [
            (r'password\s*=\s*["\'][\w]+["\']', "Hardcoded password"),
            (r'api_key\s*=\s*["\'][\w]+["\']', "Hardcoded API key"),
            (r'secret\s*=\s*["\'][\w]+["\']', "Hardcoded secret"),
            (r'token\s*=\s*["\'][\w]+["\']', "Hardcoded token"),
        ]

        code_files = [f for f in source.rglob("*") if f.suffix in {".py", ".js", ".ts", ".java", ".go", ".rb", ".php"}]

        for f in code_files[:20]:
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                for pattern, description in secret_patterns:
                    matches = re.finditer(pattern, content, re.IGNORECASE)
                    for match in matches:
                        findings.append(SecurityFinding(
                            severity="high",
                            type="secret",
                            file=str(f.relative_to(source)),
                            description=description,
                            recommendation="Use environment variables or a secrets manager"
                        ))
            except:
                pass

        # Check for SQL injection patterns
        sql_patterns = [
            (r'execute\s*\(\s*["\'].*\+.*["\']', "Potential SQL injection"),
            (r'query\s*\(\s*["\'].*\+.*["\']', "Potential SQL injection"),
        ]

        for f in code_files[:20]:
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                for pattern, description in sql_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        findings.append(SecurityFinding(
                            severity="critical",
                            type="vulnerability",
                            file=str(f.relative_to(source)),
                            description=description,
                            recommendation="Use parameterized queries"
                        ))
            except:
                pass

        # Check for missing .env in .gitignore
        if list(source.rglob(".env*")):
            gitignore = source / ".gitignore"
            if gitignore.exists():
                try:
                    content = gitignore.read_text(encoding="utf-8", errors="ignore")
                    if ".env" not in content:
                        findings.append(SecurityFinding(
                            severity="medium",
                            type="misconfig",
                            file=".gitignore",
                            description=".env files not in .gitignore",
                            recommendation="Add .env to .gitignore"
                        ))
                except:
                    pass

        return findings[:20]

    def _analyze_gaps(self, structure: StructureAnalysis, code_quality: CodeQualityMetrics,
                      test_coverage: TestCoverageAnalysis, security: List[SecurityFinding]) -> GapAnalysis:
        """Analyze gaps against pipeline standards"""
        gap = GapAnalysis()

        # Missing artifacts
        if structure.doc_files == 0:
            gap.missing_artifacts.append("No README or documentation")
        if not structure.main_entry_points:
            gap.missing_artifacts.append("No clear entry point identified")
        if not test_coverage.has_tests:
            gap.missing_artifacts.append("No tests found")
        if not any("Docker" in t for t in structure.tech_stack):
            gap.missing_artifacts.append("No Docker configuration")
        if not any("CI" in t or "Actions" in t for t in structure.tech_stack):
            gap.missing_artifacts.append("No CI/CD configuration")

        # Compliance issues
        if security:
            critical = [f for f in security if f.severity == "critical"]
            if critical:
                gap.compliance_issues.append(f"{len(critical)} critical security issues found")
            high = [f for f in security if f.severity == "high"]
            if high:
                gap.compliance_issues.append(f"{len(high)} high-severity security issues found")

        if code_quality.overall_quality_score < 0.5:
            gap.compliance_issues.append("Code quality below acceptable threshold")

        # Improvement areas
        if test_coverage.estimated_coverage < 60:
            gap.improvement_areas.append("Increase test coverage")
        if code_quality.documentation_score < 0.5:
            gap.improvement_areas.append("Improve code documentation")
        if not test_coverage.test_frameworks:
            gap.improvement_areas.append("Set up test framework")

        # Calculate scores
        structure_score = min(100, (structure.code_files / max(structure.total_files, 1)) * 100)
        quality_score = code_quality.overall_quality_score * 100
        test_score = test_coverage.estimated_coverage
        security_score = max(0, 100 - len(security) * 10)

        gap.best_practice_score = (structure_score + quality_score + test_score + security_score) / 4
        gap.pipeline_readiness = gap.best_practice_score

        return gap

    def _plan_agent_work(self, structure: StructureAnalysis, code_quality: CodeQualityMetrics,
                        test_coverage: TestCoverageAnalysis, security: List[SecurityFinding],
                        gap: GapAnalysis) -> List[AgentWorkItem]:
        """Plan agent work needed"""
        work_plan = []

        # Always run design agent for new products
        work_plan.append(AgentWorkItem(
            agent="design",
            stage=1,
            action="document",
            description="Create formal design docs for the product",
            estimated_effort="4-8 hours",
            priority="high",
            dependencies=[],
            deliverables=["docs/requirements.md", "docs/design.md"]
        ))

        # Architect agent if architecture is unclear
        if structure.architecture_pattern == "Unknown":
            work_plan.append(AgentWorkItem(
                agent="architect",
                stage=2,
                action="design",
                description="Define architecture and create ADRs",
                estimated_effort="8-16 hours",
                priority="high",
                dependencies=["design"],
                deliverables=["docs/architecture.md", "docs/decisions/"]
            ))

        # Code review agent
        work_plan.append(AgentWorkItem(
            agent="code-review",
            stage=5,
            action="review",
            description="Review existing code quality and identify issues",
            estimated_effort="4-8 hours",
            priority="high",
            dependencies=[],
            deliverables=["reports/code-review.md"]
        ))

        # Security agent (if security issues found)
        if security:
            work_plan.append(AgentWorkItem(
                agent="security",
                stage=4,
                action="scan",
                description="Run comprehensive security analysis",
                estimated_effort="4-8 hours",
                priority="critical",
                dependencies=[],
                deliverables=["security/security-issues.json", "security/reports/"]
            ))

        # Validate agent (if tests missing or low coverage)
        if not test_coverage.has_tests or test_coverage.estimated_coverage < 60:
            work_plan.append(AgentWorkItem(
                agent="validate",
                stage=6,
                action="test",
                description="Set up test framework and add comprehensive tests",
                estimated_effort="16-40 hours",
                priority="high",
                dependencies=["implement"],
                deliverables=["tests/", "reports/coverage/"]
            ))

        # Document agent
        if structure.doc_files < 5:
            work_plan.append(AgentWorkItem(
                agent="document",
                stage=8,
                action="document",
                description="Generate comprehensive documentation",
                estimated_effort="8-16 hours",
                priority="high",
                dependencies=[],
                deliverables=["docs/", "README.md"]
            ))

        # DevOps agent
        if not any("CI" in t or "Docker" in t for t in structure.tech_stack):
            work_plan.append(AgentWorkItem(
                agent="devops",
                stage=9,
                action="setup",
                description="Set up CI/CD and deployment",
                estimated_effort="8-16 hours",
                priority="medium",
                dependencies=[],
                deliverables=[".github/workflows/", "Dockerfile"]
            ))

        # Presentation agent (for product launch)
        work_plan.append(AgentWorkItem(
            agent="presentation",
            stage=14,
            action="generate",
            description="Generate product presentation and demo materials",
            estimated_effort="4-8 hours",
            priority="medium",
            dependencies=["document"],
            deliverables=["presentations/", "videos/", "marketing/"]
        ))

        return work_plan

    def _generate_recommendations(self, structure: StructureAnalysis, code_quality: CodeQualityMetrics,
                                 test_coverage: TestCoverageAnalysis, security: List[SecurityFinding],
                                 gap: GapAnalysis) -> List[Recommendation]:
        """Generate recommendations"""
        recs = []

        # Critical security issues
        critical_security = [f for f in security if f.severity in ["critical", "high"]]
        if critical_security:
            recs.append(Recommendation(
                title="Fix Critical Security Issues",
                description=f"Found {len(critical_security)} critical/high security issues. These must be fixed immediately.",
                priority="critical",
                effort="4-8 hours",
                impact="high",
                category="security",
                agent_responsible="security"
            ))

        # Test coverage
        if test_coverage.estimated_coverage < 60:
            recs.append(Recommendation(
                title="Increase Test Coverage",
                description=f"Current test coverage is {test_coverage.estimated_coverage:.0f}%. Target 80%+ for production readiness.",
                priority="high",
                effort="16-40 hours",
                impact="high",
                category="quality",
                agent_responsible="validate"
            ))

        # Documentation
        if structure.doc_files < 5:
            recs.append(Recommendation(
                title="Add Comprehensive Documentation",
                description="Product has minimal documentation. Add README, API docs, and user guide.",
                priority="high",
                effort="8-16 hours",
                impact="medium",
                category="documentation",
                agent_responsible="document"
            ))

        # CI/CD
        if not any("CI" in t or "Actions" in t for t in structure.tech_stack):
            recs.append(Recommendation(
                title="Set Up CI/CD Pipeline",
                description="No CI/CD configuration found. Set up automated testing and deployment.",
                priority="high",
                effort="8-16 hours",
                impact="high",
                category="devops",
                agent_responsible="devops"
            ))

        # Code quality
        if code_quality.overall_quality_score < 0.5:
            recs.append(Recommendation(
                title="Improve Code Quality",
                description="Code quality metrics are below acceptable threshold. Refactor and improve.",
                priority="medium",
                effort="16-40 hours",
                impact="medium",
                category="quality",
                agent_responsible="code-review"
            ))

        # Architecture documentation
        if structure.architecture_pattern == "Unknown":
            recs.append(Recommendation(
                title="Document Architecture",
                description="Architecture pattern is unclear. Create architecture documentation and ADRs.",
                priority="medium",
                effort="4-8 hours",
                impact="medium",
                category="architecture",
                agent_responsible="architect"
            ))

        # Quick wins
        recs.append(Recommendation(
            title="Set Up Pipeline Tracking",
            description="Initialize product-plan.json, traceability.json, and agent_ledger.json for pipeline integration.",
            priority="high",
            effort="1-2 hours",
            impact="high",
            category="integration",
            agent_responsible="product-analyzer"
        ))

        recs.append(Recommendation(
            title="Add Entry to Pipeline Dashboard",
            description="Register the product in the pipeline dashboard for monitoring and tracking.",
            priority="medium",
            effort="0.5-1 hour",
            impact="medium",
            category="integration",
            agent_responsible="devops"
        ))

        return recs

    def _generate_user_questions(self, structure: StructureAnalysis,
                                 gap: GapAnalysis) -> List[UserQuestion]:
        """Generate questions for the user"""
        questions = []

        # Product type question
        questions.append(UserQuestion(
            question="What is the primary product type?",
            context="This helps determine the right quality standards and agent configuration.",
            options=["exploration", "learning", "fun", "prototype", "personal", "internal", "product", "business"],
            default="prototype",
            required=True
        ))

        # Priority question
        questions.append(UserQuestion(
            question="What is your top priority for this product?",
            context="This helps prioritize the agent work plan.",
            options=["Security", "Quality", "Documentation", "Speed to market", "Feature completeness"],
            default="Quality",
            required=True
        ))

        # Timeline question
        questions.append(UserQuestion(
            question="What is your timeline for pipeline integration?",
            context="This affects how we sequence the agent work.",
            options=["Immediate (1 week)", "Short-term (1 month)", "Medium-term (3 months)", "Long-term (6+ months)"],
            default="Short-term (1 month)",
            required=True
        ))

        # Test strategy
        if not structure.tech_stack or "Python" in str(structure.tech_stack):
            questions.append(UserQuestion(
                question="What testing strategy do you prefer?",
                context="This determines which test types to prioritize.",
                options=["Unit tests only", "Unit + Integration", "Full pyramid (Unit + Integration + E2E)", "Minimal (smoke tests)"],
                default="Full pyramid (Unit + Integration + E2E)",
                required=False
            ))

        # Deployment question
        questions.append(UserQuestion(
            question="Where will this product be deployed?",
            context="This affects DevOps agent configuration.",
            options=["Cloud (AWS/GCP/Azure)", "On-premise", "Hybrid", "Not yet decided"],
            default="Cloud (AWS/GCP/Azure)",
            required=True
        ))

        # Security level
        questions.append(UserQuestion(
            question="What security level is required?",
            context="This determines the security agent's thoroughness.",
            options=["Basic", "Standard", "High", "Maximum (compliance required)"],
            default="Standard",
            required=True
        ))

        # Integration preferences
        questions.append(UserQuestion(
            question="Do you want to use BYOT (Bring Your Own Tools)?",
            context="This determines if you need custom model/MCP server integration.",
            options=["Yes, I have custom tools/models", "No, use defaults", "Not sure"],
            default="No, use defaults",
            required=False
        ))

        # Presentation needs
        questions.append(UserQuestion(
            question="Do you need presentation/marketing materials?",
            context="This determines if the presentation agent should run.",
            options=["Yes, full presentation package", "Yes, just docs", "No, internal project"],
            default="Yes, full presentation package",
            required=False
        ))

        return questions

    def _calculate_overall_score(self, structure: StructureAnalysis, code_quality: CodeQualityMetrics,
                                test_coverage: TestCoverageAnalysis, gap: GapAnalysis) -> float:
        """Calculate overall readiness score"""
        structure_score = min(100, (structure.code_files / max(structure.total_files, 1)) * 100) * 0.2
        quality_score = code_quality.overall_quality_score * 100 * 0.3
        test_score = test_coverage.estimated_coverage * 0.3
        gap_score = gap.best_practice_score * 0.2

        return structure_score + quality_score + test_score + gap_score

    def save_analysis(self, report: AnalysisReport, output_dir: Path):
        """Save analysis report to files"""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save main report as JSON
        report_data = {
            "product_name": report.product_name,
            "timestamp": report.timestamp,
            "overall_score": report.overall_score,
            "pipeline_ready": report.pipeline_ready,
            "structure": {
                "total_files": report.structure.total_files,
                "total_directories": report.structure.total_directories,
                "code_files": report.structure.code_files,
                "test_files": report.structure.test_files,
                "doc_files": report.structure.doc_files,
                "tech_stack": report.structure.tech_stack,
                "frameworks": report.structure.detected_frameworks,
                "architecture_pattern": report.structure.architecture_pattern,
                "entry_points": report.structure.main_entry_points
            },
            "code_quality": {
                "avg_file_size": report.code_quality.avg_file_size,
                "overall_score": report.code_quality.overall_quality_score,
                "naming_consistency": report.code_quality.naming_consistency,
                "documentation_score": report.code_quality.documentation_score
            },
            "test_coverage": {
                "has_tests": report.test_coverage.has_tests,
                "frameworks": report.test_coverage.test_frameworks,
                "estimated_coverage": report.test_coverage.estimated_coverage,
                "quality": report.test_coverage.test_quality,
                "missing_types": report.test_coverage.missing_test_types
            },
            "security_findings": [
                {
                    "severity": f.severity,
                    "type": f.type,
                    "file": f.file,
                    "description": f.description,
                    "recommendation": f.recommendation
                }
                for f in report.security_findings
            ],
            "gap_analysis": {
                "missing_artifacts": report.gap_analysis.missing_artifacts,
                "compliance_issues": report.gap_analysis.compliance_issues,
                "improvement_areas": report.gap_analysis.improvement_areas,
                "best_practice_score": report.gap_analysis.best_practice_score,
                "pipeline_readiness": report.gap_analysis.pipeline_readiness
            },
            "agent_work_plan": [
                {
                    "agent": w.agent,
                    "stage": w.stage,
                    "action": w.action,
                    "description": w.description,
                    "effort": w.estimated_effort,
                    "priority": w.priority,
                    "dependencies": w.dependencies,
                    "deliverables": w.deliverables
                }
                for w in report.agent_work_plan
            ],
            "recommendations": [
                {
                    "title": r.title,
                    "description": r.description,
                    "priority": r.priority,
                    "effort": r.effort,
                    "impact": r.impact,
                    "category": r.category,
                    "agent": r.agent_responsible
                }
                for r in report.recommendations
            ],
            "user_questions": [
                {
                    "question": q.question,
                    "context": q.context,
                    "options": q.options,
                    "default": q.default,
                    "required": q.required
                }
                for q in report.user_questions
            ]
        }

        # Save JSON
        json_path = output_dir / "analysis-report.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        # Save Markdown summary
        md_path = output_dir / "analysis-summary.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(self._generate_markdown_summary(report))

        return json_path, md_path

    def _generate_markdown_summary(self, report: AnalysisReport) -> str:
        """Generate markdown summary"""
        md = f"""# {report.product_name} - Analysis Summary

**Generated:** {report.timestamp}
**Overall Score:** {report.overall_score:.1f}/100
**Pipeline Ready:** {'✅ Yes' if report.pipeline_ready else '❌ No'}

## Project Structure

- **Total Files:** {report.structure.total_files}
- **Code Files:** {report.structure.code_files}
- **Test Files:** {report.structure.test_files}
- **Documentation Files:** {report.structure.doc_files}
- **Tech Stack:** {', '.join(report.structure.tech_stack) or 'None detected'}
- **Frameworks:** {', '.join(report.structure.detected_frameworks) or 'None detected'}
- **Architecture Pattern:** {report.structure.architecture_pattern}

## Code Quality

- **Overall Score:** {report.code_quality.overall_quality_score:.1%}
- **Naming Consistency:** {report.code_quality.naming_consistency:.1%}
- **Documentation Score:** {report.code_quality.documentation_score:.1%}
- **Code Smells Found:** {len(report.code_quality.code_smells)}

## Test Coverage

- **Has Tests:** {'Yes' if report.test_coverage.has_tests else 'No'}
- **Test Frameworks:** {', '.join(report.test_coverage.test_frameworks) or 'None'}
- **Estimated Coverage:** {report.test_coverage.estimated_coverage:.1f}%
- **Test Quality:** {report.test_coverage.test_quality}
- **Missing Test Types:** {', '.join(report.test_coverage.missing_test_types) or 'None'}

## Security Findings

**Total:** {len(report.security_findings)}
- Critical: {sum(1 for f in report.security_findings if f.severity == 'critical')}
- High: {sum(1 for f in report.security_findings if f.severity == 'high')}
- Medium: {sum(1 for f in report.security_findings if f.severity == 'medium')}
- Low: {sum(1 for f in report.security_findings if f.severity == 'low')}

## Gap Analysis

### Missing Artifacts

"""
        for item in report.gap_analysis.missing_artifacts:
            md += f"- {item}\n"

        md += "\n### Compliance Issues\n\n"
        for item in report.gap_analysis.compliance_issues:
            md += f"- {item}\n"

        md += "\n### Improvement Areas\n\n"
        for item in report.gap_analysis.improvement_areas:
            md += f"- {item}\n"

        md += f"\n**Best Practice Score:** {report.gap_analysis.best_practice_score:.1f}/100\n"
        md += f"**Pipeline Readiness:** {report.gap_analysis.pipeline_readiness:.1f}/100\n"

        md += "\n## Agent Work Plan\n\n"
        for work in report.agent_work_plan:
            md += f"### {work.agent.upper()} (Stage {work.stage}) - {work.priority.upper()}\n\n"
            md += f"**Action:** {work.action}\n"
            md += f"**Description:** {work.description}\n"
            md += f"**Estimated Effort:** {work.estimated_effort}\n"
            if work.dependencies:
                md += f"**Dependencies:** {', '.join(work.dependencies)}\n"
            md += f"**Deliverables:** {', '.join(work.deliverables)}\n\n"

        md += "## Recommendations\n\n"
        for rec in report.recommendations:
            md += f"### [{rec.priority.upper()}] {rec.title}\n\n"
            md += f"**Description:** {rec.description}\n"
            md += f"**Effort:** {rec.effort}\n"
            md += f"**Impact:** {rec.impact}\n"
            md += f"**Category:** {rec.category}\n"
            md += f"**Agent:** {rec.agent_responsible}\n\n"

        md += "## Questions for You\n\n"
        for i, q in enumerate(report.user_questions, 1):
            md += f"### {i}. {q.question}\n\n"
            md += f"**Context:** {q.context}\n"
            if q.options:
                md += f"**Options:**\n"
                for opt in q.options:
                    md += f"- {opt}\n"
            if q.default:
                md += f"**Default:** {q.default}\n"
            md += f"**Required:** {'Yes' if q.required else 'No'}\n\n"

        md += """## Next Steps

1. **Review this analysis** with your team
2. **Answer the questions** above to refine the plan
3. **Prioritize recommendations** based on your goals
4. **Start the agent work plan** with highest priority items
5. **Re-run analysis** after major changes to track progress

## Pipeline Integration

Once you've addressed the gaps:
1. Run `/pipeline ingest [product]` to fully integrate
2. Run `/pipeline present [product]` for marketing materials
3. Monitor via the pipeline dashboard
4. Set up maintenance and FinOps tracking
"""

        return md
