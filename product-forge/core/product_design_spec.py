"""Product Design Spec - generates and manages the product design specification.

Creates the design spec document from pipeline outputs (ideation, design, architecture).
Used as context for downstream agents and as a source of truth for the product.
"""
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Feature:
    name: str
    description: str
    priority: str = "medium"  # low, medium, high, critical
    status: str = "planned"  # planned, in-progress, done
    stage: str = ""
    owner: str = ""


@dataclass
class DesignSpec:
    project: str
    product_name: str
    vision: str
    target_users: List[str] = field(default_factory=list)
    features: List[Feature] = field(default_factory=list)
    tech_stack: List[str] = field(default_factory=list)
    design_principles: List[str] = field(default_factory=list)
    success_metrics: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    version: str = "1.0.0"
    source_stages: List[str] = field(default_factory=list)


def create_spec_from_artifacts(project: str, artifacts: Dict[str, str]) -> DesignSpec:
    """Create a design spec from pipeline artifacts."""
    spec = DesignSpec(
        project=project,
        product_name=project,
        vision="",
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
    )

    # Parse ideation output
    if "ideation" in artifacts:
        content = artifacts["ideation"]
        spec.source_stages.append("ideation")
        spec.vision = _extract_section(content, "vision") or _extract_section(content, "overview") or ""
        spec.target_users = _extract_list(content, "target users") or _extract_list(content, "users") or []
        spec.constraints = _extract_list(content, "constraints") or []

    # Parse design output
    if "design" in artifacts:
        content = artifacts["design"]
        spec.source_stages.append("design")
        spec.design_principles = _extract_list(content, "principles") or _extract_list(content, "design principles") or []
        features = _extract_features(content)
        spec.features.extend(features)

    # Parse architecture output
    if "architecture" in artifacts:
        content = artifacts["architecture"]
        spec.source_stages.append("architecture")
        spec.tech_stack = _extract_list(content, "tech stack") or _extract_list(content, "technologies") or []
        arch_features = _extract_features(content)
        for f in arch_features:
            if not any(exist.name == f.name for exist in spec.features):
                spec.features.append(f)

    return spec


def _extract_section(content: str, section_name: str) -> Optional[str]:
    """Extract a section from markdown content."""
    lines = content.split("\n")
    in_section = False
    section_lines = []
    for line in lines:
        if section_name.lower() in line.lower() and ("#" in line or "**" in line):
            in_section = True
            continue
        if in_section:
            if line.startswith("#") or (line.startswith("**") and section_name.lower() not in line.lower()):
                break
            section_lines.append(line)
    return "\n".join(section_lines).strip() if section_lines else None


def _extract_list(content: str, list_name: str) -> List[str]:
    """Extract a bullet list from markdown content."""
    lines = content.split("\n")
    in_list = False
    items = []
    for line in lines:
        if list_name.lower() in line.lower() and ("#" in line or "**" in line):
            in_list = True
            continue
        if in_list:
            stripped = line.strip()
            if stripped.startswith("- ") or stripped.startswith("* "):
                items.append(stripped[2:].strip())
            elif stripped.startswith("#"):
                break
            elif not stripped:
                continue
    return items


def _extract_features(content: str) -> List[Feature]:
    """Extract feature definitions from markdown."""
    features = []
    lines = content.split("\n")
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- ") and ("feature" in stripped.lower() or "as a" in stripped.lower()):
            name = stripped[2:].split(":")[0].split("(")[0].strip()
            desc = stripped[2:].split(":")[1].strip() if ":" in stripped else name
            features.append(Feature(name=name, description=desc, priority="medium"))
    return features


def spec_to_dict(spec: DesignSpec) -> Dict[str, Any]:
    return {
        "project": spec.project,
        "product_name": spec.product_name,
        "vision": spec.vision,
        "target_users": spec.target_users,
        "features": [
            {"name": f.name, "description": f.description, "priority": f.priority, "status": f.status}
            for f in spec.features
        ],
        "tech_stack": spec.tech_stack,
        "design_principles": spec.design_principles,
        "success_metrics": spec.success_metrics,
        "constraints": spec.constraints,
        "version": spec.version,
        "created_at": spec.created_at,
        "updated_at": spec.updated_at,
        "source_stages": spec.source_stages,
    }


def save_spec(project_dir: str, spec: DesignSpec) -> str:
    """Save design spec to project directory."""
    spec_path = os.path.join(project_dir, "design-spec.json")
    with open(spec_path, "w", encoding="utf-8") as f:
        json.dump(spec_to_dict(spec), f, indent=2)
    return spec_path


def load_spec(project_dir: str) -> Optional[DesignSpec]:
    """Load design spec from project directory."""
    spec_path = os.path.join(project_dir, "design-spec.json")
    if not os.path.exists(spec_path):
        return None
    with open(spec_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return DesignSpec(
        project=data.get("project", ""),
        product_name=data.get("product_name", ""),
        vision=data.get("vision", ""),
        target_users=data.get("target_users", []),
        features=[Feature(**f) for f in data.get("features", [])],
        tech_stack=data.get("tech_stack", []),
        design_principles=data.get("design_principles", []),
        success_metrics=data.get("success_metrics", []),
        constraints=data.get("constraints", []),
        version=data.get("version", "1.0.0"),
        created_at=data.get("created_at", ""),
        updated_at=data.get("updated_at", ""),
        source_stages=data.get("source_stages", []),
    )


def render_markdown(spec: DesignSpec) -> str:
    """Render the spec to the canonical ``artifacts/1a/product-design-spec-output.md``.

    Deterministic (no LLM), so the stage artifact can be regenerated from the
    saved ``design-spec.json`` at any time.
    """
    lines: List[str] = []
    lines.append(f"# Product Design Spec - {spec.product_name or spec.project}")
    lines.append("")
    lines.append(f"_Version {spec.version} - generated {spec.updated_at or spec.created_at}_")
    lines.append("")

    def _bullets(title: str, items: List[str]) -> None:
        if items:
            lines.append(f"## {title}")
            lines.append("")
            for it in items:
                lines.append(f"- {it}")
            lines.append("")

    if spec.vision:
        lines.append("## Vision")
        lines.append("")
        lines.append(spec.vision.strip())
        lines.append("")
    _bullets("Target Users", spec.target_users)
    if spec.features:
        lines.append("## Features")
        lines.append("")
        lines.append("| Feature | Priority | Status | Description |")
        lines.append("| --- | --- | --- | --- |")
        for f in spec.features:
            lines.append(f"| {f.name} | {f.priority} | {f.status} | {f.description} |")
        lines.append("")
    _bullets("Tech Stack", spec.tech_stack)
    _bullets("Design Principles", spec.design_principles)
    _bullets("Success Metrics", spec.success_metrics)
    _bullets("Constraints", spec.constraints)
    if spec.source_stages:
        lines.append(f"_Source stages: {', '.join(spec.source_stages)}_")
        lines.append("")
    return "\n".join(lines)
