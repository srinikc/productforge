"""pipeline.json compatibility layer (BI-0005, option 3: split + retire).

Truths:
  config  -> products/<project>/project.json        (writer: core/project_store.py)
  state   -> products/<project>/pipeline-state.json (writer: pipeline_executor)

`pipeline.json` is NOT a truth any more. It is kept only as a **derived projection**
(config + state) so the ~20 legacy readers keep working until they are migrated.

  read(project)  -> unified view (truths first, legacy file as fallback)
  sync(project)  -> regenerate the derived pipeline.json projection
"""
import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

_DEFAULT_PRODUCTS = "products"


def _path(project: str, products_dir: str = _DEFAULT_PRODUCTS) -> str:
    return os.path.join(products_dir, project, "pipeline.json")


def _read_json(p: str) -> Dict:
    try:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def read(project: str, products_dir: str = _DEFAULT_PRODUCTS) -> Dict:
    """Unified pipeline view: config (project.json) + state (pipeline-state.json).

    Falls back to the legacy pipeline.json when the truth files are absent.
    """
    pdir = os.path.join(products_dir, project)
    cfg = _read_json(os.path.join(pdir, "project.json"))
    state = _read_json(os.path.join(pdir, "pipeline-state.json"))
    legacy = _read_json(_path(project, products_dir))
    out: Dict[str, Any] = {}
    out.update({k: v for k, v in legacy.items() if k not in ("generated", "derived_from")})
    out.update({k: v for k, v in cfg.items() if v not in (None, "", {}, [])})
    out.update({k: v for k, v in state.items() if v not in (None, "", {}, [])})
    if cfg or state:
        out["_derived"] = True
    return out


def sync(project: str, products_dir: str = _DEFAULT_PRODUCTS) -> Dict:
    """Regenerate the derived pipeline.json projection from project.json + pipeline-state.json."""
    pdir = os.path.join(products_dir, project)
    cfg = _read_json(os.path.join(pdir, "project.json"))
    state = _read_json(os.path.join(pdir, "pipeline-state.json"))
    if not (cfg or state):
        return {}
    projection: Dict[str, Any] = {}
    # config-derived
    for k in ("name", "idea", "description", "model_tier", "auto_mode", "auto_approve",
              "budget", "vcs", "qa", "tech_stack_hints", "max_total_time"):
        if k in cfg:
            projection[k] = cfg[k]
    # state-derived
    for k in ("project", "pipeline_id", "current_stage", "completed_stages",
              "total_stages", "pipeline_complete", "total_tokens", "total_cost",
              "started_at", "updated_at", "current_iteration", "stages"):
        if k in state:
            projection[k] = state[k]
    projection["generated"] = True
    projection["derived_from"] = ["project.json", "pipeline-state.json"]
    projection["generated_at"] = datetime.now().isoformat()
    p = _path(project, products_dir)
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(projection, f, indent=2, ensure_ascii=False)
        os.replace(tmp, p)
    except Exception:
        pass
    return projection
