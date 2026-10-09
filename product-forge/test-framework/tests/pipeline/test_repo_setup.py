"""BI-PF: stage-0 repo setup (core.repo_setup) + API endpoints."""
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
os.environ.setdefault("PF_OFFLINE", "1")
os.environ.setdefault("API_ALLOW_ANON", "1")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import app  # noqa: E402
from core import github, repo_setup  # noqa: E402


def test_recommend_name():
    assert repo_setup.recommend_name("p", "A Tiny Idea!") == "a-tiny-idea"


def test_no_create_without_confirm(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), capture_output=True, text=True)
    r = repo_setup.setup("p", str(tmp_path), idea="An Idea", confirm=False)
    assert r["created"] is False and r["reason"] == "confirmation required"


def test_create_and_connect_on_confirm(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), capture_output=True, text=True)
    monkeypatch.setattr(github, "create_repo", lambda name, private=True, owner="", description="": {
        "ok": True, "adapter": "test", "full_name": name, "url": "https://example.invalid/" + name})
    r = repo_setup.setup("p", str(tmp_path), idea="An Idea", confirm=True)
    assert r["created"] and r["connected"]
    assert "example.invalid" in repo_setup.remote_url(str(tmp_path))


def test_failclosed_local_only(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), capture_output=True, text=True)
    monkeypatch.setattr(github, "create_repo", lambda name, private=True, owner="", description="": {
        "ok": False, "reason": "no gh CLI and no GITHUB_TOKEN/GH_TOKEN"})
    r = repo_setup.setup("p", str(tmp_path), idea="An Idea", confirm=True)
    assert r["created"] is False and r.get("local_only") is True


def test_api_endpoints(tmp_path, monkeypatch):
    from core import paths
    d = Path(str(paths.PRODUCTS_DIR)) / "_test_repo_api"
    d.mkdir(parents=True, exist_ok=True)
    (d / "project.json").write_text('{"name":"_test_repo_api","idea":"An Idea"}', encoding="utf-8")
    monkeypatch.setattr(repo_setup, "status", lambda p, pd, idea="": {"recommended_name": "an-idea"})
    monkeypatch.setattr(repo_setup, "setup", lambda *a, **k: {"created": False, "reason": "confirmation required"})
    client = TestClient(app)
    try:
        assert client.get("/api/v1/projects/_test_repo_api/repo").status_code == 200
        assert client.post("/api/v1/projects/_test_repo_api/repo", json={"confirm": True}).status_code == 200
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)
