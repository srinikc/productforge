"""Control evidence SHA must stay valid when its own evidence commit is added."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))
import control_runner as cr  # noqa: E402


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def test_control_sha_ignores_evidence_commit(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "tracked.txt").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "update-ref", "refs/remotes/origin/develop", "HEAD")
    (repo / "feature.txt").write_text("feature\n", encoding="utf-8")
    _git(repo, "add", "feature.txt")
    _git(repo, "commit", "-q", "-m", "feature")

    monkeypatch.setattr(cr, "ROOT", repo)
    before = cr.current_sha()

    ev = repo / "engineering" / "evidence"
    ev.mkdir(parents=True)
    (ev / "control.txt").write_text("PASS\n", encoding="utf-8")
    _git(repo, "add", "engineering/evidence/control.txt")
    _git(repo, "commit", "-q", "-m", "evidence")
    assert cr.current_sha() == before

    (repo / "feature.txt").write_text("feature changed\n", encoding="utf-8")
    _git(repo, "add", "feature.txt")
    _git(repo, "commit", "-q", "-m", "code change")
    assert cr.current_sha() != before
