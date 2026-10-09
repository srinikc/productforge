"""Global command sync: sync .opencode/command_global/*.md -> dest (byte-for-byte) + --check drift guard."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "dev" / "sync_global_commands.py"


def _run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def test_sync_then_check(tmp_path):
    d = tmp_path / "cmd"
    r = _run("--dest", str(d))
    assert r.returncode == 0, r.stdout + r.stderr
    assert (d / "pf.md").exists() and (d / "wg.md").exists()
    r2 = _run("--check", "--dest", str(d))
    assert r2.returncode == 0, r2.stdout + r2.stderr


def test_check_detects_drift(tmp_path):
    d = tmp_path / "cmd"
    _run("--dest", str(d))
    (d / "pf.md").write_text("tampered\n", encoding="utf-8")
    r = _run("--check", "--dest", str(d))
    assert r.returncode == 1
