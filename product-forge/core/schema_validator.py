"""Schema validation for Product Forge pipeline artifacts.

Uses jsonschema to validate data against the JSON Schemas in docs/schemas/.
Provides validate_artifact(), validate_agent_md(), and CLI interface.
"""
from __future__ import annotations

try:
    from core.paths import ROOT as _PF_ROOT
except ImportError:  # executed as a script: seed the repo root on sys.path, then retry
    import os as _pf_os
    import sys as _pf_sys
    _pf_d = _pf_os.path.abspath(__file__)
    for _pf_i in range(3):
        _pf_d = _pf_os.path.dirname(_pf_d)
        if _pf_os.path.isfile(_pf_os.path.join(_pf_d, 'core', 'paths.py')):
            _pf_sys.path.insert(0, _pf_d)
            break
    from core.paths import ROOT as _PF_ROOT

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import jsonschema

# Root of the product-forge repo
_REPO_ROOT = _PF_ROOT
_SCHEMAS_DIR = _REPO_ROOT / "docs" / "schemas"

# Schema name → filename mapping
SCHEMA_FILES: Dict[str, str] = {
    "pipeline-state": "pipeline-state.v1.schema.json",
    "agent-contract": "agent-contract.v1.schema.json",
    "audit-log-entry": "audit-log-entry.v1.schema.json",
    "product-plan": "product-plan.v1.schema.json",
    "compliance-report": "compliance-report.v1.schema.json",
    "error-response": "error-response.v1.schema.json",
    "human-gate": "human-gate.v1.schema.json",
    "project": "project.v1.schema.json",
    "infra": "infra.v1.schema.json",
}

# Schema name → example data path (for quick validation)
SCHEMA_EXAMPLE_PATHS: Dict[str, str] = {
    "pipeline-state": "products/{project}/pipeline.json",
    "product-plan": "products/{project}/product-plan.json",
    "compliance-report": "products/{project}/compliance/{agent}-compliance.md",
}


@dataclass
class ValidationError:
    """A single validation error."""
    path: str
    message: str
    schema_path: str = ""
    severity: str = "high"


@dataclass
class ValidationResult:
    """Result of a validation operation."""
    valid: bool
    schema_name: str
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    data: Optional[Dict] = None

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    def summary(self) -> str:
        status = "VALID" if self.valid else "INVALID"
        lines = [f"[{status}] {self.schema_name}"]
        for err in self.errors:
            lines.append(f"  ERROR: {err.path} — {err.message}")
        for warn in self.warnings:
            lines.append(f"  WARN: {warn}")
        return "\n".join(lines)


def _load_schema(schema_name: str) -> Dict:
    """Load a JSON schema by name."""
    if schema_name not in SCHEMA_FILES:
        raise ValueError(
            f"Unknown schema: {schema_name}. "
            f"Available: {', '.join(SCHEMA_FILES.keys())}"
        )
    schema_path = _SCHEMAS_DIR / SCHEMA_FILES[schema_name]
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_artifact(
    schema_name: str,
    data: Dict,
    strict: bool = False,
) -> ValidationResult:
    """Validate data against a JSON schema.

    Args:
        schema_name: Name of the schema (e.g., 'pipeline-state')
        data: The data to validate
        strict: If True, warnings become errors

    Returns:
        ValidationResult with valid/error fields
    """
    try:
        schema = _load_schema(schema_name)
    except (ValueError, FileNotFoundError) as e:
        return ValidationResult(
            valid=False,
            schema_name=schema_name,
            errors=[ValidationError(path="<load>", message=str(e))],
        )

    validator = jsonschema.Draft7Validator(schema)
    errors = []
    warnings = []

    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path)):
        path = ".".join(str(p) for p in error.absolute_path) or "<root>"
        err = ValidationError(
            path=path,
            message=error.message,
            schema_path=".".join(str(p) for p in error.absolute_path),
        )
        errors.append(err)

    return ValidationResult(
        valid=len(errors) == 0,
        schema_name=schema_name,
        errors=errors,
        warnings=warnings,
        data=data,
    )


def validate_pipeline_state(project: str, strict: bool = False) -> ValidationResult:
    """Validate a project's pipeline.json."""
    path = _REPO_ROOT / "products" / project / "pipeline.json"
    if not path.exists():
        return ValidationResult(
            valid=False,
            schema_name="pipeline-state",
            errors=[ValidationError(path=str(path), message="File not found")],
        )
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return validate_artifact("pipeline-state", data, strict=strict)


def validate_product_plan(project: str, strict: bool = False) -> ValidationResult:
    """Validate a project's product-plan.json."""
    path = _REPO_ROOT / "products" / project / "product-plan.json"
    if not path.exists():
        return ValidationResult(
            valid=False,
            schema_name="product-plan",
            errors=[ValidationError(path=str(path), message="File not found")],
        )
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return validate_artifact("product-plan", data, strict=strict)


def validate_agent_md(agent_id: str, strict: bool = False) -> ValidationResult:
    """Validate an agent .md file against the agent-contract schema.

    This is a basic structural validation. For full compliance checking,
    use core.compliance_check.ComplianceChecker.
    """
    agent_path = _REPO_ROOT / ".opencode" / "agent" / f"{agent_id}.md"
    if not agent_path.exists():
        return ValidationResult(
            valid=False,
            schema_name="agent-contract",
            errors=[ValidationError(path=str(agent_path), message="Agent file not found")],
        )

    # Parse the .md file into structured data
    with open(agent_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract frontmatter
    frontmatter = {}
    sections = []
    lines = content.split("\n")

    in_frontmatter = False
    fm_lines = []
    section_num = 0
    section_title = ""
    section_content = []
    in_section = False

    for line in lines:
        if line.strip() == "---":
            if not in_frontmatter:
                in_frontmatter = True
            else:
                # Parse YAML frontmatter
                for fm_line in fm_lines:
                    if ":" in fm_line:
                        key, _, val = fm_line.partition(":")
                        frontmatter[key.strip()] = val.strip().strip('"').strip("'")
                in_frontmatter = False
            continue

        if in_frontmatter:
            fm_lines.append(line)
            continue

        # Check for section headings
        if line.startswith("## "):
            if in_section and section_content:
                sections.append({
                    "number": section_num,
                    "title": section_title,
                    "level": 2,
                    "content": "\n".join(section_content),
                })
            section_content = []
            in_section = True
            heading = line[3:].strip()
            # Parse "0. METADATA" format
            parts = heading.split(".", 1)
            if len(parts) == 2 and parts[0].strip().isdigit():
                section_num = int(parts[0].strip())
                section_title = parts[1].strip()
            else:
                section_title = heading

    # Add last section
    if in_section and section_content:
        sections.append({
            "number": section_num,
            "title": section_title,
            "level": 2,
            "content": "\n".join(section_content),
        })

    # Build validation data
    agent_data = {
        "frontmatter": frontmatter,
        "title": lines[0].lstrip("# ").strip() if lines else "",
        "sections": sections,
    }

    return validate_artifact("agent-contract", agent_data, strict=strict)


def validate_all_schemas(project: Optional[str] = None) -> Dict[str, ValidationResult]:
    """Validate all available schemas. Returns dict of schema_name → result."""
    results = {}

    # Always check pipeline-state and product-plan if project given
    if project:
        results["pipeline-state"] = validate_pipeline_state(project)
        results["product-plan"] = validate_product_plan(project)

    # Check all agent .md files
    agents_dir = _REPO_ROOT / ".opencode" / "agent"
    if agents_dir.exists():
        for md_file in sorted(agents_dir.glob("*.md")):
            agent_id = md_file.stem
            results[f"agent:{agent_id}"] = validate_agent_md(agent_id)

    return results


# ── CLI Interface ──────────────────────────────────────────────────────

def _cli():
    """CLI entry point for schema validation."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m core.schema_validator validate <schema> <json-file>")
        print("  python -m core.schema_validator validate-agent <agent-id>")
        print("  python -m core.schema_validator validate-all [project]")
        print("  python -m core.schema_validator list-schemas")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "list-schemas":
        print("Available schemas:")
        for name, filename in SCHEMA_FILES.items():
            print(f"  {name}: {filename}")
        return

    if cmd == "validate" and len(sys.argv) >= 4:
        schema_name = sys.argv[2]
        json_file = sys.argv[3]
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        result = validate_artifact(schema_name, data)
        print(result.summary())
        sys.exit(0 if result.valid else 1)

    if cmd == "validate-agent" and len(sys.argv) >= 3:
        agent_id = sys.argv[2]
        result = validate_agent_md(agent_id)
        print(result.summary())
        sys.exit(0 if result.valid else 1)

    if cmd == "validate-all":
        project = sys.argv[2] if len(sys.argv) > 2 else None
        results = validate_all_schemas(project)
        all_valid = True
        for name, result in results.items():
            print(result.summary())
            print()
            if not result.valid:
                all_valid = False
        sys.exit(0 if all_valid else 1)

    print(f"Unknown command: {cmd}")
    sys.exit(1)


if __name__ == "__main__":
    _cli()
