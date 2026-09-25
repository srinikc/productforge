"""
Test Framework bridge (4.1).

Reads test-framework/config/test-suites.yaml and maps a pipeline stage to a
test mode + categories, so verification runs the right suite per phase
(smoke / feature / nfr / packaging) instead of always running everything.

Pure selection logic; execution is done by core.verification_runner.
"""
import os
from typing import Dict, List, Optional

_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "test-framework", "config", "test-suites.yaml",
)

# pipeline stage -> test mode (defaults to per-phase feature suite)
STAGE_MODE = {
    "5": "nfr",
    "5-vqa": "nfr",
    "6": "nfr",
    "7": "packaging",
}
DEFAULT_MODE = "feature"


def load_config(path: Optional[str] = None) -> Dict:
    p = path or _CONFIG_PATH
    if not os.path.exists(p):
        return {}
    try:
        import yaml
        with open(p, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def mode_for_stage(stage_id: Optional[str]) -> str:
    if not stage_id:
        return DEFAULT_MODE
    return STAGE_MODE.get(str(stage_id), DEFAULT_MODE)


def categories_for_mode(mode: str, config: Optional[Dict] = None) -> List[str]:
    cfg = config if config is not None else load_config()
    modes = (cfg.get("test_modes") or {})
    cats = (modes.get(mode) or {}).get("categories")
    if not cats:
        return ["unit", "api", "integration", "e2e"]
    if cats == ["all"]:
        allcats = (cfg.get("categories") or {})
        return list(allcats.keys()) or ["unit", "api", "integration", "e2e"]
    return list(cats)


def select_for_stage(stage_id: Optional[str]) -> Dict:
    cfg = load_config()
    mode = mode_for_stage(stage_id)
    return {"mode": mode, "categories": categories_for_mode(mode, cfg)}


def selected_test_paths(project_dir: str, categories: List[str]) -> List[str]:
    """Conventional per-category test directories that actually exist."""
    found = []
    for c in categories:
        for cand in (os.path.join("tests", c), os.path.join("test", c), c):
            p = os.path.join(project_dir, cand)
            if os.path.isdir(p):
                found.append(cand)
    return found
