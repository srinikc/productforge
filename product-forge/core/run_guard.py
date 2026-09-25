"""Single-run guard: ensure exactly ONE pipeline instance per project.

On any start/restart/resume/continue:
  1. clean up stale locks,
  2. if another instance holds the lock AND its process is alive -> ask it to STOP
     (via the project's ``control.json`` channel the stage runner honors), wait for
     it to exit, and force-terminate if it does not,
  3. acquire the lock and return.

Never touches user data — it only coordinates processes.
"""
import json
import os
import subprocess
import time
from datetime import datetime
from typing import Dict, Optional

from core.lock_manager import LockManager


def _pid_from_holder(holder: str) -> Optional[int]:
    """``run-12345`` (or a bare int) -> 12345; else None."""
    h = str(holder or "").strip()
    if h.startswith("run-"):
        h = h[4:]
    try:
        return int(h)
    except Exception:
        return None


def _pid_alive(pid: int) -> bool:
    if not pid:
        return False
    try:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"],
                             capture_output=True, text=True, timeout=10).stdout
        return str(pid) in (out or "")
    except Exception:
        try:
            os.kill(pid, 0)
            return True
        except Exception:
            return False


def _terminate(pid: int) -> bool:
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       capture_output=True, text=True, timeout=15)
        return True
    except Exception:
        try:
            os.kill(pid, 9)
            return True
        except Exception:
            return False


def _write_control(project_dir: str, action: str) -> None:
    try:
        with open(os.path.join(project_dir, "control.json"), "w", encoding="utf-8") as f:
            json.dump({"action": action, "updated_at": datetime.now().isoformat()}, f)
    except Exception:
        pass


def active_run(project: str, products_dir: str = "products") -> Dict:
    """Describe any live run for the project (without stopping it)."""
    lm = LockManager(products_dir)
    info = lm.get_lock_info(project)
    if not info:
        return {"active": False}
    pid = _pid_from_holder(info.holder)
    return {"active": bool(not info.is_expired() and (pid is None or _pid_alive(pid))),
            "holder": info.holder, "pid": pid, "run_id": getattr(info, "run_id", ""),
            "expired": info.is_expired()}


def ensure_single_run(project: str, products_dir: str = "products",
                      wait_seconds: int = 20, force: bool = True,
                      run_id: str = "") -> Dict:
    """Stop any other instance, then acquire the lock. Returns a report."""
    lm = LockManager(products_dir)
    report: Dict = {"project": project, "stopped": False, "forced": False,
                    "waited_s": 0, "stopped_run": "", "acquired": False, "run_id": run_id}
    try:
        lm.cleanup_stale_locks()
    except Exception:
        pass

    info = lm.get_lock_info(project)
    if info and not info.is_expired():
        pid = _pid_from_holder(info.holder)
        alive = (pid is None) or _pid_alive(pid)
        if alive:
            report["stopped_run"] = getattr(info, "run_id", "") or info.holder
            project_dir = os.path.join(products_dir, project)
            print(f"  [Guard] '{project}' is running ({info.holder}); requesting stop...")
            _write_control(project_dir, "stop")
            for i in range(max(1, wait_seconds)):
                time.sleep(1)
                report["waited_s"] = i + 1
                if not lm.is_locked(project):
                    break
            if lm.is_locked(project):
                if force and pid:
                    print(f"  [Guard] did not stop gracefully; terminating pid {pid}")
                    _terminate(pid)
                    report["forced"] = True
                try:
                    lm.release_lock(project, info.holder)
                except Exception:
                    pass
            report["stopped"] = True

    lock = lm.acquire_lock(project, holder=f"run-{os.getpid()}", run_id=run_id or None)
    report["acquired"] = lock is not None
    if lock is not None:
        try:
            # reset the control channel for the new run
            _write_control(os.path.join(products_dir, project), "run")
        except Exception:
            pass
    return report


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Single-run guard")
    ap.add_argument("project")
    ap.add_argument("--products-dir", default="products")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.status:
        print(json.dumps(active_run(a.project, a.products_dir), indent=2))
    else:
        print(json.dumps(ensure_single_run(a.project, a.products_dir), indent=2))
