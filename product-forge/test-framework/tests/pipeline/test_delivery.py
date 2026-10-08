"""BI-PF-0421 / BI-PF-0428: optimistic delivery lane (landing never switches the live tree's branch)."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PF_OFFLINE", "1")

from core import backlog, delivery, github, grooming, run_quality_gate as rqg  # noqa: E402
from core import validation_engine as ve  # noqa: E402
from core.paths import PRODUCTS_DIR  # noqa: E402
from core.vcs import VCSManager  # noqa: E402

_PROJ = "_test_delivery"


def _clean():
    shutil.rmtree(os.path.join(str(PRODUCTS_DIR), _PROJ), ignore_errors=True)
    shutil.rmtree(os.path.join(str(PRODUCTS_DIR), _PROJ + "-worktrees"), ignore_errors=True)


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _bare(tmp: Path) -> Path:
    o = tmp / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", str(o)], check=True, capture_output=True)
    return o


def _repo(proj_dir: Path, origin: Path = None) -> Path:
    proj_dir.mkdir(parents=True, exist_ok=True)
    _git(proj_dir, "init", "-q")
    _git(proj_dir, "checkout", "-q", "-b", "develop")
    (proj_dir / "a.txt").write_text("base\n", encoding="utf-8")
    _git(proj_dir, "add", "a.txt")
    _git(proj_dir, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")
    if origin is not None:
        _git(proj_dir, "remote", "add", "origin", str(origin))
        _git(proj_dir, "push", "-u", "origin", "develop")
    return proj_dir


def _wg_branch(proj_dir: Path, iid: str, origin: Path = None) -> str:
    v = VCSManager(str(proj_dir))
    br = v.feature_branch_name("wg", iid)
    _git(proj_dir, "checkout", "-q", "-b", br)
    (proj_dir / "a.txt").write_text("base\nfeature\n", encoding="utf-8")
    _git(proj_dir, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-am", "feat")
    if origin is not None:
        _git(proj_dir, "push", "-u", "origin", br)
    _git(proj_dir, "checkout", "-q", "develop")
    return br


def _seed_verifying() -> str:
    iid = backlog.add_epic("project", _PROJ, "deliver me", tag="TST")["id"]
    grooming.decide("project", _PROJ, iid, "APPROVE")
    backlog.set_status("project", _PROJ, iid, "verifying", note="executed")
    return iid


def _pass(monkeypatch):
    monkeypatch.setattr(ve, "feature_pr", lambda *a, **k: {"result": "PASS"})
    monkeypatch.setattr(rqg, "evaluate", lambda *a, **k: {"passed": True, "reasons": []})
    # no PR number -> exercise the push-ref fallback (the gh path needs a real PR)
    monkeypatch.setattr(github, "create_pr", lambda *a, **k: {"ok": True, "number": "", "url": ""})


def test_deliver_push_ref_advances_develop_without_touching_live_tree(tmp_path, monkeypatch):
    _clean()
    try:
        iid = _seed_verifying()
        proj = Path(str(PRODUCTS_DIR)) / _PROJ
        origin = _bare(tmp_path)
        _repo(proj, origin=origin)
        _wg_branch(proj, iid, origin=origin)
        _pass(monkeypatch)

        r = delivery.deliver("project", _PROJ, iid)
        assert r["ok"] is True and r["method"] == "push-ref", r
        # develop advanced on the remote ...
        out = subprocess.run(["git", "--git-dir", str(origin), "show", "develop:a.txt"],
                             capture_output=True, text=True)
        assert "feature" in out.stdout, "remote develop has the merged change"
        # ... and the live tree's branch was never switched
        assert VCSManager(str(proj)).current_branch() == "develop"
        it = backlog.get("project", _PROJ, iid)
        assert it["status"] == "completed"
        assert (it.get("links") or {}).get("delivery", {}).get("merge_sha") == r["merge_sha"]
    finally:
        _clean()


def test_deliver_blocks_when_branch_missing(monkeypatch):
    _clean()
    try:
        iid = _seed_verifying()
        _repo(Path(str(PRODUCTS_DIR)) / _PROJ)
        _pass(monkeypatch)
        r = delivery.deliver("project", _PROJ, iid)
        assert r["ok"] is False and "not found" in r["reason"], r
        assert backlog.get("project", _PROJ, iid)["status"] == "blocked"
    finally:
        _clean()


def test_deliver_blocks_on_validation_fail(monkeypatch):
    _clean()
    try:
        iid = _seed_verifying()
        proj = Path(str(PRODUCTS_DIR)) / _PROJ
        _repo(proj)
        _wg_branch(proj, iid)
        monkeypatch.setattr(ve, "feature_pr", lambda *a, **k: {"result": "FAIL"})
        monkeypatch.setattr(github, "create_pr", lambda *a, **k: {"ok": True, "number": ""})
        r = delivery.deliver("project", _PROJ, iid)
        assert r["ok"] is False and "validation" in r["reason"], r
        assert backlog.get("project", _PROJ, iid)["status"] == "blocked"
    finally:
        _clean()
