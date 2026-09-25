"""Single source of truth for repository paths (BI-0204).

`ROOT` is the absolute Product Forge root -- the directory that contains
``core/``, ``config/``, ``data/``, ``products/`` and friends. It is computed
here, and ONLY here. Every other module imports from this file:

    from core.paths import ROOT, CONFIG_DIR, DATA_DIR, PRODUCTS_DIR

Rules (enforced by ``scripts/dev/wired_audit.py:paths_audit``):
  * never re-derive the root with ``os.path.dirname(...)`` chains elsewhere;
  * never open paths relative to the current working directory (CWD);
  * derive everything from ``ROOT`` so a command behaves identically from any CWD.

Override the root with the ``PF_ROOT`` environment variable (used by tests and
non-standard installs); otherwise it is inferred from this file's location.
"""
import os
from pathlib import Path

__all__ = [
    "ROOT", "ROOT_STR",
    "CORE_DIR", "DASHBOARD_DIR", "SCRIPTS_DIR", "CONFIG_DIR", "DATA_DIR",
    "DOCS_DIR", "AGENTS_DIR", "PRODUCTS_DIR", "TEMPLATES_DIR",
    "PIPELINE_TEMPLATES_DIR", "OPENCODE_DIR", "OPENCODE_AGENT_DIR",
    "FORGE_HOME", "FORGE_DATA_DIR", "PIPELINE_DEFINITION",
    "path", "cfg", "data", "products", "project_dir", "docs", "agents",
]

# --- the one and only root computation -------------------------------------
_ENV_ROOT = os.environ.get("PF_ROOT")
if _ENV_ROOT:
    ROOT: Path = Path(_ENV_ROOT).expanduser().resolve()
else:
    # core/paths.py -> parents[0] = core/, parents[1] = repo root
    ROOT = Path(__file__).resolve().parents[1]

ROOT_STR: str = str(ROOT)

# --- derived directories (all absolute, all from ROOT) ----------------------
CORE_DIR = ROOT / "core"
DASHBOARD_DIR = ROOT / "dashboard"
SCRIPTS_DIR = ROOT / "scripts"
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
AGENTS_DIR = ROOT / "agents"
PRODUCTS_DIR = ROOT / "products"
TEMPLATES_DIR = ROOT / "templates"
PIPELINE_TEMPLATES_DIR = ROOT / "pipeline_templates"
OPENCODE_DIR = ROOT / ".opencode"
OPENCODE_AGENT_DIR = OPENCODE_DIR / "agent"
PIPELINE_DEFINITION = ROOT / "pipeline-definition.json"

# --- forge scope aliases (kept for readability at call sites) ---------------
FORGE_HOME = ROOT
FORGE_DATA_DIR = DATA_DIR


# --- helpers: keep call sites terse and CWD-free ----------------------------
def path(*parts) -> Path:
    """Absolute path under ROOT, e.g. ``path("config", "model-tier.json")``."""
    return ROOT.joinpath(*parts)


def cfg(*parts) -> Path:
    """Absolute path under ``config/``."""
    return CONFIG_DIR.joinpath(*parts)


def data(*parts) -> Path:
    """Absolute path under ``data/`` (forge runtime state)."""
    return DATA_DIR.joinpath(*parts)


def products(project: str = "", *parts) -> Path:
    """Absolute path under ``products/`` (all projects, or one project)."""
    base = PRODUCTS_DIR / project if project else PRODUCTS_DIR
    return base.joinpath(*parts)


def project_dir(project: str, *parts) -> Path:
    """Absolute path for one project root (alias of ``products(project, ...)``)."""
    return products(project, *parts)


def docs(*parts) -> Path:
    """Absolute path under ``docs/``."""
    return DOCS_DIR.joinpath(*parts)


def agents(*parts) -> Path:
    """Absolute path under ``agents/`` (agent definitions / cards)."""
    return AGENTS_DIR.joinpath(*parts)
