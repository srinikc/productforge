"""Single-writer facade for `project.json` (the project descriptor / truth).

`project.json` is read by ~30 modules but must be written from one place. All writers
(portfolio create, run_pipeline create/update, pr_gate QA override, feature flags) go
through this module; everyone else keeps reading the file directly.

Layout (per project): products/<project>/project.json
"""
import json
import os
import time
from typing import Any, Dict, Optional

_DEFAULT_PRODUCTS = "products"
_DEEP_SECTIONS = ("qa", "vcs", "deploy", "budget", "signing", "test", "feature_flags")


def path(project: str, products_dir: str = _DEFAULT_PRODUCTS) -> str:
    return os.path.join(products_dir, project, "project.json")


def _lock(project_dir: str):
    try:
        os.makedirs(project_dir, exist_ok=True)
        lp = os.path.join(project_dir, ".project.lock")
        for _ in range(50):
            try:
                fd = os.open(lp, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                return lp
            except FileExistsError:
                time.sleep(0.1)
    except Exception:
        pass
    return None


def _unlock(lp):
    try:
        if lp:
            os.remove(lp)
    except Exception:
        pass


def load(project: str, products_dir: str = _DEFAULT_PRODUCTS) -> Dict:
    """Read the project descriptor ({} when missing/invalid)."""
    try:
        with open(path(project, products_dir), "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def save(project: str, cfg: Dict, products_dir: str = _DEFAULT_PRODUCTS) -> Dict:
    """Atomic write (use sparingly; prefer update/update_section)."""
    p = path(project, products_dir)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg or {}, f, indent=2, ensure_ascii=False)
    os.replace(tmp, p)
    return cfg or {}


def _mutate(project: str, fn, products_dir: str = _DEFAULT_PRODUCTS) -> Dict:
    p = path(project, products_dir)
    lp = _lock(os.path.dirname(p))
    try:
        cfg = load(project, products_dir)
        before = json.dumps(cfg, sort_keys=True)
        fn(cfg)
        if json.dumps(cfg, sort_keys=True) != before:
            save(project, cfg, products_dir)
        return cfg
    finally:
        _unlock(lp)


def ensure(project: str, products_dir: str = _DEFAULT_PRODUCTS, **defaults) -> Dict:
    """Get-or-create; only fills missing keys (never overwrites)."""
    def _fn(cfg):
        cfg.setdefault("name", project)
        for k, v in defaults.items():
            if v not in (None, ""):
                cfg.setdefault(k, v)
    return _mutate(project, _fn, products_dir)


def update(project: str, products_dir: str = _DEFAULT_PRODUCTS, **fields) -> Dict:
    """Shallow merge of top-level fields."""
    def _fn(cfg):
        cfg.setdefault("name", project)
        cfg.update({k: v for k, v in fields.items() if v is not None})
    return _mutate(project, _fn, products_dir)


def update_section(project: str, section: str, values: Dict,
                   products_dir: str = _DEFAULT_PRODUCTS) -> Dict:
    """Deep-merge values into one section (e.g. qa override, vcs, deploy)."""
    def _fn(cfg):
        cur = cfg.get(section)
        if not isinstance(cur, dict):
            cur = {}
        cur.update(values or {})
        cfg[section] = cur
    return _mutate(project, _fn, products_dir)


def read_section(project: str, section: str, products_dir: str = _DEFAULT_PRODUCTS) -> Dict:
    cfg = load(project, products_dir)
    val = cfg.get(section)
    return val if isinstance(val, dict) else {}
