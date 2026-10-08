"""BI-PF-0421: optimistic delivery lane (push+PR -> validate -> rebase -> merge -> push -> set_delivery)."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

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


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _repo(proj_dir: Path) -> Path:
    proj_dir.mkdir(parents=True, exist_ok=True)
    _git(proj_dir, "init", "-q")
    _git(proj_dir, "checkout", "-q", "-b", "develop")
    (proj_dir / "a.txt").write_text("base\n", encoding="utf-8")
    _git(proj_dir, "add", "a.txt")
    _git(proj_dir, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")
    return proj_dir


def _seed_verifying() -> str:
    iid = backlog.add_epic("project", _PROJ, "deliver me", tag="TST")["id"]
    grooming.decide("project", _PROJ, iid, "APPROVE")
    backlog.set_status("project", _PROJ, iid, "verifying", note="executed")
    return iid


def _pass_validation(monkeypatch):
    monkeypatch.setattr(ve, "feature_pr", lambda *a, **k: {"result": "PASS"})
    monkeypatch.setattr(rqg, "evaluate", lambda *a, **k: {"passed": True, "reasons": []})
    monkeypatch.setattr(github, "create_pr", lambda *a, **k: {"ok": True, "number": "1", "url": "http://x/1"})


def test_deliver_merges_and_records(monkeypatch):
    _clean()
    try:
        iid = _seed_verifying()
        proj_dir = _repo(Path(str(PRODUCTS_DIR)) / _PROJ)
        v = VCSManager(str(proj_dir))
        br = v.feature_branch_name("wg", iid)
        _git(proj_dir, "checkout", "-q", "-b", br)
        (proj_dir / "a.txt").write_text("base\nfeature\n", encoding="utf-8")
        _git(proj_dir, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-am", "feat")
        _git(proj_dir, "checkout", "-q", "develop")
        _pass_validation(monkeypatch)

        r = delivery.deliver("project", _PROJ, iid)
        assert r["ok"] is True and r["merge_sha"], r
        assert "feature" in (proj_dir / "a.txt").read_text(encoding="utf-8"), "merged into develop"
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
        _pass_validation(monkeypatch)
        r = delivery.deliver("project", _PROJ, iid)
        assert r["ok"] is False and "not found" in r["reason"], r
        assert backlog.get("project", _PROJ, iid)["status"] == "blocked"
    finally:
        _clean()


def test_deliver_blocks_on_validation_fail(monkeypatch):
    _clean()
    try:
        iid = _seed_verifying()
        proj_dir = _repo(Path(str(PRODUCTS_DIR)) / _PROJ)
        v = VCSManager(str(proj_dir))
        br = v.feature_branch_name("wg", iid)
        _git(proj_dir, "checkout", "-q", "-b", br)
        (proj_dir / "a.txt").write_text("base\nx\n", encoding="utf-8")
        _git(proj_dir, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-am", "feat")
        _git(proj_dir, "checkout", "-q", "develop")
        monkeypatch.setattr(ve, "feature_pr", lambda *a, **k: {"result": "FAIL"})
        monkeypatch.setattr(github, "create_pr", lambda *a, **k: {"ok": True})
        r = delivery.deliver("project", _PROJ, iid)
        assert r["ok"] is False and "validation" in r["reason"], r
        assert backlog.get("project", _PROJ, iid)["status"] == "blocked"
        assert "feature" not in (proj_dir / "a.txt").read_text(encoding="utf-8"), "not merged on fail"
    finally:
        _clean()
