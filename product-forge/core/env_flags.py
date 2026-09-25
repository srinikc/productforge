"""Central environment-flag registry — every PIPELINE_*/MODEL_*/etc. switch in one place.

Why: ~78 `os.getenv(...)` calls were scattered with no single source of truth (default,
purpose, owner). This documents and resolves them uniformly, so behaviour is
discoverable and testable.

`get(name)` returns the resolved value (env or declared default) and `docs()` lists all.
Undeclared env vars still work (get() falls through to os.environ) but `undeclared()`
helps find drift.
"""
import json
import os
from typing import Dict, List, Optional

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG = os.path.join(REPO_ROOT, "config", "env-flags.json")

_DEFAULT_FLAGS = {
    "PIPELINE_INTERACTIVE": {"default": "", "purpose": "force interactive prompts on/off", "owner": "core/interactive.py"},
    "PIPELINE_PANEL_MODEL": {"default": "mimo-v2.6-flash", "purpose": "model for the 360 discovery panel", "owner": "core/pipeline_executor.py"},
    "PIPELINE_REANALYZE": {"default": "0", "purpose": "re-analyze panel recommendations on rerun", "owner": "core/pipeline_executor.py"},
    "PIPELINE_PANEL_ONE_BY_ONE": {"default": "0", "purpose": "legacy per-question discovery ask", "owner": "core/pipeline_executor.py"},
    "PIPELINE_PROMPT_TIMEOUT": {"default": "3600", "purpose": "max seconds to wait for a human prompt", "owner": "core/pipeline_executor.py"},
    "PIPELINE_ALLOW_UNGUARDED": {"default": "0", "purpose": "override the run-lock bypass guard", "owner": "core/pipeline_executor.py"},
    "PIPELINE_PANEL_TIMEOUT": {"default": "300", "purpose": "discovery panel ask timeout", "owner": "core/pipeline_executor.py"},
    "MODEL_FIT_TIMEOUT": {"default": "300", "purpose": "model-fit preflight wait", "owner": "core/pipeline_executor.py"},
}


def load(path: Optional[str] = None) -> Dict:
    cfg = dict(_DEFAULT_FLAGS)
    try:
        with open(path or _CONFIG, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        if isinstance(data.get("flags"), dict):
            cfg.update(data["flags"])
    except Exception:
        pass
    return cfg


def get(name: str, default: Optional[str] = None) -> Optional[str]:
    if name in os.environ:
        return os.environ[name]
    flag = load().get(name)
    if flag is not None:
        return flag.get("default", default)
    return default


def docs() -> List[Dict]:
    return [{"name": k, **v} for k, v in sorted(load().items())]
