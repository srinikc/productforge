"""ENG-3 gate: the one git owner (core.vcs) provides worktree isolation + branch naming.

Exercises, in an isolated temp repo: branch-name helpers, worktree add/list/remove, working-dir isolation,
and protected-branch detection. Regression guard for PF-050 (worktree creation must not pass a bad kwarg).
Run: ``python scripts/dev/vcs_worktree_check.py`` (wired into precheck). Exit 1 on any failure.
"""
import os
import shutil
import subprocess
import sys
import tempfile

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

FAILS = []


def _check(cond, msg):
    if not cond:
        FAILS.append(msg)


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def main() -> int:
    from core.vcs import VCSManager

    _check(VCSManager.feature_branch_name("Web UI", "TC-PF-0001") == "feature/web-ui/tc-pf-0001",
           "feature_branch_name format")
    _check(VCSManager.validation_branch_name("RUN 42") == "validation/run-42",
           "validation_branch_name format")

    tmp = tempfile.mkdtemp(prefix="pf-vcs-worktree-")
    try:
        _git(tmp, "init", "-q")
        _git(tmp, "config", "user.email", "pf@local")
        _git(tmp, "config", "user.name", "Product Forge")
        with open(os.path.join(tmp, "README.md"), "w", encoding="utf-8") as f:
            f.write("init\n")
        _git(tmp, "add", "-A")
        _git(tmp, "commit", "-q", "-m", "init")

        m = VCSManager(tmp)
        _check(m.is_repo(), "temp repo detected")
        branch = VCSManager.feature_branch_name("eng", "TC-PF-0002")
        res = m.add_worktree("worker-a", branch=branch)
        _check(res.get("ok"), f"add_worktree ok: {res.get('error')}")
        if res.get("ok"):
            _check(os.path.normcase(res["path"]).startswith(os.path.normcase(m.worktree_root())),
                   "worktree under worktree_root")
            listed = m.list_worktrees()
            _check(any(os.path.normcase(os.path.abspath(w.get("path", ""))) == os.path.normcase(res["path"])
                       for w in listed), "worktree appears in list")
            with open(os.path.join(res["path"], "only.txt"), "w", encoding="utf-8") as f:
                f.write("y\n")
            _check(not os.path.exists(os.path.join(tmp, "only.txt")),
                   "worktree isolated from main working dir")
            rr = m.remove_worktree("worker-a")
            _check(rr.get("ok"), f"remove_worktree ok: {rr.get('error')}")
        _check(m.is_protected("main"), "main is protected")
        _check(m.is_protected("develop"), "develop is protected")

        # Stage 2a (git sync): auto-push gating, fetch/base_ref without + with a remote
        _check(VCSManager.auto_push_enabled() is False, "auto-push default off")
        os.environ["PF_AUTO_PUSH"] = "1"
        _check(VCSManager.auto_push_enabled() is True, "auto-push honors PF_AUTO_PUSH=1")
        os.environ.pop("PF_AUTO_PUSH", None)
        _check(m.fetch().get("ok") is False, "fetch is a no-op without a remote")
        _check(m.base_ref() == m.integration_branch, "base_ref -> local integration without a remote")
        _check(m.sync(push=False).get("ok") is False, "sync no-op without a remote")

        remote = tempfile.mkdtemp(prefix="pf-vcs-remote-")
        try:
            _git(remote, "init", "--bare", "-q")
            _git(tmp, "branch", m.integration_branch)          # develop at HEAD
            _git(tmp, "remote", "add", "origin", remote)
            _git(tmp, "push", "-q", "-u", "origin", m.integration_branch)
            _check(m.fetch().get("ok"), "fetch ok with a remote")
            _check(m.base_ref() == f"origin/{m.integration_branch}",
                   f"base_ref prefers origin/<integration> (got {m.base_ref()})")
        finally:
            shutil.rmtree(remote, ignore_errors=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if FAILS:
        print("vcs-worktree: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("vcs-worktree: OK (naming, add/list/remove, isolation, protected)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
