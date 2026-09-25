"""Run-mode-aware quality gate (BI-0184).

The repo gate (`compileall` + `wired_audit`) traditionally ran only in CI / the PR merge gate. For
an ITEM / amend run (a real change) it IS needed; for a full e2e run it is not (per-agent compliance
already runs for every agent). This module:
  * runs the gate as a subprocess (compileall + wired_audit),
  * records the result on the project as `quality-gate.json`,
  * exposes read helpers for the dashboard.

Owner: this module (single writer of quality-gate.json). Wired into pipeline_executor at run end.
"""
import json
import os
import subprocess
import sys
from datetime import datetime
from typing import Dict, List, Optional

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILENAME = "quality-gate.json"
GATED_MODES = {"item", "amend"}


def should_gate(mode: str) -> bool:
    """Only item/amend runs are gated by the repo audits; e2e is not."""
    return str(mode or "").lower() in GATED_MODES


def mode_from_scope(scope: Optional[Dict]) -> str:
    """Derive the run mode from a run-scope: selective -> 'item', else 'e2e'."""
    if isinstance(scope, dict) and (scope.get("only_stages") or scope.get("only_agents")):
        return "item"
    return "e2e"


def _run(cmd: List[str], cwd: str, timeout: int = 900):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return 1, str(e)


def evaluate(project_dir: str = "", mode: str = "item") -> Dict:
    """Run compileall + wired_audit; return {passed, mode, reasons, checks}. Records if project_dir."""
    checks = []
    rc1, out1 = _run([sys.executable, "-m", "compileall", "-q", "core", "scripts", "dashboard"], REPO)
    checks.append({"name": "compileall", "passed": rc1 == 0, "rc": rc1, "tail": out1[-400:]})
    rc2, out2 = _run([sys.executable, os.path.join("scripts", "dev", "wired_audit.py")], REPO)
    checks.append({"name": "wired_audit", "passed": rc2 == 0, "rc": rc2, "tail": out2[-1000:]})
    result = {"passed": all(c["passed"] for c in checks), "mode": mode,
              "at": datetime.now().isoformat(timespec="seconds"), "checks": checks,
              "reasons": [c["name"] for c in checks if not c["passed"]]}
    if project_dir:
        record(project_dir, result)
    return result


def record(project_dir: str, result: Dict) -> None:
    try:
        os.makedirs(project_dir, exist_ok=True)
        p = os.path.join(project_dir, FILENAME)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        os.replace(tmp, p)
    except Exception:
        pass


def latest(project_dir: str) -> Optional[Dict]:
    try:
        return json.load(open(os.path.join(project_dir, FILENAME), encoding="utf-8"))
    except Exception:
        return None


def gate_if_item_run(project_dir: str, mode: str) -> Optional[Dict]:
    """Run + record the gate ONLY for item/amend modes. Returns the result or None if skipped."""
    if not should_gate(mode):
        return None
    res = evaluate(project_dir, mode)
    print(f"  [QualityGate] mode={mode} passed={res['passed']}"
          + ("" if res["passed"] else f" reasons={res['reasons']}"))
    return res


def _main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Run-mode-aware quality gate (BI-0184)")
    ap.add_argument("--project-dir", default="")
    ap.add_argument("--mode", default="item")
    a = ap.parse_args(argv)
    res = evaluate(a.project_dir, a.mode)
    print(json.dumps({k: res[k] for k in ("passed", "mode", "reasons")}, indent=2))
    return 0 if res["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(_main())
