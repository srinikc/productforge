"""ENG-4: worker runtime + provider abstraction + normalized WorkerResult.

A worker executes ONE scheduled task contract inside an isolated worktree (ENG-3) and returns a **PF-owned,
normalized** ``WorkerResult`` (plan §16). Providers are adapters:

    WorkerProvider
      +-- NoopProvider        (mark NEEDS_REVIEW; safe default)
      +-- HumanProvider       (hand to a human operator)
      +-- CommandProvider     (run a configured command in the worktree)
      +-- OpenCodeProvider    (OpenCode session adapter - OPTIONAL; a client, never a dependency)

The runtime itself owns no engine state beyond the evidence store ``worker-results.json`` (single writer here);
task status is updated only through ``core.task_contract`` (the task store's single writer).
"""
import json
import os
import shlex
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.paths import PRODUCTS_DIR, ROOT

FILENAME = "worker-results.json"

LIFECYCLE = ("ASSIGNED", "INITIALIZING", "WORKING", "TESTING", "PR_READY", "INTEGRATING", "DONE")
FAILURE = ("BLOCKED", "FAILED", "NEEDS_REVIEW", "CONFLICT")
# WorkerResult.status -> task-contract status
_STATUS_MAP = {"PR_READY": "review", "DONE": "done", "NEEDS_REVIEW": "review",
               "BLOCKED": "blocked", "FAILED": "failed", "CONFLICT": "blocked"}


def _norm_scope(scope: str) -> str:
    return "product_forge" if str(scope) in ("portfolio", "product_forge") else "project"


def _dir(scope: str, project: Optional[str] = None) -> str:
    if _norm_scope(scope) == "product_forge":
        return os.path.join(ROOT, "engineering")
    return os.path.join(PRODUCTS_DIR, str(project or "_unknown"), "engineering")


def path(scope: str, project: Optional[str] = None) -> str:
    return os.path.join(_dir(scope, project), FILENAME)


def _lock(d: str) -> str:
    os.makedirs(d, exist_ok=True)
    lp = os.path.join(d, ".lock")
    for _ in range(50):
        try:
            fd = os.open(lp, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return lp
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(lp) > 300:
                    os.remove(lp)
                    continue
            except Exception:
                pass
            time.sleep(0.1)
    raise TimeoutError("could not acquire worker-result lock")


def _unlock(lp: str) -> None:
    try:
        os.remove(lp)
    except Exception:
        pass


def _read(scope: str, project: Optional[str] = None) -> Dict[str, Any]:
    try:
        with open(path(scope, project), encoding="utf-8-sig") as f:
            d = json.load(f)
        if isinstance(d, dict) and isinstance(d.get("results"), list):
            return d
    except Exception:
        pass
    return {"results": []}


def _write(scope: str, project: Optional[str], data: Dict[str, Any]) -> None:
    p = path(scope, project)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, p)


def record_result(scope: str, project: Optional[str], result: Dict[str, Any]) -> Dict[str, Any]:
    d = _lock(_dir(scope, project))
    try:
        store = _read(scope, project)
        store["results"].append(result)
        _write(scope, project, store)
        return result
    finally:
        _unlock(d)


def list_results(scope: str, project: Optional[str] = None, task_id: str = "") -> List[Dict[str, Any]]:
    rows = _read(scope, project).get("results", [])
    if task_id:
        rows = [r for r in rows if str(r.get("task_id")) == str(task_id)]
    return list(rows)


@dataclass
class WorkerResult:
    task_id: str = ""
    worker_id: str = ""
    provider: str = ""
    run_id: str = ""
    worktree_id: str = ""
    branch: str = ""
    base_commit: str = ""
    final_commit: str = ""
    status: str = "FAILED"
    files_changed: List[str] = field(default_factory=list)
    tests: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    error: str = ""
    lifecycle: List[str] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── providers (adapters) ────────────────────────────────────────────────────
class WorkerProvider:
    name = "base"
    description = ""

    def available(self) -> bool:
        return True

    def run(self, ctx: Dict[str, Any]) -> Dict[str, Any]:  # pragma: no cover - abstract
        raise NotImplementedError


class NoopProvider(WorkerProvider):
    name = "noop"
    description = "no implementation adapter; mark the task NEEDS_REVIEW"

    def run(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        return {"ok": True, "status": "needs_review", "output": "noop provider: no code produced"}


class HumanProvider(WorkerProvider):
    name = "human"
    description = "hand the task to a human operator"

    def run(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        return {"ok": True, "status": "needs_review", "output": "queued for a human operator"}


class CommandProvider(WorkerProvider):
    name = "command"
    description = "run a configured command inside the isolated worktree"

    def run(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        cmd = ctx.get("command")
        if not cmd:
            return {"ok": False, "status": "blocked", "error": "no command supplied for 'command' provider"}
        argv = shlex.split(cmd) if isinstance(cmd, str) else list(cmd)
        try:
            r = subprocess.run(argv, cwd=ctx["worktree"], capture_output=True, text=True,
                               timeout=int(ctx.get("timeout") or 1800))
        except Exception as e:
            return {"ok": False, "status": "failed", "error": str(e)}
        return {"ok": r.returncode == 0, "status": "pr_ready" if r.returncode == 0 else "failed",
                "output": (r.stdout or "")[-4000:], "error": (r.stderr or "")[-2000:]}


class OpenCodeProvider(WorkerProvider):
    """Optional OpenCode session adapter. A client only - PF never depends on OpenCode being present."""
    name = "opencode"
    description = "OpenCode session adapter (optional client; degrades to BLOCKED if absent)"

    def available(self) -> bool:
        return shutil.which("opencode") is not None

    def run(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        exe = shutil.which("opencode")
        if not exe:
            return {"ok": False, "status": "blocked",
                    "error": "opencode not installed (optional adapter; not a dependency)"}
        objective = str(ctx.get("objective") or (ctx.get("task") or {}).get("objective") or "")
        try:
            r = subprocess.run([exe, "run", objective], cwd=ctx["worktree"],
                               capture_output=True, text=True, timeout=int(ctx.get("timeout") or 3600))
        except Exception as e:
            return {"ok": False, "status": "failed", "error": str(e)}
        return {"ok": r.returncode == 0, "status": "pr_ready" if r.returncode == 0 else "failed",
                "output": (r.stdout or "")[-4000:], "error": (r.stderr or "")[-2000:]}


_PROVIDERS: Dict[str, WorkerProvider] = {p.name: p for p in
                                         (NoopProvider(), HumanProvider(), CommandProvider(), OpenCodeProvider())}


def available_providers() -> List[Dict[str, Any]]:
    return [{"name": p.name, "description": p.description, "available": bool(p.available())}
            for p in _PROVIDERS.values()]


def _git(cwd: str, *args: str) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=120)
        return (r.stdout or "").strip()
    except Exception:
        return ""


def task_project_dir(scope: str, project: Optional[str]) -> str:
    """The repository a task's worktree is created in (product_forge -> the Product Forge repo)."""
    return ROOT if _norm_scope(scope) == "product_forge" else os.path.join(PRODUCTS_DIR, str(project or ""))


def run_task(task: Dict[str, Any], project_dir: str, provider: str = "noop", base: str = "",
             run_id: str = "", command: Any = None, commit: bool = False,
             timeout: int = 1800) -> WorkerResult:
    """Execute one task contract in an isolated worktree; return a normalized WorkerResult."""
    from core.vcs import VCSManager

    res = WorkerResult(task_id=str(task.get("task_id") or ""), provider=str(provider),
                       run_id=run_id or f"wrun-{int(time.time())}",
                       worker_id=str(task.get("required_worker_type") or "worker"),
                       created_at=datetime.now().isoformat())
    res.lifecycle.append("ASSIGNED")

    prov = _PROVIDERS.get(str(provider))
    if prov is None:
        res.status, res.error = "FAILED", f"unknown provider {provider!r}"
        res.lifecycle.append("FAILED")
        return res
    if not prov.available():
        res.status, res.error = "BLOCKED", f"provider {provider!r} unavailable"
        res.lifecycle.append("BLOCKED")
        return res

    vcs = VCSManager(project_dir)
    if not vcs.is_repo():
        res.status, res.error = "BLOCKED", "project is not a git repository"
        res.lifecycle.append("BLOCKED")
        return res

    res.lifecycle.append("INITIALIZING")
    area = str((task.get("affected_components") or ["task"])[0])
    branch = str((task.get("branch_policy") or {}).get("branch") or "") or \
        VCSManager.feature_branch_name(area, res.task_id)
    wt = vcs.add_worktree(res.task_id or "task", branch=branch, base=base)
    if not wt.get("ok"):
        res.status, res.error = "FAILED", wt.get("error") or "worktree create failed"
        res.lifecycle.append("FAILED")
        return res
    res.worktree_id, res.branch = wt["name"], wt["branch"]
    worktree = wt["path"]
    res.base_commit = _git(worktree, "rev-parse", "HEAD")

    res.lifecycle.append("WORKING")
    ctx = {"task": task, "project_dir": project_dir, "worktree": worktree, "branch": res.branch,
           "run_id": res.run_id, "objective": task.get("objective"), "timeout": timeout,
           "command": command or (task.get("branch_policy") or {}).get("worker_command")}
    out = prov.run(ctx)
    res.evidence["provider_output"] = str(out.get("output") or "")
    if out.get("error"):
        res.error = str(out["error"])

    res.lifecycle.append("TESTING")
    if commit and out.get("ok"):
        _git(worktree, "add", "-A")
        c = _git(worktree, "commit", "-m", f"{res.task_id}: {str(task.get('title') or '')[:60]}")
        if not c:
            res.warnings.append("no commit created (nothing to commit)")
    if commit:
        res.final_commit = _git(worktree, "rev-parse", "HEAD")
    changed = set()
    if res.base_commit:
        changed.update(x for x in _git(worktree, "diff", "--name-only",
                                       f"{res.base_commit}..HEAD").splitlines() if x.strip())
    changed.update(x[3:].strip() for x in _git(worktree, "status", "--porcelain").splitlines()
                   if x.strip() and not x.startswith("??"))
    changed.update(x[3:].strip() for x in _git(worktree, "status", "--porcelain").splitlines()
                   if x.startswith("??"))
    res.files_changed = sorted(changed)

    st = str(out.get("status") or "")
    if out.get("ok") and st == "pr_ready":
        res.status = "PR_READY"
    elif st == "needs_review":
        res.status = "NEEDS_REVIEW"
    elif out.get("ok"):
        res.status = "DONE"
    else:
        res.status = "FAILED"
    res.lifecycle.append(res.status)
    res.tests = [{"requirement": str(t), "ran": False} for t in (task.get("test_requirements") or [])]
    return res


def contract_status_for(result: Dict[str, Any]) -> str:
    """Map a WorkerResult to the next task-contract status."""
    return _STATUS_MAP.get(str(result.get("status") or ""), "in_progress")
