"""Canonical log router — the single place that decides WHERE logs live and their names.

Convention (config/log-conventions.json):
  products/<project>/logs/<run_id>/<stage>-<agent>.log   per-agent (run-scoped)
  products/<project>/logs/<run_id>/<run_id>-pipeline.log overall, per run
  product-forge/logs/pipeline-backend.log                the pipeline backend itself
  dashboard/logs/dashboard.log                           the dashboard (when built)

Agents/                                                                                                                                                                       say must be attributable:
every line is `ts | level | run_id | stage | agent | event | message`, and each run
directory carries an INDEX.json so the UI/API can list/stream per agent.

One writer per file: this module owns log-file creation; callers only append events.
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
import os
import re
from datetime import datetime
from typing import Dict, Optional

REPO_ROOT = str(_PF_ROOT)
_CONFIG = os.path.join(REPO_ROOT, "config", "log-conventions.json")

_DEFAULT = {
    "layout": {"product_runs": "products/<project>/logs/<run_id>/",
               "pipeline_backend": "product-forge/logs/",
               "dashboard": "dashboard/logs/"},
    "naming": {"per_agent": "<stage>-<agent>.log",
               "run_overall": "<run_id>-pipeline.log",
               "backend": "pipeline-backend.log",
               "dashboard": "dashboard.log",
               "index": "INDEX.json"},
    "rotation": {"max_bytes": 5242880, "backup_count": 5, "keep_runs": 20},
}


def config(path: Optional[str] = None) -> Dict:
    cfg = json.loads(json.dumps(_DEFAULT))
    try:
        with open(path or _CONFIG, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        for k in ("layout", "naming", "rotation"):
            if isinstance(data.get(k), dict):
                cfg[k].update(data[k])
    except Exception:
        pass
    return cfg


def _san(name: str) -> str:
    s = str(name or "").strip().lower()
    s = re.sub(r"[ /\\:]+", "-", s)
    s = re.sub(r"[^a-z0-9\-_.]+", "", s)
    return s or "unknown"


def run_dir(project_dir: str, run_id: str = "") -> str:
    """products/<project>/logs/<run_id>/ (created)."""
    rid = _san(run_id) or "run-unknown"
    d = os.path.join(project_dir, "logs", rid)
    os.makedirs(d, exist_ok=True)
    return d


def agent_log_path(project_dir: str, stage_id: str, agent_id: str, run_id: str = "") -> str:
    """<stage>-<agent>.log inside the run's log dir."""
    name = config()["naming"]["per_agent"]
    fn = name.replace("<stage>", _san(stage_id)).replace("<agent>", _san(agent_id))
    return os.path.join(run_dir(project_dir, run_id), fn)


def run_log_path(project_dir: str, run_id: str = "") -> str:
    name = config()["naming"]["run_overall"].replace("<run_id>", _san(run_id) or "run-unknown")
    return os.path.join(run_dir(project_dir, run_id), name)


def backend_dir() -> str:
    d = os.path.join(REPO_ROOT, "data", str(config()["layout"]["pipeline_backend"]).split("/")[-2])
    os.makedirs(d, exist_ok=True)
    return d


def backend_log_path() -> str:
    d = os.path.join(REPO_ROOT, "data", "logs")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, config()["naming"]["backend"])


def dashboard_log_path() -> str:
    d = os.path.join(REPO_ROOT, "dashboard", "logs")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, config()["naming"]["dashboard"])


def log_event(path: str, *, run_id: str = "", stage: str = "", agent: str = "",
              event: str = "", message: str = "", level: str = "INFO") -> None:
    """Append one standard line. Best-effort (never raises)."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        ts = datetime.now().isoformat(timespec="seconds")
        msg = " ".join(str(message or "").split())
        line = f"{ts} | {level.upper()} | {run_id or '-'} | {stage or '-'} | {agent or '-'} | {event or '-'} | {msg}\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def update_index(project_dir: str, run_id: str = "", extra: Optional[Dict] = None) -> None:
    """Refresh logs/<run_id>/INDEX.json (which agents logged, sizes)."""
    try:
        d = run_dir(project_dir, run_id)
        files = []
        for fn in sorted(os.listdir(d)):
            if fn == config()["naming"]["index"] or not fn.endswith(".log"):
                continue
            p = os.path.join(d, fn)
            files.append({"file": fn, "size": os.path.getsize(p),
                          "updated": datetime.fromtimestamp(os.path.getmtime(p)).isoformat()})
        idx = {"run_id": _san(run_id) or "run-unknown",
               "generated_at": datetime.now().isoformat(), "logs": files}
        if extra:
            idx.update(extra)
        with open(os.path.join(d, config()["naming"]["index"]), "w",
                  encoding="utf-8", newline="\n") as f:
            json.dump(idx, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
