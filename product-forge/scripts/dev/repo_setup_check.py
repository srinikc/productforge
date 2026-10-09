"""BI-PF gate: stage-0 repo setup — recommend + confirm + create/connect (fail-closed, hermetic).

Exercises ``core.repo_setup`` with ``core.github.create_repo`` stubbed (no network/GitHub).
Run: ``python scripts/dev/repo_setup_check.py``.
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


def main() -> int:
    from core import github, repo_setup

    _check(repo_setup.recommend_name("p", "A Tiny Idea App") == "a-tiny-idea-app", "recommend slug from idea")
    _check(repo_setup.recommend_name("my-proj", "") == "my-proj", "recommend falls back to project")

    tmp = tempfile.mkdtemp(prefix="pf-repo-setup-")
    try:
        subprocess.run(["git", "init", "-q"], cwd=tmp, capture_output=True, text=True)

        r0 = repo_setup.setup("p", tmp, idea="An Idea", confirm=False)
        _check(r0["created"] is False and r0["reason"] == "confirmation required",
               "no creation without confirm")

        orig = github.create_repo
        github.create_repo = lambda name, private=True, owner="", description="": {
            "ok": True, "adapter": "test", "full_name": name, "url": "https://example.invalid/" + name}
        try:
            r1 = repo_setup.setup("p", tmp, idea="An Idea", confirm=True, private=True)
            _check(r1["created"] and r1["connected"], "create + connect on confirm")
            _check("example.invalid" in repo_setup.remote_url(tmp), "remote url connected")
        finally:
            github.create_repo = orig
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if FAILS:
        print("repo-setup: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("repo-setup: OK (recommend, no-create-without-confirm, create+connect, fail-closed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
