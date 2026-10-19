"""BI-PF-1427: Gate 2.5 architect-review helper - structured findings parsing."""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import architect_review as ar  # noqa: E402
import architect_review_check as c  # noqa: E402
import gitutil  # noqa: E402


def test_parse_review_sections():
    text = (
        "### BLOCKER\n- secret in log\n"
        "### MAJOR\n- no test for the new path\n"
        "### MINOR\n- naming\n"
        "### NIT\n- spacing\n"
        "### SUMMARY\n- overall fine once blocker fixed\n"
    )
    r = ar.parse_review(text)
    assert r["BLOCKER"] == ["secret in log"]
    assert r["MAJOR"] == ["no test for the new path"]
    assert r["MINOR"] == ["naming"]
    assert r["NIT"] == ["spacing"]
    assert r["SUMMARY"] == ["overall fine once blocker fixed"]


def test_parse_review_empty():
    r = ar.parse_review("no findings")
    assert all(r[s] == [] for s in ar.SEVERITIES)


def test_iter_findings_canonical_order():
    f = {"NIT": ["n1"], "BLOCKER": ["b1", "b2"], "MINOR": ["m1"], "MAJOR": ["j1"]}
    assert list(ar.iter_findings(f)) == [
        ("BLOCKER", "b1"), ("BLOCKER", "b2"), ("MAJOR", "j1"), ("MINOR", "m1"), ("NIT", "n1"),
    ]


def test_pending_blocking_only_blocks_blocker_and_major():
    f = {"BLOCKER": ["b"], "MAJOR": ["j"], "MINOR": ["m"], "NIT": ["n"]}
    # all pending -> the two high severities block; total/pending count all
    total, pending, blocking = ar.pending_blocking(f, {})
    assert (total, pending) == (4, 4)
    assert [s for _, s, _ in blocking] == ["BLOCKER", "MAJOR"]

    disp = {"1": {"status": "actioned"}, "2": {"status": "deferred"}, "3": {"status": "PENDING"}}
    total, pending, blocking = ar.pending_blocking(f, disp)
    assert (total, pending, blocking) == (4, 2, [])
    # a pending MINOR/NIT never blocks
    assert blocking == []


def test_none_placeholder_is_not_a_finding():
    f = {"BLOCKER": ["none"], "MAJOR": ["-"], "MINOR": [], "NIT": []}
    assert list(ar.iter_findings(f)) == []
    assert ar.pending_blocking(f, {}) == (0, 0, [])


def test_dispositions_bind_by_content_signature_across_reorder():
    # a content-hash disposition stays attached when findings are reordered/reclassified
    disp = {"sig:" + ar.finding_sig("finding A"): {"status": "accepted"}}
    total, pending, blocking = ar.pending_blocking({"MAJOR": ["finding B", "finding A"]}, disp)
    assert (total, pending) == (2, 1)
    assert [t for _, _, t in blocking] == ["finding B"]


def test_sig_pending_does_not_shadow_valid_ordinal():
    disp = {"sig:" + ar.finding_sig("A"): {"status": "PENDING"}, "1": {"status": "actioned"}}
    assert ar.pending_blocking({"BLOCKER": ["A"]}, disp) == (1, 0, [])


def test_unknown_status_is_fail_closed():
    total, pending, blocking = ar.pending_blocking({"MAJOR": ["A"]}, {"1": {"status": "typo"}})
    assert (total, pending) == (1, 1) and blocking


def test_design_prompt_includes_checklist():
    p = ar._build_prompt({"acceptance_criteria": ["x"]}, "ID", "design")
    assert "Design pre-check checklist" in p


def test_gate_command_blocks_on_pending(monkeypatch):
    pending = {"review": {"findings": {"BLOCKER": ["b"]}, "model": "m", "sha": "s"},
               "dispositions": {}, "total": 1, "pending": 1, "blocking": [(1, "BLOCKER", "b")]}
    monkeypatch.setattr(ar, "gate_view", lambda item, mode="design": pending)
    assert ar.main(["gate", "--item", "X", "--gate", "1"]) == 1


def test_gate1_check_exit_codes(monkeypatch):
    import gate1_check as g1

    monkeypatch.setattr(g1.ar, "gate_view", lambda item, mode="design": None)
    assert g1.main(["--item", "X"]) == 2          # no evidence

    clean = {"review": {"findings": {}, "model": "m", "sha": "s"}, "dispositions": {},
             "total": 0, "pending": 0, "blocking": []}
    monkeypatch.setattr(g1.ar, "gate_view", lambda item, mode="design": clean)
    assert g1.main(["--item", "X"]) == 0          # all dispositioned

    pending = {"review": {"findings": {"MAJOR": ["m"]}, "model": "m", "sha": "s"},
               "dispositions": {}, "total": 1, "pending": 1, "blocking": [(1, "MAJOR", "m")]}
    monkeypatch.setattr(g1.ar, "gate_view", lambda item, mode="design": pending)
    assert g1.main(["--item", "X"]) == 1          # BLOCKER/MAJOR pending


def test_git_text_forces_utf8_decoding(monkeypatch):
    """BI-PF-1464: never decode git stdout with the OS locale (cp1252 on Windows)."""
    captured = {}

    class _Done:
        stdout = "caf\u00e9 \u2014 \u2192"
        stderr = ""
        returncode = 0

    def fake_run(cmd, **kw):
        captured["cmd"] = list(cmd)
        captured.update(kw)
        return _Done()

    monkeypatch.setattr(gitutil.subprocess, "run", fake_run)
    assert gitutil.git_text(["diff"], ar.ROOT) == "caf\u00e9 \u2014 \u2192"
    assert captured["encoding"] == "utf-8"
    assert captured["errors"] == "replace"
    assert "text" not in captured


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@local"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)


def test_git_text_decodes_real_utf8_bytes(tmp_path, monkeypatch):
    """End-to-end: real git output containing non-cp1252 UTF-8 must decode (fails pre-fix on Windows)."""
    _init_repo(tmp_path)
    (tmp_path / "note.txt").write_text("caf\u00e9 \u2014 \u2192\n", encoding="utf-8")
    subprocess.run(["git", "add", "note.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)
    monkeypatch.setattr(ar, "ROOT", tmp_path)

    assert ar._git_text(["show", "HEAD:note.txt"]) == "caf\u00e9 \u2014 \u2192\n"


def test_git_text_fails_closed_on_git_error(tmp_path, monkeypatch):
    """A failing git command must raise, never silently become an empty diff."""
    _init_repo(tmp_path)
    monkeypatch.setattr(ar, "ROOT", tmp_path)

    with pytest.raises(gitutil.GitError):
        ar._git_text(["rev-parse", "definitely-not-a-ref"])


def test_check_fails_closed_when_git_missing(monkeypatch):
    def boom():
        raise OSError("git not found")

    monkeypatch.setattr(c.ar, "changed_files", boom)
    assert c.main() == 1


def test_check_fails_closed_when_diff_unavailable(monkeypatch):
    def boom():
        raise RuntimeError("git diff failed")

    monkeypatch.setattr(c.ar, "changed_files", boom)
    assert c.main() == 1

