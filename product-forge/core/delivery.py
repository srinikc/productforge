"""BI-PF-0421 / BI-PF-0428: optimistic delivery lane.

On completion an item is ``verifying`` (execution done). This module ORCHESTRATES its delivery by composing
existing owners (no new engine, no new store):

  push feature branch + open PR (github.create_pr)
    -> validate (validation_engine.feature_pr; 0420 parallel-safe, own worktree)
    -> LANDING (serialized by a repo lock) - NEVER checks out the integration branch in the live tree:
         * gh available + PR number:  ``gh pr merge --merge``  (GitHub merges; develop advances remotely)
         * else:                     temp ``integrate/<item>`` worktree off ``origin/<integration>`` ->
                                     merge -> fast re-verify -> ``git push origin HEAD:<integration>``
  -> backlog.set_delivery + set_status(completed)

Fail-closed: any failure/conflict -> ``blocked``; never merge.

BI-PF-0428: the landing must NOT switch the branch of the live working tree (IS-PF-0036); it lands in a
GitHub-side merge (preferred) or a throwaway `integrate/*` worktree - ROOT is never checked out.

Queue = backlog items in status ``verifying`` (no new store; single writer core/backlog.py).
"""
import contextlib
import os
import subprocess
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


def _git_in(cwd: str, *args: str):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=300)


def _gh() -> str:
    try:
        from core import github
        return github._gh()
    except Exception:
        return ""


def _land(v, repo: str, item_id: str, target: str, branch: str, pr: dict, title: str) -> dict:
    """Serialized landing. gh PR-merge primary; integrate-worktree push-ref fallback. ROOT never checked out."""
    number = str(pr.get("number") or "")
    gh = _gh()
    if gh and number:
        with contextlib.suppress(Exception):
            subprocess.run([gh, "pr", "update-branch", number], cwd=repo,
                           capture_output=True, text=True, timeout=180)
        # BI-PF-1255: no --delete-branch - the head branch is normally checked out by a worker
        # worktree, so gh's LOCAL branch delete fails and would spuriously fail a good merge.
        def _merge():
            return subprocess.run([gh, "pr", "merge", number, "--merge"],
                                  cwd=repo, capture_output=True, text=True, timeout=300)

        r = _merge()
        if r.returncode != 0 and "base branch was modified" in ((r.stderr or "") + (r.stdout or "")).lower():
            # transient race (develop advanced mid-run): re-update the branch and retry once
            with contextlib.suppress(Exception):
                subprocess.run([gh, "pr", "update-branch", number], cwd=repo,
                               capture_output=True, text=True, timeout=180)
            r = _merge()
        if r.returncode == 0:
            with contextlib.suppress(Exception):
                v.fetch()
            return {"ok": True, "merge_sha": v.head_commit(f"origin/{target}"), "method": "gh-pr-merge"}
        return {"ok": False, "reason": f"gh pr merge failed: {((r.stderr or r.stdout) or '').strip()[:200]}"}

    # fallback (no gh / no PR): temp integrate worktree off origin/<target>, then push HEAD:<target>
    from core import run_quality_gate
    if v.has_remote():
        v.fetch()
    ts = int(time.time())
    wt = v.add_worktree(f"integrate-{item_id}-{ts}", branch=f"integrate/{item_id}-{ts}", base=v.base_ref(target))
    if not wt.get("ok"):
        return {"ok": False, "reason": f"integrate worktree failed: {wt.get('error')}"}
    try:
        m = _git_in(wt["path"], "merge", "--no-ff", branch, "-m", f"merge {item_id}: {title or ''}")
        if m.returncode != 0:
            return {"ok": False, "reason": "integrate merge conflict"}
        # BI-PF-1254: run the gate on the PF code root (the product-forge/ subtree in a framework
        # repo), not the repo root, so repo-level layouts don't spuriously fail wired_audit.
        code_root = wt["path"]
        _sub = os.path.join(wt["path"], "product-forge")
        if os.path.isdir(_sub) and os.path.isfile(os.path.join(_sub, "core", "paths.py")):
            code_root = _sub
        g = run_quality_gate.evaluate(code_root, "item", run_dir=code_root, run_id=f"deliver-{item_id}")
        if not g.get("passed"):
            return {"ok": False, "reason": f"post-merge gate failed: {g.get('reasons')}"}
        merge_sha = _git_in(wt["path"], "rev-parse", "HEAD").stdout.strip()
        if v.has_remote():
            p = _git_in(wt["path"], "push", "origin", f"HEAD:{target}")
            if p.returncode != 0:
                return {"ok": False,
                        "reason": f"push {target} failed: {((p.stderr or p.stdout) or '').strip()[:200]}"}
        return {"ok": True, "merge_sha": merge_sha, "method": "push-ref"}
    finally:
        with contextlib.suppress(Exception):
            v.remove_worktree(wt["name"])
            _git_in(repo, "branch", "-D", f"integrate/{item_id}-{ts}")


def deliver(scope: str = "product_forge", project: str | None = None, item_id: str = "",
            *, integration: str = "") -> dict:
    """Deliver ONE item end to end (see module docstring). Idempotent per item; fail-closed."""
    from core import backlog, github, validation_engine, vcs, runtime_freshness
    it = backlog.get_epic(scope, project, item_id)
    if not it:
        return {"ok": False, "reason": "item not found"}
    # BI-PF-1253: fail-closed on a stale runtime. A long-lived process (the API server) keeps executing
    # its import-time snapshot after merges; refuse instead of validating/merging with outdated code.
    fs = runtime_freshness.status()
    if fs.get("stale"):
        return _block(scope, project, item_id,
                      f"stale runtime: loaded {fs['loaded_sha'][:8]} != tree {fs['current_sha'][:8]} "
                      f"- restart the API server (or run `python -m core.delivery {item_id}` for a fresh process)")
    repo = repo_dir(scope, project)
    v = vcs.VCSManager(repo)
    if not v.is_repo():
        return _block(scope, project, item_id, "not a git repository")
    target = str(integration or getattr(v, "integration_branch", "") or "develop")
    branch = v.feature_branch_name("wg", item_id)
    if not v._git(["rev-parse", "--verify", branch]).get("ok"):
        return _block(scope, project, item_id, f"branch {branch!r} not found")

    # 1) publish: push the feature branch + open a PR
    push = v.push(branch) if v.has_remote() else {"ok": False, "error": "no remote"}
    pr_res = github.create_pr(project or scope, repo, title=f"{item_id}: {it.get('title') or ''}",
                              head=branch, base=target, backlog_ref=item_id, scope=scope)
    # BI-PF-1254: create_pr returns {ok, pr:{number,url,...}, evidence}; _land + provenance need the
    # PR record itself, not the envelope (the shape mismatch silently forced the push-ref fallback).
    pr = pr_res.get("pr") if isinstance(pr_res, dict) else None
    if not isinstance(pr, dict):
        pr = pr_res if isinstance(pr_res, dict) else {}

    # 2) validate (parallel-safe; feature_pr uses its own validation worktree)
    val = validation_engine.feature_pr(project or scope, repo, target=branch, base=target, scope=scope)
    if str(val.get("result")) != "PASS":
        return _block(scope, project, item_id, f"validation {val.get('result')}")

    # 3) LANDING (serialized; live tree never checked out)
    lp = _acquire(repo)
    if not lp:
        return {"ok": False, "item": item_id, "reason": "delivery lane busy"}
    try:
        land = _land(v, repo, item_id, target, branch, pr, it.get("title") or "")
        if not land.get("ok"):
            return _block(scope, project, item_id, land.get("reason") or "landing failed")
        backlog.set_delivery(scope, project, item_id, branch=branch, merge_sha=land["merge_sha"],
                             pr=str(pr.get("number") or ""), pr_url=str(pr.get("url") or ""),
                             note=f"delivery ({land['method']})")
        backlog.set_status(scope, project, item_id, "completed", note="delivered")
        return {"ok": True, "item": item_id, "branch": branch, "merge_sha": land["merge_sha"],
                "pr": pr.get("number") or "", "pr_url": pr.get("url") or "",
                "method": land["method"], "pushed": bool(push.get("ok"))}
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


def _main(argv=None) -> int:
    """BI-PF-1253: CLI so the lane can deliver in a FRESH process on current tree code.

    ``python -m core.delivery <item> [--scope s] [--project p]`` - a short-lived process always loads
    the current checkout (never a stale server snapshot).
    """
    import argparse
    import json
    ap = argparse.ArgumentParser(description="Delivery lane (BI-PF-1253: run on fresh tree code)")
    ap.add_argument("item")
    ap.add_argument("--scope", default="product_forge")
    ap.add_argument("--project", default=None)
    a = ap.parse_args(argv)
    print(json.dumps(deliver(a.scope, a.project, a.item), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
