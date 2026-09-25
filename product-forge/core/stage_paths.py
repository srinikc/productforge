"""Single source for artifact stage directories + human-readable stage names.

Why: the `artifacts/<stage>` layout was constructed inline in ~10 modules, so a
naming change (e.g. `artifacts/1/` -> `artifacts/1 - Design/`) could not be made
safely. Everything now goes through this module.

Naming is config-driven (`config/artifact-paths.json`):
  {"naming": "stage-name" | "id", "separator": " - "}
`stage-name` gives human-readable dirs like `1 - Design`; `id` keeps `1`.

`find_stage_dir()` / `iter_stages()` tolerate BOTH namings, so a project that has
not been migrated still resolves. `migrate_project()` renames in place.
"""
import json
import os
import re
from typing import Dict, List, Optional, Tuple

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG = os.path.join(REPO_ROOT, "config", "artifact-paths.json")
_PIPELINE = os.path.join(REPO_ROOT, "pipeline-definition.json")
_DEFAULT = {"naming": "stage-name", "separator": " - "}

_cache: Dict[str, object] = {}


def config(path: Optional[str] = None) -> Dict:
    if path is None and "cfg" in _cache:
        return _cache["cfg"]
    cfg = dict(_DEFAULT)
    try:
        with open(path or _CONFIG, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        if isinstance(data, dict):
            cfg.update(data)
    except Exception:
        pass
    if path is None:
        _cache["cfg"] = cfg
    return cfg


def _stage_defs() -> Dict[str, Dict]:
    if "defs" in _cache:
        return _cache["defs"]
    defs: Dict[str, Dict] = {}
    try:
        with open(_PIPELINE, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        for sid, st in (data.get("stages") or {}).items():
            if isinstance(st, dict):
                defs[str(sid)] = st
    except Exception:
        pass
    _cache["defs"] = defs
    return defs


def stage_name(stage_id: str) -> str:
    """The stage's display name (e.g. ``Design``)."""
    return str((_stage_defs().get(str(stage_id)) or {}).get("name") or "").strip()


def stage_display(stage_id: str) -> str:
    """Human label ``1 - Design`` (falls back to the id)."""
    sid = str(stage_id)
    name = stage_name(sid)
    sep = str(config().get("separator") or " - ")
    return f"{sid}{sep}{name}" if name else sid


def _sanitize(name: str) -> str:
    """Filesystem-safe dir name (drop path-illegal chars; keep spaces/dashes)."""
    name = re.sub(r'[<>:"/\\|?*]', "", name or "").strip().rstrip(".")
    return name


def stage_dirname(stage_id: str) -> str:
    """Directory name for a stage per config (``1 - Design`` or ``1``)."""
    sid = str(stage_id)
    if str(config().get("naming") or "id") == "stage-name":
        return _sanitize(stage_display(sid))
    return sid


def _alt_dirname(stage_id: str) -> str:
    """The OTHER possible dir name (for tolerance when reading)."""
    sid = str(stage_id)
    return sid if stage_dirname(sid) != sid else _sanitize(stage_display(sid))


def stage_dir(project_dir: str, stage_id: str, create: bool = False) -> str:
    """Canonical artifact dir for a stage (per config naming)."""
    p = os.path.join(project_dir, "artifacts", stage_dirname(stage_id))
    if create:
        os.makedirs(p, exist_ok=True)
    return p


def find_stage_dir(project_dir: str, stage_id: str, create: bool = False) -> str:
    """Existing dir for a stage, tolerating either naming (else canonical)."""
    base = os.path.join(project_dir, "artifacts")
    for name in (stage_dirname(stage_id), _alt_dirname(stage_id)):
        p = os.path.join(base, name)
        if os.path.isdir(p):
            return p
    return stage_dir(project_dir, stage_id, create=create)


def artifacts_root(project_dir: str, create: bool = False) -> str:
    p = os.path.join(project_dir, "artifacts")
    if create:
        os.makedirs(p, exist_ok=True)
    return p


# ── Other canonical project dirs (one owner so paths are never hand-built) ──

def docs_dir(project_dir: str, create: bool = False) -> str:
    p = os.path.join(project_dir, "docs")
    if create:
        os.makedirs(p, exist_ok=True)
    return p


def approvals_dir(project_dir: str, stage_id: str = "", create: bool = False) -> str:
    p = os.path.join(project_dir, "approvals", str(stage_id)) if stage_id \
        else os.path.join(project_dir, "approvals")
    if create:
        os.makedirs(p, exist_ok=True)
    return p


def backlog_dir(project_dir: str, create: bool = False) -> str:
    p = os.path.join(project_dir, "backlog")
    if create:
        os.makedirs(p, exist_ok=True)
    return p


def logs_dir(project_dir: str, run_id: str = "", create: bool = False) -> str:
    p = os.path.join(project_dir, "logs", str(run_id)) if run_id \
        else os.path.join(project_dir, "logs")
    if create:
        os.makedirs(p, exist_ok=True)
    return p


def _sid_from_dirname(name: str) -> str:
    """Recover the stage id from a dir name (``1 - Design`` -> ``1``)."""
    m = re.match(r"^\s*([0-9]+[a-z]?(?:-[0-9a-z]+)?)\b", name or "")
    return m.group(1) if m else ""


def iter_stages(project_dir: str) -> List[Tuple[str, str]]:
    """[(stage_id, dir_path)] for every stage dir present (both namings)."""
    base = os.path.join(project_dir, "artifacts")
    out: List[Tuple[str, str]] = []
    if not os.path.isdir(base):
        return out
    for name in sorted(os.listdir(base)):
        p = os.path.join(base, name)
        if not os.path.isdir(p):
            continue
        sid = _sid_from_dirname(name)
        if sid:
            out.append((sid, p))
    return out


def migrate_project(project_dir: str) -> List[Tuple[str, str]]:
    """Rename stage dirs to the configured naming. Returns [(old, new)] moved."""
    base = os.path.join(project_dir, "artifacts")
    moved: List[Tuple[str, str]] = []
    if not os.path.isdir(base):
        return moved
    for name in sorted(os.listdir(base)):
        old = os.path.join(base, name)
        if not os.path.isdir(old):
            continue
        sid = _sid_from_dirname(name)
        if not sid:
            continue
        want = stage_dirname(sid)
        if name == want:
            continue
        new = os.path.join(base, want)
        if os.path.exists(new):
            # merge: move files that do not collide
            for f in os.listdir(old):
                src, dst = os.path.join(old, f), os.path.join(new, f)
                if not os.path.exists(dst):
                    os.replace(src, dst)
            try:
                os.rmdir(old)
            except OSError:
                pass
        else:
            os.replace(old, new)
        moved.append((name, want))
    return moved


# ── Human-readable index (3a): per-stage _stage.json + artifacts/INDEX.md ──

def _agent_role(agent_id: str) -> str:
    try:
        with open(os.path.join(REPO_ROOT, "agents", f"{agent_id}.agent.json"),
                  encoding="utf-8") as f:
            c = json.load(f)
        return (c.get("description") or c.get("name") or "").strip()
    except Exception:
        return ""


def write_stage_meta(project_dir: str, stage_id: str) -> str:
    """Write ``<stage_dir>/_stage.json`` (stage display name + agents + artifacts)."""
    d = find_stage_dir(project_dir, stage_id, create=True)
    st = _stage_defs().get(str(stage_id)) or {}
    agents = [{"id": a, "role": _agent_role(a)} for a in (st.get("ideal_flow") or [])]
    files = sorted(f for f in os.listdir(d) if os.path.isfile(os.path.join(d, f)))
    meta = {
        "stage": str(stage_id),
        "display": stage_display(stage_id),
        "name": stage_name(stage_id),
        "phase": st.get("phase", ""),
        "display_id": st.get("display_id", ""),
        "agents": agents,
        "artifacts": files,
    }
    p = os.path.join(d, "_stage.json")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    return p


def write_index(project_dir: str) -> str:
    """Write ``artifacts/INDEX.md`` — human index of stages, agents, artifacts."""
    base = artifacts_root(project_dir, create=True)
    lines = ["# Artifacts index", "",
             "> Generated by `core.stage_paths.write_index`. Do not hand-edit.", ""]
    for sid, d in iter_stages(project_dir):
        st = _stage_defs().get(sid) or {}
        agents = st.get("ideal_flow") or []
        files = sorted(f for f in os.listdir(d)
                       if os.path.isfile(os.path.join(d, f)) and f != "_stage.json")
        lines.append(f"## {stage_display(sid)}")
        lines.append("")
        if agents:
            lines.append("- Agents: " + ", ".join("`" + a + "`" for a in agents))
        if files:
            lines.append("- Artifacts:")
            for f in files:
                lines.append(f"  - `{f}`")
        lines.append("")
    p = os.path.join(base, "INDEX.md")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    return p


def refresh(project_dir: str, stage_id: str = "") -> None:
    """Best-effort refresh of the index (+ one stage's meta). Never raises."""
    try:
        if stage_id:
            write_stage_meta(project_dir, stage_id)
        write_index(project_dir)
    except Exception:
        pass
