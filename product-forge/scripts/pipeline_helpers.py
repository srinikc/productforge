"""
Pipeline Helpers - System-level utilities for the Product Forge pipeline.

These helpers are GENERAL (not project-specific) and provide:
- Default project resolution (from index.json)
- System schema management (product_completion, etc.)
- Auto-migration for existing projects
- Valid project enumeration

This is the system-level foundation that any project can use.
"""
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
from pathlib import Path
from datetime import datetime
from typing import Optional


# System-level files (live under products/.pipeline/)
SYSTEM_DIR_NAME = ".pipeline"
SYSTEM_CONFIG_FILE = "system_config.json"


def get_system_dir(products_dir: Path) -> Path:
    """Get the system directory: products/.pipeline/"""
    return products_dir / SYSTEM_DIR_NAME


def load_index(products_dir: Path) -> dict:
    """Load products/index.json, creating if missing."""
    index_file = products_dir / "index.json"
    if not index_file.exists():
        return {"products": []}
    try:
        return json.loads(index_file.read_text())
    except (json.JSONDecodeError, OSError):
        return {"products": []}


def save_index(products_dir: Path, data: dict) -> None:
    """Save products/index.json."""
    index_file = products_dir / "index.json"
    index_file.write_text(json.dumps(data, indent=2))


def get_all_projects(products_dir: Path) -> list[str]:
    """Get list of all product names from index.json (no hardcoding)."""
    data = load_index(products_dir)
    return data.get("products", [])


def get_default_project(products_dir: Path) -> Optional[str]:
    """
    Get the default project to use when none is specified.

    Logic:
    - If exactly 1 project exists, return it
    - If 0 or >1 projects, return None (caller must specify)

    This is GENERAL - no hardcoded project names.
    """
    projects = get_all_projects(products_dir)
    if len(projects) == 1:
        return projects[0]
    return None


def resolve_project(products_dir: Path, requested: Optional[str] = None) -> Optional[str]:
    """
    Resolve which project to use, with clear error messages.

    Args:
        products_dir: Path to products/ directory
        requested: Project name from CLI arg, or None for default

    Returns:
        Project name, or None if not resolvable (with error printed)
    """
    products = get_all_projects(products_dir)

    if not products:
        print("ERROR: No products found.")
        print("Create one with: python pipeline.py new <idea>")
        return None

    if requested:
        if requested in products:
            return requested
        print(f"ERROR: Project '{requested}' not found.")
        print(f"Available projects: {', '.join(products)}")
        return None

    # Use default
    if len(products) == 1:
        return products[0]

    print("ERROR: Multiple projects exist. Please specify which one:")
    for p in products:
        print(f"  - {p}")
    print("\nUsage: python pipeline.py <command> <project>")
    return None


def get_system_config(products_dir: Path) -> dict:
    """Load system-level config (product_completion schema, etc.)."""
    system_dir = get_system_dir(products_dir)
    config_file = system_dir / SYSTEM_CONFIG_FILE
    if not config_file.exists():
        return _get_default_system_config()
    try:
        return json.loads(config_file.read_text())
    except (json.JSONDecodeError, OSError):
        return _get_default_system_config()


def save_system_config(products_dir: Path, config: dict) -> None:
    """Save system-level config."""
    system_dir = get_system_dir(products_dir)
    system_dir.mkdir(parents=True, exist_ok=True)
    config_file = system_dir / SYSTEM_CONFIG_FILE
    config_file.write_text(json.dumps(config, indent=2, default=str))


def _get_default_system_config() -> dict:
    """Default system config with product_completion schema template."""
    return {
        "version": "1.0",
        "schema_version": "1.0",
        "created_at": datetime.utcnow().isoformat(),
        "product_completion_schema": {
            "total_features": 0,
            "completed": 0,
            "remaining": 0,
            "percent_complete": 0.0,
            "phases": {},
            "completion_definition": "All features implemented and accepted by user.",
            "mvp_decision_log": {
                "decided_by": "unknown",
                "explicit_user_approval": False,
                "rationale": "Not yet decided",
            }
        },
        "phases_template": {
            "mvp": {
                "status": "not_started",
                "label": "MVP (Phase 1)",
                "features": [],
                "completed_features": [],
                "trigger": "user_signal",
                "blocked_by": None,
            },
            "phase_2": {
                "status": "not_started",
                "label": "Phase 2",
                "features": [],
                "completed_features": [],
                "trigger": "user_signal",
                "blocked_by": "mvp",
            },
            "phase_3": {
                "status": "not_started",
                "label": "Phase 3",
                "features": [],
                "completed_features": [],
                "trigger": "user_signal",
                "blocked_by": "phase_2",
            },
            "phase_4": {
                "status": "not_started",
                "label": "Phase 4",
                "features": [],
                "completed_features": [],
                "trigger": "user_signal",
                "blocked_by": "phase_3",
            },
            "phase_5": {
                "status": "not_started",
                "label": "Phase 5",
                "features": [],
                "completed_features": [],
                "trigger": "user_signal",
                "blocked_by": "phase_4",
            },
        },
    }


def initialize_product_completion(products_dir: Path, project: str) -> dict:
    """
    Initialize product_completion for a new project.
    Uses system-level schema, not hardcoded values.
    """
    project_dir = products_dir / project
    pipeline_file = project_dir / "pipeline.json"

    if not pipeline_file.exists():
        return {}

    try:
        config = json.loads(pipeline_file.read_text())
    except (json.JSONDecodeError, OSError):
        return {}

    # Get system schema
    system_config = get_system_config(products_dir)
    schema = system_config.get("product_completion_schema", {})
    template = system_config.get("phases_template", {})

    # Initialize product_completion using schema
    config["product_completion"] = {
        "total_features": schema.get("total_features", 0),
        "completed": 0,
        "remaining": 0,
        "percent_complete": 0.0,
        "phases": {k: dict(v, features=[], completed_features=[]) for k, v in template.items()},
        "completion_definition": schema.get(
            "completion_definition",
            "All features implemented and accepted by user."
        ),
        "mvp_decision_log": {
            "decided_by": "TBD (ideation stage)",
            "decided_at": datetime.utcnow().isoformat(),
            "explicit_user_approval": False,
            "rationale": "Pending ideation decision",
        },
    }

    pipeline_file.write_text(json.dumps(config, indent=2, default=str))
    return config["product_completion"]


def ensure_product_completion(products_dir: Path, project: str) -> dict:
    """
    Ensure product_completion exists in pipeline.json.
    If missing, initialize from system schema.
    """
    project_dir = products_dir / project
    pipeline_file = project_dir / "pipeline.json"

    if not pipeline_file.exists():
        return {}

    try:
        config = json.loads(pipeline_file.read_text())
    except (json.JSONDecodeError, OSError):
        return {}

    if "product_completion" not in config:
        # Initialize using system schema
        return initialize_product_completion(products_dir, project)

    return config["product_completion"]


def migrate_all_projects(products_dir: Path) -> dict:
    """
    Migrate all existing projects to add product_completion if missing.
    This is a one-time migration for backward compatibility.
    """
    products = get_all_projects(products_dir)
    results = {"migrated": [], "skipped": [], "errors": []}

    for project in products:
        try:
            completion = ensure_product_completion(products_dir, project)
            if completion:
                # Check if it was just added
                project_dir = products_dir / project
                pipeline_file = project_dir / "pipeline.json"
                config = json.loads(pipeline_file.read_text())
                if config.get("product_completion", {}).get("total_features", 0) == 0:
                    # Newly initialized
                    results["migrated"].append(project)
                else:
                    results["skipped"].append(project)
        except Exception as e:
            results["errors"].append({"project": project, "error": str(e)})

    return results


def get_products_dir() -> Path:
    """Get the products directory (project root + products/)."""
    return _PF_ROOT / "products"


def get_current_project() -> Optional[str]:
    """
    Get the project currently being worked on by the agent.
    
    Used by agents (like Fix, Validate) to know which product they're handling
    without hardcoding names.
    
    Reads from (in order of priority):
    1. PIPELINE_PROJECT env variable
    2. Current working directory (if inside products/<name>/)
    3. products/index.json (if only 1 project)
    4. None (caller must specify)
    """
    import os
    
    # 1. Environment variable (set by orchestrator)
    env_project = os.environ.get("PIPELINE_PROJECT")
    if env_project:
        return env_project
    
    # 2. Current working directory
    cwd = Path.cwd()
    products_dir = get_products_dir()
    try:
        rel = cwd.relative_to(products_dir)
        parts = rel.parts
        if parts and parts[0] not in (".pipeline",):
            return parts[0]
    except ValueError:
        pass
    
    # 3. Default (single project)
    return get_default_project(get_products_dir())
