"""
Verification Runner (real test/build execution)

Runs the tests/build for a project workspace when real project files exist, so
'validate' actually verifies instead of only checking file existence. Detects
the stack (Node / Python / Go / Rust) and runs allow-listed commands.

Returns ran=False when nothing recognizable is present (markdown-only runs stay
untouched).
"""
import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


@dataclass
class VerificationResult:
    ran: bool = False
    detected: str = ""
    results: List[Dict] = field(default_factory=list)
    passed: bool = False

    def to_dict(self) -> Dict:
        return asdict(self)


def _which(exe: str) -> bool:
    return shutil.which(exe) is not None


def _run(cmd: List[str], cwd: str, timeout: int = 600) -> Dict:
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        tail = ((r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.stderr else ""))[-4000:]
        return {"cmd": " ".join(cmd), "ok": r.returncode == 0, "tail": tail}
    except subprocess.TimeoutExpired:
        return {"cmd": " ".join(cmd), "ok": False, "tail": "timeout"}
    except FileNotFoundError:
        return {"cmd": " ".join(cmd), "ok": False, "tail": "executable not found"}
    except Exception as e:
        return {"cmd": " ".join(cmd), "ok": False, "tail": str(e)}


def _augment_nfr(res: "VerificationResult", project_dir: str, suite) -> None:
    """Append security/packaging/perf gate results for nfr/packaging modes (4.3-4.6)."""
    if not (suite and suite.get("mode") in ("nfr", "packaging")):
        return
    try:
        from core.nfr_runner import run_for_mode
        nfr = run_for_mode(project_dir, suite["mode"], suite.get("categories", []))
        for e in nfr:
            e["nfr"] = suite["mode"]
        res.results.extend(nfr)
        if nfr:
            res.ran = True
    except Exception:
        pass


def run_verification(project_dir: str, stack_hints: Optional[List[str]] = None,
                     stage_id: Optional[str] = None, use_suites: bool = False) -> Dict:
    res = VerificationResult()
    if not os.path.isdir(project_dir):
        return res.to_dict()

    # Per-phase suite selection (4.1): choose mode/categories for this stage.
    suite = None
    if use_suites:
        try:
            from core.test_framework_bridge import select_for_stage
            suite = select_for_stage(stage_id)
        except Exception:
            suite = None

    pkg = os.path.join(project_dir, "package.json")
    has_py = (
        any(os.path.exists(os.path.join(project_dir, p)) for p in
            ["pyproject.toml", "requirements.txt", "setup.py"])
        or os.path.isdir(os.path.join(project_dir, "tests"))
        or any(fn.endswith(".py") for fn in os.listdir(project_dir)
               if os.path.isfile(os.path.join(project_dir, fn)))
    )

    if os.path.exists(pkg):
        res.ran = True
        res.detected = "node"
        try:
            with open(pkg, "r", encoding="utf-8") as f:
                scripts = (json.load(f) or {}).get("scripts", {})
        except Exception:
            scripts = {}
        runner = "npm" if _which("npm") else ("pnpm" if _which("pnpm") else None)
        if runner:
            if "test" in scripts:
                res.results.append(_run([runner, "test", "--silent"], project_dir))
            if "build" in scripts:
                res.results.append(_run([runner, "run", "build"], project_dir))
        _augment_nfr(res, project_dir, suite)
        res.passed = bool(res.results) and all(r["ok"] for r in res.results)
        return res.to_dict()

    if has_py:
        res.ran = True
        res.detected = "python"
        has_tests = any(
            os.path.isdir(os.path.join(project_dir, d)) for d in ["tests", "test", "src"]
        )
        if _which("python"):
            args = ["python", "-m", "pytest", "-q"]
            paths = []
            if suite:
                try:
                    from core.test_framework_bridge import selected_test_paths
                    paths = selected_test_paths(project_dir, suite["categories"])
                    args += paths
                except Exception:
                    paths = []
            entry = _run(args, project_dir)
            if suite:
                entry["suite"] = {"mode": suite["mode"],
                                  "categories": suite["categories"], "paths": paths}
            res.results.append(entry)
        _augment_nfr(res, project_dir, suite)
        res.passed = bool(res.results) and all(r["ok"] for r in res.results)
        if not has_tests and res.results and not res.results[0]["ok"]:
            res.results[0]["tail"] += "\n(no tests directory found — phantom-tests check)"
        return res.to_dict()

    _augment_nfr(res, project_dir, suite)
    return res.to_dict()
