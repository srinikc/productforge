# DEPRECATED (2026-09-12): superseded by PipelineExecutor + core/orchestrator/*.
# Kept for reference; not part of the generic pipeline. See docs/UNWIRED-MODULES-TRIAGE.md.
"""
Product Ingestion
Import existing products/projects into the pipeline for ongoing management
"""
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
import json


@dataclass
class IngestionSource:
    """Source for product ingestion"""
    type: str  # git, zip, folder, url
    location: str
    branch: Optional[str] = None
    credentials: Optional[Dict[str, str]] = None


@dataclass
class IngestionResult:
    """Result of product ingestion"""
    product_name: str
    success: bool
    files_imported: int = 0
    modules_detected: int = 0
    features_detected: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    product_plan_path: Optional[str] = None
    traceability_path: Optional[str] = None
    agent_ledger_path: Optional[str] = None


class ProductIngester:
    """Ingests existing products into the pipeline"""

    def __init__(self, products_dir: str = "products"):
        self.products_dir = Path(products_dir)

    def ingest_from_folder(self, product_name: str, source_folder: str,
                           product_type: str = "general") -> IngestionResult:
        """Ingest a product from a local folder"""
        result = IngestionResult(product_name=product_name, success=False)

        source_path = Path(source_folder)
        if not source_path.exists():
            result.errors.append(f"Source folder not found: {source_folder}")
            return result

        # Create product directory
        product_dir = self.products_dir / product_name
        product_dir.mkdir(parents=True, exist_ok=True)

        # Scan source folder
        files = list(source_path.rglob("*"))
        source_files = [f for f in files if f.is_file()]
        result.files_imported = len(source_files)

        # Detect tech stack
        tech_stack = self._detect_tech_stack(source_path)

        # Detect modules and features
        modules = self._detect_modules(source_path)
        result.modules_detected = len(modules)

        features = self._detect_features(source_path)
        result.features_detected = len(features)

        # Create product plan
        product_plan = {
            "$schema": "product-plan-v1",
            "version": "1.0.0",
            "project": product_name,
            "last_updated": datetime.now().isoformat(),
            "updated_by": "ingestion",
            "vision": {
                "summary": f"Imported product: {product_name}",
                "source": source_folder,
                "imported_at": datetime.now().isoformat()
            },
            "modules": modules,
            "tech_stack": tech_stack,
            "product_type": product_type
        }

        # Save product plan
        plan_path = product_dir / "product-plan.json"
        with open(plan_path, "w", encoding="utf-8") as f:
            json.dump(product_plan, f, indent=2, ensure_ascii=False)
        result.product_plan_path = str(plan_path)

        # Create traceability
        trace = {
            "$schema": "traceability-v1",
            "version": "1.0.0",
            "project": product_name,
            "last_updated": datetime.now().isoformat(),
            "matrix": [],
            "coverage_metrics": {
                "total_requirements": 0,
                "implemented": 0,
                "tested": 0,
                "secured": 0,
                "reviewed": 0
            }
        }

        trace_path = product_dir / "traceability.json"
        with open(trace_path, "w", encoding="utf-8") as f:
            json.dump(trace, f, indent=2, ensure_ascii=False)
        result.traceability_path = str(trace_path)

        # Create agent ledger
        ledger_dir = product_dir / "ledger"
        ledger_dir.mkdir(exist_ok=True)
        ledger = {
            "$schema": "agent-ledger-v1",
            "version": "1.0.0",
            "work_items": [],
            "summary": {
                "total_agents": 0,
                "total_work_items": 0,
                "total_files_written": 0,
                "total_projects": 1
            }
        }

        ledger_path = ledger_dir / "agent_ledger.json"
        with open(ledger_path, "w", encoding="utf-8") as f:
            json.dump(ledger, f, indent=2, ensure_ascii=False)
        result.agent_ledger_path = str(ledger_path)

        result.success = True
        return result

    def _detect_tech_stack(self, source_path: Path) -> List[str]:
        """Detect technology stack from files"""
        tech_stack = []

        # Check for common files
        files_to_check = {
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
            ".github/workflows": "GitHub Actions",
            ".gitlab-ci.yml": "GitLab CI",
            "Jenkinsfile": "Jenkins",
            "terraform": "Terraform"
        }

        for file_pattern, tech in files_to_check.items():
            matches = list(source_path.rglob(file_pattern))
            if matches:
                tech_stack.append(tech)

        return tech_stack

    def _detect_modules(self, source_path: Path) -> List[Dict[str, Any]]:
        """Detect modules from folder structure"""
        modules = []
        common_dirs = ["src", "lib", "app", "core", "api", "services", "models", "views", "controllers", "components", "modules"]

        for dir_name in common_dirs:
            dir_path = source_path / dir_name
            if dir_path.exists() and dir_path.is_dir():
                modules.append({
                    "id": f"MOD-{len(modules) + 1:03d}",
                    "name": dir_name.title(),
                    "phase": 1,
                    "status": "imported",
                    "description": f"Imported from {dir_name}/ directory",
                    "features": []
                })

        if not modules:
            modules.append({
                "id": "MOD-001",
                "name": "Main Module",
                "phase": 1,
                "status": "imported",
                "description": "Imported product",
                "features": []
            })

        return modules

    def _detect_features(self, source_path: Path) -> List[Dict[str, Any]]:
        """Detect features from code files"""
        features = []
        code_extensions = {".py", ".js", ".ts", ".java", ".go", ".rs", ".rb", ".php"}
        code_files = [f for f in source_path.rglob("*") if f.suffix in code_extensions and f.is_file()]

        # Group by parent directory
        seen_dirs = set()
        for file in code_files[:20]:  # Limit to 20 features
            parent = file.parent
            if parent not in seen_dirs:
                seen_dirs.add(parent)
                features.append({
                    "id": f"F-{len(features) + 1:03d}",
                    "name": parent.name,
                    "status": "imported",
                    "priority": "must-have",
                    "module": "MOD-001",
                    "phase": 1,
                    "file": str(file.relative_to(source_path))
                })

        return features

    def generate_ingestion_report(self, result: IngestionResult) -> str:
        """Generate ingestion report"""
        report = f"""# Product Ingestion Report

**Product:** {result.product_name}
**Status:** {'SUCCESS' if result.success else 'FAILED'}
**Date:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Summary

- **Files Imported:** {result.files_imported}
- **Modules Detected:** {result.modules_detected}
- **Features Detected:** {result.features_detected}

## Generated Files

- **Product Plan:** `{result.product_plan_path}`
- **Traceability:** `{result.traceability_path}`
- **Agent Ledger:** `{result.agent_ledger_path}`

## Errors

"""
        if result.errors:
            for error in result.errors:
                report += f"- {error}\n"
        else:
            report += "No errors.\n"

        report += "\n## Warnings\n\n"
        if result.warnings:
            for warning in result.warnings:
                report += f"- {warning}\n"
        else:
            report += "No warnings.\n"

        report += """
## Next Steps

1. Review the generated product plan
2. Verify detected modules and features
3. Run security analysis: `/pipeline security`
4. Run validation: `/pipeline validate`
5. Generate documentation: `/pipeline document`
6. Generate presentation: `/pipeline present`
"""

        return report
