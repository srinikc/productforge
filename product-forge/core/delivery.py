"""BI-PF-0421: optimistic delivery lane.

On completion an item is in status ``verifying`` (execution done). This module ORCHESTRATES its delivery by
composing existing owners (no new engine, no new store):

  push feature branch + open PR (github.create_pr; degrades to a local pr_ready record without ``gh``)
    -> validate (validation_engine.feature_pr; 0420 parallel-safe, own worktree)
    -> LANDING (serialized by a repo lock): rebase onto the integration branch
         -> fast re-verify (run_quality_gate) -> merge --no-ff -> push integration
         -> backlog.set_delivery(...) + set_status(completed)

Fail-closed: any failure/conflict -> ``blocked`` (+ a defect via the caller), never merge.

Queue = backlog items in status ``verifying`` (no new store; single writer core/backlog.py).

Constraint (documented): the landing checks out the integration branch in the project dir, so the lane must run
against a working tree dedicated to integration (a generated product's repo, or a dedicated PF runner/clone) -
not a live operator session on ``product_forge`` (IS-PF-0036).
"""
import contextlib
import os
import time

from core.paths import PRODUCTS_DIR, ROOT

_LOCK_TTL = 900  # seconds


def repo_dir(scope: str, project: str | None) -> str:
    return str(ROOT) if str(scope) == "product_forge" else os.path.join(str(PRODUCTS_DIR), str(project or ""))


def _lock_path(repo: str) -> str:
    d = os.path.join(repo, "engineering")
    with contextlib.suppress(Exception):
        os.makedirs(d, exist_ok=True)
    return os.path.join(d, ".delivery.lock")


def _acquire(repo: str) -> str:
    lp = _lock_path(repo)
    if os.path.exists(lp):
        with contextlib.suppress(Exception):
            if time.time() - os.path.getmtime(lp) > _LOCK_TTL:
                os.remove(lp)
    try:
        fd = os.open(lp, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return lp
    except FileExistsError:
        return ""


def _release(lp: str) -> None:
    with contextlib.suppress(Exception):
        os.remove(lp)


def _block(scope: str, project: str | None, item_id: str, reason: str) -> dict:
    from core import backlog
    backlog.set_status(scope, project, item_id, "blocked", note=f"delivery: {reason}")
    return {"ok": False, "item": item_id, "reason": reason}


def deliver(scope: str = "product_forge", project: str | None = None, item_id: str = "",
            *, integration: str = "") -> dict:
    """Deliver ONE item end to end (see module docstring). Idempotent per item; fail-closed."""
    from core import backlog, github, run_quality_gate, validation_engine, vcs
    it = backlog.get_epic(scope, project, item_id)
    if not it:
        return {"ok": False, "reason": "item not found"}
    repo = repo_dir(scope, project)
    v = vcs.VCSManager(repo)
    if not v.is_repo():
        return _block(scope, project, item_id, "not a git repository")
    target = str(integration or getattr(v, "integration_branch", "") or "develop")
    branch = v.feature_branch_name("wg", item_id)
    if not v._git(["rev-parse", "--verify", branch]).get("ok"):
        return _block(scope, project, item_id, f"branch {branch!r} not found")

    # 1) publish: push the feature branch + open a PR (guarded; degrades without gh)
    push = v.push(branch) if v.has_remote() else {"ok": False, "error": "no remote"}
    pr = github.create_pr(project or scope, repo, title=f"{item_id}: {it.get('title') or ''}",
                          head=branch, base=target, backlog_ref=item_id, scope=scope)

    # 2) validate (parallel-safe; feature_pr uses its own validation worktree and runs pr_gate)
    val = validation_engine.feature_pr(project or scope, repo, target=branch, base=target, scope=scope)
    if str(val.get("result")) != "PASS":
        return _block(scope, project, item_id, f"validation {val.get('result')}")

    # 3) LANDING (serialized): rebase onto latest integration -> fast re-verify -> merge -> push
    lp = _acquire(repo)
    if not lp:
        return {"ok": False, "item": item_id, "reason": "delivery lane busy"}
    try:
        v._git(["checkout", branch])
        if v.has_remote():
            v.fetch()
        rb = v.rebase(target)
        if not rb.get("ok") or v.has_conflicts():
            return _block(scope, project, item_id, "rebase conflict")
        g = run_quality_gate.evaluate(repo, "item", run_dir=repo, run_id=f"deliver-{item_id}")
        if not g.get("passed"):
            return _block(scope, project, item_id, f"post-rebase gate failed: {g.get('reasons')}")
        m = v.merge(branch, target, message=f"merge {item_id}: {it.get('title') or ''}", require_gate=False)
        if not m.get("ok"):
            return _block(scope, project, item_id, f"merge failed: {m.get('error')}")
        if v.has_remote():
            v.push(target)
        merge_sha = v.head_commit(target)
        backlog.set_delivery(scope, project, item_id, branch=branch, merge_sha=merge_sha,
                             pr=str(pr.get("number") or ""), pr_url=str(pr.get("url") or ""),
                             note="optimistic delivery lane")
        backlog.set_status(scope, project, item_id, "completed", note="delivered (merge-to-develop)")
        return {"ok": True, "item": item_id, "branch": branch, "merge_sha": merge_sha,
                "pr": pr.get("number") or "", "pr_url": pr.get("url") or "", "pushed": bool(push.get("ok"))}
    finally:
        _release(lp)


def drain(scope: str = "product_forge", project: str | None = None, *, limit: int = 0) -> dict:
    """Process items awaiting delivery (status ``verifying``), one landing at a time."""
    from core import backlog
    items = [i for i in backlog.list_open(scope, project, order=False)
             if backlog._normalize_status(str(i.get("status") or "")) == "verifying"]
    done = []
    for it in (items[:limit] if limit else items):
        r = deliver(scope, project, str(it.get("id")))
        done.append({"item": it.get("id"), "ok": bool(r.get("ok")), "reason": r.get("reason", "")})
    return {"delivered": done, "count": len(done)}
