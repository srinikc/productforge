"""Artifact Store - manages artifacts produced by pipeline stages.

Provides structured artifact storage, metadata tracking, lookup, and validation.
Artifacts are stored under products/{project}/artifacts/{stage}/{agent}-output.md.
"""
import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime

from core import stage_paths
from typing import Any, Dict, List, Optional


@dataclass
class ArtifactMeta:
    """Metadata for a single artifact."""
    artifact_id: str
    stage: str
    agent: str
    path: str
    artifact_type: str  # code, design, architecture, test, docs, security
    content_hash: str
    size_bytes: int
    created_at: str
    version: int = 1
    tags: List[str] = field(default_factory=list)
    validation_status: str = "pending"  # pending, valid, invalid
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StageArtifacts:
    """All artifacts produced by a single pipeline stage."""
    stage_id: str
    artifacts: List[ArtifactMeta] = field(default_factory=list)
    total_tokens: int = 0
    total_cost: float = 0.0
    completed_at: Optional[str] = None


@dataclass
class ProjectArtifacts:
    """All artifacts for a project."""
    project: str
    stages: Dict[str, StageArtifacts] = field(default_factory=dict)
    total_artifacts: int = 0
    total_size_bytes: int = 0


ARTIFACT_TYPES = {
    "ideation": "docs",
    "design": "design",
    "architecture": "architecture",
    "implement": "code",
    "quality-security": "test",
    "release": "docs",
    "deploy": "docs",
}

ARTIFACT_TYPE_ORDER = ["docs", "design", "architecture", "code", "test", "security"]


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _current_run_id(project_dir: str) -> str:
    """Best-effort run id for stamping artifact metadata (never invented)."""
    try:
        from core.audit_trail import current_run_id
        return current_run_id(os.path.basename(project_dir))
    except Exception:
        return ""


def scan_project_artifacts(project_dir: str) -> ProjectArtifacts:
    """Scan a project directory and catalog all artifacts."""
    from core import stage_paths as _sp
    artifacts_dir = _sp.artifacts_root(project_dir)
    project_name = os.path.basename(project_dir)
    result = ProjectArtifacts(project=project_name)

    if not os.path.isdir(artifacts_dir):
        return result

    for stage_name in sorted(os.listdir(artifacts_dir)):
        stage_path = os.path.join(artifacts_dir, stage_name)
        if not os.path.isdir(stage_path):
            continue
        stage_id = _sp._sid_from_dirname(stage_name) or stage_name

        stage = StageArtifacts(stage_id=stage_id)

        for fname in sorted(os.listdir(stage_path)):
            if fname == "_stage.json":   # index metadata, not an artifact (3a)
                continue
            fpath = os.path.join(stage_path, fname)
            if not os.path.isfile(fpath):
                continue

            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                content_hash = _hash_content(content)
                size_bytes = os.path.getsize(fpath)
                created = datetime.fromtimestamp(os.path.getmtime(fpath)).isoformat()

                # Infer agent name from filename
                agent = fname.replace("-output.md", "").replace(".md", "")

                artifact = ArtifactMeta(
                    artifact_id=f"{stage_id}/{fname}",
                    stage=stage_id,
                    agent=agent,
                    path=fpath,
                    artifact_type=ARTIFACT_TYPES.get(stage_id, "docs"),
                    content_hash=content_hash,
                    size_bytes=size_bytes,
                    created_at=created,
                )
                stage.artifacts.append(artifact)
                result.total_artifacts += 1
                result.total_size_bytes += size_bytes
            except Exception:
                pass

        if stage.artifacts:
            stage.completed_at = stage.artifacts[-1].created_at
            result.stages[stage_id] = stage

    return result


def get_artifact_content(path: str) -> Optional[str]:
    """Read artifact content from disk."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def get_artifact_summary(project_dir: str) -> Dict[str, Any]:
    """Get a summary of all artifacts for the dashboard."""
    proj = scan_project_artifacts(project_dir)
    stages_summary = {}
    for sid, stage in proj.stages.items():
        stages_summary[sid] = {
            "artifact_count": len(stage.artifacts),
            "artifacts": [
                {
                    "id": a.artifact_id,
                    "agent": a.agent,
                    "type": a.artifact_type,
                    "hash": a.content_hash,
                    "size": a.size_bytes,
                    "created": a.created_at,
                }
                for a in stage.artifacts
            ],
            "completed_at": stage.completed_at,
        }
    return {
        "project": proj.project,
        "total_artifacts": proj.total_artifacts,
        "total_size_bytes": proj.total_size_bytes,
        "stages": stages_summary,
    }


def create_or_update_artifact(
    project_dir: str,
    stage: str,
    agent: str,
    content: str,
    artifact_type: str = "docs",
    tags: Optional[List[str]] = None,
) -> ArtifactMeta:
    """Create or update an artifact file and return its metadata."""
    from core import stage_paths as _sp
    artifacts_dir = _sp.stage_dir(project_dir, stage, create=True)

    fname = f"{agent}-output.md"
    fpath = os.path.join(artifacts_dir, fname)

    # Check if existing for versioning
    version = 1
    if os.path.exists(fpath):
        existing = get_artifact_content(fpath)
        if existing:
            version = 2  # Simple versioning: v1 or v2

    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)

    return ArtifactMeta(
        artifact_id=f"{stage}/{fname}",
        stage=stage,
        agent=agent,
        path=fpath,
        artifact_type=artifact_type,
        content_hash=_hash_content(content),
        size_bytes=len(content.encode("utf-8")),
        created_at=datetime.now().isoformat(),
        version=version,
        tags=tags or [],
        validation_status="pending",
        metadata={"run_id": _current_run_id(project_dir)},
    )


def validate_artifact_schema(content: str, artifact_type: str) -> Dict[str, Any]:
    """Basic validation of artifact content structure."""
    issues = []

    if not content or not content.strip():
        issues.append("Artifact is empty")
        return {"valid": False, "issues": issues}

    if artifact_type == "code":
        if "```" not in content and "def " not in content and "function " not in content:
            issues.append("No code blocks or function definitions found")
    elif artifact_type == "design":
        if "wireframe" not in content.lower() and "layout" not in content.lower() and "component" not in content.lower():
            issues.append("No design-related content found (wireframe/layout/component)")
    elif artifact_type == "architecture":
        if "diagram" not in content.lower() and "component" not in content.lower() and "service" not in content.lower():
            issues.append("No architecture-related content found")
    elif artifact_type == "test":
        if "test" not in content.lower() and "assert" not in content.lower():
            issues.append("No test-related content found")
    elif artifact_type == "docs":
        if len(content.strip()) < 50:
            issues.append("Documentation content seems too short")

    return {"valid": len(issues) == 0, "issues": issues}


def get_artifacts_for_context(project_dir: str, up_to_stage: str) -> Dict[str, str]:
    """Get artifacts from stages BEFORE ``up_to_stage`` for context building.

    Uses the pipeline display order when available (falling back to the legacy
    named order), and reads stage dirs through stage_paths (either naming).
    """
    proj = scan_project_artifacts(project_dir)
    order: List[str] = []
    for sid, _d in stage_paths.iter_stages(project_dir):
        if sid not in order:
            order.append(sid)
    if not order:
        order = ["ideation", "design", "architecture", "implement",
                 "quality-security", "release"]
    result = {}
    for stage_id in order:
        if str(stage_id) == str(up_to_stage):
            break
        stage = proj.stages.get(stage_id)
        if stage:
            for artifact in stage.artifacts:
                content = get_artifact_content(artifact.path)
                if content:
                    result[f"{stage_id}_{artifact.agent}"] = content
    return result
