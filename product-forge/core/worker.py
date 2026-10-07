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
import contextlib
import json
import os
import shlex
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from core.paths import PRODUCTS_DIR, ROOT

FILENAME = "worker-results.json"

LIFECYCLE = ("ASSIGNED", "INITIALIZING", "WORKING", "TESTING", "PR_READY", "INTEGRATING", "DONE")
FAILURE = ("BLOCKED", "FAILED", "NEEDS_REVIEW", "CONFLICT")
# WorkerResult.status -> task-contract status
_STATUS_MAP = {"PR_READY": "review", "DONE": "done", "NEEDS_REVIEW": "review",
               "BLOCKED": "blocked", "FAILED": "failed", "CONFLICT": "blocked"}


def _norm_scope(scope: str) -> str:
    return "product_forge" if str(scope) in ("portfolio", "product_forge") else "project"


def _stamp_end(res: "WorkerResult") -> "WorkerResult":
    """Close the timing window: set ended_at and, if the provider did not time it, the duration."""
    if not res.timing.get("ended_at"):
        try:
            started = datetime.fromisoformat(res.timing.get("started_at") or res.created_at)
            ended = datetime.now()
            res.timing["ended_at"] = ended.isoformat()
            if not res.timing.get("duration_ms"):
                res.timing["duration_ms"] = int((ended - started).total_seconds() * 1000)
        except Exception:
            res.timing["ended_at"] = datetime.now().isoformat()
    return res


def _extract_usage(out: dict[str, Any], fallback_model: str = "") -> dict[str, Any]:
    """Token + cost from a provider output, computing cost via core.cost_model (no duplicate cost logic).

    Accepts ``usage`` / ``tokens`` (input|output|in|out|prompt|completion) and a ``model``.
    """
    u = (out.get("usage") or out.get("tokens") or {}) if isinstance(out, dict) else {}
    it = int(u.get("input_tokens", u.get("input", u.get("in", u.get("prompt_tokens", 0)))) or 0)
    ot = int(u.get("output_tokens", u.get("output", u.get("out", u.get("completion_tokens", 0)))) or 0)
    model = str(u.get("model") or out.get("model") or fallback_model or "")
    cost = 0.0
    if it or ot:
        try:
            from core.cost_model import token_cost
            cost = float(token_cost(model, it, ot)) if model else 0.0
        except Exception:
            cost = 0.0
    return {"model": model, "input_tokens": it, "output_tokens": ot, "cost": round(cost, 6)}


def _dir(scope: str, project: str | None = None) -> str:
    if _norm_scope(scope) == "product_forge":
        return os.path.join(ROOT, "engineering")
    return os.path.join(PRODUCTS_DIR, str(project or "_unknown"), "engineering")


def path(scope: str, project: str | None = None) -> str:
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
    with contextlib.suppress(Exception):
        os.remove(lp)


def _read(scope: str, project: str | None = None) -> dict[str, Any]:
    try:
        with open(path(scope, project), encoding="utf-8-sig") as f:
            d = json.load(f)
        if isinstance(d, dict) and isinstance(d.get("results"), list):
            return d
    except Exception:
        pass
    return {"results": []}


def _write(scope: str, project: str | None, data: dict[str, Any]) -> None:
    p = path(scope, project)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, p)


def record_result(scope: str, project: str | None, result: dict[str, Any]) -> dict[str, Any]:
    d = _lock(_dir(scope, project))
    try:
        store = _read(scope, project)
        store["results"].append(result)
        _write(scope, project, store)
    finally:
        _unlock(d)
    # persist timing + usage onto the task contract (single writer: core.task_contract)
    task_id = str(result.get("task_id") or "")
    if task_id:
        try:
            from core import task_contract
            task_contract.set_metrics(scope, project, task_id,
                                      timing=result.get("timing") or {},
                                      usage=result.get("usage") or {})
        except Exception:
            pass
    return result


def list_results(scope: str, project: str | None = None, task_id: str = "") -> list[dict[str, Any]]:
    rows = _read(scope, project).get("results", [])
    if task_id:
        rows = [r for r in rows if str(r.get("task_id")) == str(task_id)]
    return list(rows)


def run_totals(scope: str, project: str | None = None, run_id: str = "") -> dict[str, Any]:
    """Aggregate timing + tokens + cost across worker results (optionally one run).

    Active work time and human-wait time are reported separately; tokens and cost summed.
    Reuses the worker-results store - no new store.
    """
    rows = list_results(scope, project)
    if run_id:
        rows = [r for r in rows if str(r.get("run_id")) == str(run_id)]
    agg = {"workers": 0, "duration_ms": 0, "wait_ms": 0, "total_ms": 0,
           "input_tokens": 0, "output_tokens": 0, "cost": 0.0, "by_worker": [], "run_id": run_id}
    for r in rows:
        t = r.get("timing") or {}
        u = r.get("usage") or {}
        d = int(t.get("duration_ms") or 0)
        w = int(t.get("wait_ms") or 0)
        row = {"worker_id": r.get("worker_id"), "task_id": r.get("task_id"),
               "provider": r.get("provider"), "status": r.get("status"),
               "started_at": t.get("started_at", ""), "ended_at": t.get("ended_at", ""),
               "duration_ms": d, "wait_ms": w, "total_ms": d + w,
               "input_tokens": int(u.get("input_tokens") or 0),
               "output_tokens": int(u.get("output_tokens") or 0),
               "cost": float(u.get("cost") or 0.0)}
        agg["workers"] += 1
        agg["duration_ms"] += row["duration_ms"]
        agg["wait_ms"] += row["wait_ms"]
        agg["total_ms"] += row["total_ms"]
        agg["input_tokens"] += row["input_tokens"]
        agg["output_tokens"] += row["output_tokens"]
        agg["cost"] = round(agg["cost"] + row["cost"], 6)
        agg["by_worker"].append(row)
    return agg


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
    files_changed: list[str] = field(default_factory=list)
    tests: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str = ""
    lifecycle: list[str] = field(default_factory=list)
    created_at: str = ""
    # timing: active work vs time blocked on a human (approval/response/input), both in ms
    timing: dict[str, Any] = field(default_factory=lambda: {
        "started_at": "", "ended_at": "", "duration_ms": 0, "wait_ms": 0})
    # token + cost accounting for this worker (populated from the provider output)
    usage: dict[str, Any] = field(default_factory=lambda: {
        "model": "", "input_tokens": 0, "output_tokens": 0, "cost": 0.0})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def metrics(self) -> dict[str, Any]:
        """Aggregate timing + usage in one place (no separate store)."""
        return {
            "duration_ms": int(self.timing.get("duration_ms") or 0),
            "wait_ms": int(self.timing.get("wait_ms") or 0),
            "total_ms": int(self.timing.get("duration_ms") or 0) + int(self.timing.get("wait_ms") or 0),
            "input_tokens": int(self.usage.get("input_tokens") or 0),
            "output_tokens": int(self.usage.get("output_tokens") or 0),
            "cost": float(self.usage.get("cost") or 0.0),
        }


# ── providers (adapters) ────────────────────────────────────────────────────
class WorkerProvider:
    name = "base"
    description = ""

    def available(self) -> bool:
        return True

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:  # pragma: no cover - abstract
        raise NotImplementedError


class NoopProvider(WorkerProvider):
    name = "noop"
    description = "no implementation adapter; mark the task NEEDS_REVIEW"

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "status": "needs_review", "output": "noop provider: no code produced"}


class HumanProvider(WorkerProvider):
    name = "human"
    description = "hand the task to a human operator"

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "status": "needs_review", "output": "queued for a human operator"}


class CommandProvider(WorkerProvider):
    name = "command"
    description = "run a configured command inside the isolated worktree"

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
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

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
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


class ClaudeCodeProvider(WorkerProvider):
    """Optional Claude Code CLI adapter. A client only - PF never depends on it being present."""
    name = "claude-code"
    description = "Claude Code CLI adapter (optional client; degrades to BLOCKED if absent)"

    def available(self) -> bool:
        return shutil.which("claude") is not None

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        exe = shutil.which("claude")
        if not exe:
            return {"ok": False, "status": "blocked",
                    "error": "claude not installed (optional adapter; not a dependency)"}
        objective = str(ctx.get("objective") or (ctx.get("task") or {}).get("objective") or "")
        argv = ctx.get("command") or [exe, "-p", objective]
        if isinstance(argv, str):
            argv = shlex.split(argv)
        try:
            r = subprocess.run(argv, cwd=ctx["worktree"], capture_output=True, text=True,
                               timeout=int(ctx.get("timeout") or 3600))
        except Exception as e:
            return {"ok": False, "status": "failed", "error": str(e)}
        return {"ok": r.returncode == 0, "status": "pr_ready" if r.returncode == 0 else "failed",
                "output": (r.stdout or "")[-4000:], "error": (r.stderr or "")[-2000:]}


_PROVIDERS: dict[str, WorkerProvider] = {p.name: p for p in
                                         (NoopProvider(), HumanProvider(), CommandProvider(),
                                          OpenCodeProvider(), ClaudeCodeProvider())}


def available_providers() -> list[dict[str, Any]]:
    return [{"name": p.name, "description": p.description, "available": bool(p.available())}
            for p in _PROVIDERS.values()]


def _new_run_id() -> str:
    """Canonical Product Forge run identity (same namespace as pipeline runs)."""
    try:
        from core.pipeline_executor import new_run_id
        return str(new_run_id())
    except Exception:
        return f"run-{int(time.time())}"


def _git(cwd: str, *args: str) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=120)
        return (r.stdout or "").strip()
    except Exception:
        return ""


def task_project_dir(scope: str, project: str | None) -> str:
    """The repository a task's worktree is created in (product_forge -> the Product Forge repo)."""
    return ROOT if _norm_scope(scope) == "product_forge" else os.path.join(PRODUCTS_DIR, str(project or ""))


def run_task(task: dict[str, Any], project_dir: str, provider: str = "noop", base: str = "",
             run_id: str = "", command: Any = None, commit: bool = False,
             timeout: int = 1800) -> WorkerResult:
    """Execute one task contract in an isolated worktree; return a normalized WorkerResult."""
    from core.vcs import VCSManager

    res = WorkerResult(task_id=str(task.get("task_id") or ""), provider=str(provider),
                       run_id=run_id or _new_run_id(),
                       worker_id=str(task.get("required_worker_type") or "worker"),
                       created_at=datetime.now().isoformat())
    res.timing["started_at"] = res.created_at
    res.lifecycle.append("ASSIGNED")

    prov = _PROVIDERS.get(str(provider))
    if prov is None:
        res.status, res.error = "FAILED", f"unknown provider {provider!r}"
        res.lifecycle.append("FAILED")
        return _stamp_end(res)
    if not prov.available():
        res.status, res.error = "BLOCKED", f"provider {provider!r} unavailable"
        res.lifecycle.append("BLOCKED")
        return _stamp_end(res)

    vcs = VCSManager(project_dir)
    if not vcs.is_repo():
        res.status, res.error = "BLOCKED", "project is not a git repository"
        res.lifecycle.append("BLOCKED")
        return _stamp_end(res)

    res.lifecycle.append("INITIALIZING")
    area = str((task.get("affected_components") or ["task"])[0])
    branch = str((task.get("branch_policy") or {}).get("branch") or "") or \
        VCSManager.feature_branch_name(area, res.task_id)
    wt = vcs.add_worktree(res.task_id or "task", branch=branch, base=base)
    if not wt.get("ok"):
        res.status, res.error = "FAILED", wt.get("error") or "worktree create failed"
        res.lifecycle.append("FAILED")
        return _stamp_end(res)
    res.worktree_id, res.branch = wt["name"], wt["branch"]
    worktree = wt["path"]
    res.base_commit = _git(worktree, "rev-parse", "HEAD")

    res.lifecycle.append("WORKING")
    ctx = {"task": task, "project_dir": project_dir, "worktree": worktree, "branch": res.branch,
           "run_id": res.run_id, "objective": task.get("objective"), "timeout": timeout,
           "command": command or (task.get("branch_policy") or {}).get("worker_command")}
    _work_start = time.time()
    out = prov.run(ctx)
    _work_end = time.time()
    res.evidence["provider_output"] = str(out.get("output") or "")
    if out.get("error"):
        res.error = str(out["error"])
    # timing: active work time; human wait (approval/response/input) is tracked SEPARATELY
    res.timing["duration_ms"] = int((_work_end - _work_start) * 1000)
    res.timing["wait_ms"] = int(out.get("wait_ms") or out.get("human_wait_ms") or 0)
    res.usage = _extract_usage(out, fallback_model=str(task.get("model") or ""))
    # merge any learning/usage the provider reported into evidence (single source: the result)
    if out.get("usage") or out.get("tokens"):
        res.evidence["usage"] = dict(res.usage)

    res.lifecycle.append("TESTING")
    if commit and out.get("ok"):
        _git(worktree, "add", "-A")
        c = _git(worktree, "commit", "-m", f"{res.task_id}: {str(task.get('title') or '')[:60]}")
        if not c:
            res.warnings.append("no commit created (nothing to commit)")
    if commit:
        res.final_commit = _git(worktree, "rev-parse", "HEAD")
        # Stage 2a (git sync): optionally push the feature branch (gated by PF_AUTO_PUSH; default off).
        if res.branch and VCSManager.auto_push_enabled():
            with contextlib.suppress(Exception):
                vcs.push(res.branch)
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
    return _stamp_end(res)


def contract_status_for(result: dict[str, Any]) -> str:
    """Map a WorkerResult to the next task-contract status."""
    return _STATUS_MAP.get(str(result.get("status") or ""), "in_progress")
